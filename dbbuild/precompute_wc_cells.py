#!/usr/bin/env python
"""
Precalcula wc_cells (celdas por rango WorldClim y por malla) para que
get-data/3 del middleware no tenga que unir polígonos y cruzarlos con la malla
en cada análisis (~23 s por rango en 8 km).

Por cada rango (raster_bins.bid) se copian sus polígonos a una tabla temporal
con índice en meshandregions_db y se cruzan con cada resolución completa. Las
celdas de cada región (cat_grid.region_id) se calculan una sola vez por grid_id,
con el mismo criterio que el middleware (ST_Intersects con el border de
grid_geojson_<res>_aoi).

Fases: primero mallas regulares (64/32/16/8 km), luego las de México
(state/mun/cue/ageb). Es reanudable: solo calcula los (bid, grid_id) que aún no
están en wc_cells.

Uso:
  python precompute_wc_cells.py [--phase regular|irregular|all] [--bids 300000,300001]
                                [--grids 1,13] [--force]
"""
import os
import sys
import time
import logging
import argparse

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

REGULAR = ['64km', '32km', '16km', '8km']
IRREGULAR = ['state', 'mun', 'cue', 'ageb']

logging.basicConfig(format='[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)
log = logging.getLogger('wc_cells')


def env_first(*names):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def connect_wc():
    return psycopg2.connect(
        dbname=os.getenv('DBNICHENAME'), host=os.getenv('DBNICHEHOST'), port=os.getenv('DBNICHEPORT'),
        user=os.getenv('DBNICHEUSER'), password=os.getenv('DBNICHEPASSWD'),
        application_name='wc_cells_precompute')


def connect_mesh():
    return psycopg2.connect(
        dbname=env_first('DBMESHNAME', 'DBNAME_MALLAS'), host=env_first('DBMESHHOST', 'DBHOST_MALLAS'),
        port=env_first('DBMESHPORT', 'DBPORT_MALLAS'), user=env_first('DBMESHUSER', 'DBUSER_MALLAS'),
        password=env_first('DBMESHPASSWD', 'DBPWD_MALLAS'),
        application_name='wc_cells_precompute', options='-c work_mem=64MB')


def load_grids(mesh, resolutions, only_grids):
    """{resolution: {'table', 'view', 'grids': [(grid_id, region_id)]}}"""
    with mesh.cursor() as cur:
        cur.execute("""SELECT grid_id, region_id, resolution, table_cell_name, table_view_name
                       FROM cat_grid WHERE resolution = ANY(%s) ORDER BY grid_id""", (resolutions,))
        out = {}
        for grid_id, region_id, res, table, view in cur.fetchall():
            if only_grids and grid_id not in only_grids:
                continue
            entry = out.setdefault(res, {'table': table, 'view': view, 'grids': []})
            entry['grids'].append((grid_id, region_id))
    # conserva el orden de prioridad (64km primero, etc.)
    return {r: out[r] for r in resolutions if r in out}


def region_cells(mesh, table, view, res, region_id):
    """Celdas de la malla dentro de la región, igual que el CTE regionarea del middleware."""
    with mesh.cursor() as cur:
        cur.execute(f"""
            SELECT array_agg(DISTINCT g.gridid_{res})
            FROM {table} g
            JOIN {view} vg ON ST_Intersects(g.the_geom, vg.border)
            WHERE vg.region_id = %s""", (region_id,))
        return set(cur.fetchone()[0] or [])


def load_bins(wc, only_bids):
    with wc.cursor() as cur:
        cur.execute("""SELECT rb.bid, rb.layer, rb.icat, fb.bins
                       FROM raster_bins rb JOIN fuentes_bioclimaticas fb ON fb.id = rb.id_fuentes_bio
                       ORDER BY rb.bid""")
        rows = cur.fetchall()
    return [r for r in rows if not only_bids or r[0] in only_bids]


def done_pairs(wc):
    with wc.cursor() as cur:
        cur.execute("SELECT bid, grid_id FROM wc_cells")
        return set(cur.fetchall())


def load_bin_polygons(wc, mesh, layer, icat, nbins):
    """Copia los polígonos del rango a la tabla temporal bin_polys de mesh."""
    table = f"{layer}_q{nbins}"
    with wc.cursor() as cur:
        cur.execute(f"""SELECT ST_AsEWKB(ST_SetSRID(the_geom, 4326))
                        FROM {psycopg2.extensions.quote_ident(table, cur)}
                        WHERE categoria = %s AND icat = %s""", (layer, icat))
        polys = [(bytes(r[0]),) for r in cur.fetchall()]
    with mesh.cursor() as cur:
        cur.execute("TRUNCATE bin_polys")
        psycopg2.extras.execute_values(cur, "INSERT INTO bin_polys (geom) VALUES %s", polys,
                                       template="(ST_GeomFromEWKB(%s))", page_size=2000)
        cur.execute("ANALYZE bin_polys")
    return len(polys)


def bin_cells(mesh, table, res):
    with mesh.cursor() as cur:
        cur.execute(f"""
            SELECT DISTINCT g.gridid_{res}
            FROM bin_polys p
            JOIN {table} g ON ST_Intersects(g.the_geom, p.geom)""")
        return {r[0] for r in cur.fetchall()}


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['regular', 'irregular', 'all'], default='all')
    ap.add_argument('--bids', help='lista de bid separada por comas (prueba)')
    ap.add_argument('--grids', help='lista de grid_id separada por comas (prueba)')
    ap.add_argument('--force', action='store_true', help='recalcular aunque ya exista en wc_cells')
    args = ap.parse_args()

    only_bids = {int(x) for x in args.bids.split(',')} if args.bids else None
    only_grids = {int(x) for x in args.grids.split(',')} if args.grids else None
    phases = {'regular': [('regulares', REGULAR)], 'irregular': [('irregulares', IRREGULAR)],
              'all': [('regulares', REGULAR), ('irregulares', IRREGULAR)]}[args.phase]

    wc = connect_wc()
    wc.autocommit = True
    mesh = connect_mesh()
    mesh.autocommit = True

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sql', 'create_wc_cells.sql')) as f:
        wc.cursor().execute(f.read())
    mesh.cursor().execute("CREATE TEMP TABLE bin_polys (geom geometry(Geometry, 4326))")
    mesh.cursor().execute("CREATE INDEX ON bin_polys USING gist (geom)")

    bins = load_bins(wc, only_bids)

    for phase_name, resolutions in phases:
        grids = load_grids(mesh, resolutions, only_grids)
        all_grid_ids = [gid for g in grids.values() for gid, _ in g['grids']]
        done = set() if args.force else done_pairs(wc)
        pending = [b for b in bins if any((b[0], gid) not in done for gid in all_grid_ids)]
        log.info(f"Fase {phase_name}: mallas={all_grid_ids} rangos pendientes={len(pending)}/{len(bins)}")
        if not pending:
            continue

        regions = {}
        for res, g in grids.items():
            for grid_id, region_id in g['grids']:
                t0 = time.time()
                regions[grid_id] = region_cells(mesh, g['table'], g['view'], res, region_id)
                log.info(f"  región grid_id={grid_id} ({res}, region {region_id}): "
                         f"{len(regions[grid_id])} celdas en {time.time() - t0:.1f}s")

        started = time.time()
        for i, (bid, layer, icat, nbins) in enumerate(pending, 1):
            t0 = time.time()
            npolys = load_bin_polygons(wc, mesh, layer, icat, nbins)
            rows = []
            for res, g in grids.items():
                todo = [(gid, rid) for gid, rid in g['grids'] if (bid, gid) not in done]
                if not todo:
                    continue
                cells = bin_cells(mesh, g['table'], res) if npolys else set()
                for grid_id, _ in todo:
                    rows.append((bid, grid_id, sorted(cells & regions[grid_id])))
            with wc.cursor() as cur:
                psycopg2.extras.execute_values(cur, """
                    INSERT INTO wc_cells (bid, grid_id, cells) VALUES %s
                    ON CONFLICT (bid, grid_id) DO UPDATE SET cells = EXCLUDED.cells, updated_at = now()""",
                    rows)
            elapsed = time.time() - started
            eta = elapsed / i * (len(pending) - i) / 3600
            log.info(f"[{phase_name}] {i}/{len(pending)} bid={bid} {layer} icat={icat} "
                     f"polígonos={npolys} mallas={len(rows)} tiempo={time.time() - t0:.1f}s eta~{eta:.1f}h")

    log.info("Precalculo WorldClim completo.")


if __name__ == '__main__':
    sys.exit(main())
