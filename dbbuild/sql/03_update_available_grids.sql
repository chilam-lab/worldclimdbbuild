DO $$
DECLARE
  t record;
  bio record;
  total_targets int;
  total_ok int := 0;
  v_sql text;
  has_presence boolean;
  has_region_col boolean;
  has_border_col boolean;
  t0 timestamptz;
  target_source_id integer := __WC_SOURCE_ID__;
  result_grids int4[];
BEGIN
  t0 := clock_timestamp();

  IF NOT EXISTS (SELECT 1 FROM fuentes_bioclimaticas WHERE id = target_source_id) THEN
    RAISE EXCEPTION 'WorldClim source id % not found', target_source_id;
  END IF;

  CREATE TEMP TABLE tmp_wc_mesh_presence (
    table_view_name text,
    region_id int4,
    has_presence boolean,
    PRIMARY KEY (table_view_name, region_id)
  ) ON COMMIT DROP;

  CREATE TEMP TABLE tmp_wc_bio_tables (
    table_name text PRIMARY KEY
  ) ON COMMIT DROP;

  INSERT INTO tmp_wc_bio_tables (table_name)
  SELECT DISTINCT lower(rb.layer || '_q' || fb.bins::text) AS table_name
  FROM fuentes_bioclimaticas fb
  JOIN raster_bins rb ON rb.id_fuentes_bio = fb.id
  WHERE fb.id = target_source_id
    AND rb.layer IS NOT NULL
    AND fb.bins IS NOT NULL;

  DELETE FROM tmp_wc_bio_tables
  WHERE to_regclass(format('public.%I', table_name)) IS NULL;

  IF NOT EXISTS (SELECT 1 FROM tmp_wc_bio_tables) THEN
    RAISE EXCEPTION 'No WorldClim bio tables found for source id %', target_source_id;
  END IF;

  SELECT count(*)
  INTO total_targets
  FROM (
    SELECT DISTINCT table_view_name, region_id
    FROM wc_mesh_fdw.cat_grid
    WHERE table_view_name IS NOT NULL
      AND region_id IS NOT NULL
  ) q;

  RAISE NOTICE '[wc_available_grids] Inicio. combinaciones (vista,region)=%', total_targets;

  FOR t IN
    SELECT DISTINCT table_view_name, region_id
    FROM wc_mesh_fdw.cat_grid
    WHERE table_view_name IS NOT NULL
      AND region_id IS NOT NULL
    ORDER BY table_view_name, region_id
  LOOP
    IF to_regclass(format('wc_mesh_fdw.%I', t.table_view_name)) IS NULL THEN
      INSERT INTO tmp_wc_mesh_presence VALUES (t.table_view_name, t.region_id, false)
      ON CONFLICT DO NOTHING;
      CONTINUE;
    END IF;

    SELECT EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'wc_mesh_fdw'
        AND table_name = t.table_view_name
        AND column_name = 'region_id'
    ) INTO has_region_col;

    SELECT EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'wc_mesh_fdw'
        AND table_name = t.table_view_name
        AND column_name = 'border'
    ) INTO has_border_col;

    IF NOT has_region_col OR NOT has_border_col THEN
      INSERT INTO tmp_wc_mesh_presence VALUES (t.table_view_name, t.region_id, false)
      ON CONFLICT DO NOTHING;
      CONTINUE;
    END IF;

    has_presence := false;

    FOR bio IN
      SELECT table_name
      FROM tmp_wc_bio_tables
      ORDER BY table_name
    LOOP
      v_sql := format($f$
        SELECT EXISTS (
          SELECT 1
          FROM public.%I d
          JOIN wc_mesh_fdw.%I g
            ON g.region_id = %L
           AND d.the_geom IS NOT NULL
           AND d.the_geom && g.border
           AND ST_Intersects(d.the_geom, g.border)
          LIMIT 1
        )
      $f$, bio.table_name, t.table_view_name, t.region_id);

      BEGIN
        EXECUTE v_sql INTO has_presence;
      EXCEPTION WHEN OTHERS THEN
        has_presence := false;
      END;

      IF has_presence THEN
        EXIT;
      END IF;
    END LOOP;

    IF has_presence THEN
      total_ok := total_ok + 1;
    END IF;

    INSERT INTO tmp_wc_mesh_presence (table_view_name, region_id, has_presence)
    VALUES (t.table_view_name, t.region_id, has_presence)
    ON CONFLICT (table_view_name, region_id)
    DO UPDATE SET has_presence = EXCLUDED.has_presence;
  END LOOP;

  SELECT COALESCE(array_agg(cg.grid_id ORDER BY cg.grid_id), '{}'::int4[])
  INTO result_grids
  FROM wc_mesh_fdw.cat_grid cg
  JOIN tmp_wc_mesh_presence p
    ON p.table_view_name = cg.table_view_name
   AND p.region_id = cg.region_id
  WHERE p.has_presence;

  UPDATE fuentes_bioclimaticas
  SET available_grids = result_grids
  WHERE id = target_source_id;

  RAISE NOTICE '[wc_available_grids] Fin. combinaciones_con_presencia=% de %', total_ok, total_targets;
  RAISE NOTICE '[wc_available_grids] Fin. tiempo=%', (clock_timestamp() - t0);
END$$;
