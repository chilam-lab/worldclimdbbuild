var debug = require('debug')('verbs:auth')
var verb_utils = require('./verb_utils')
var pgp = require('pg-promise')()
var config = require('../../config')

var pool = verb_utils.pool 
var pool_mallas = verb_utils.pool_mallas 


let dic_wc_select = new Map();
dic_wc_select.set('1','select array_agg(bid) as level_id, id_fuentes_bio, (fb.fuente || \' - \' || fb.descripcion) as  descripcion, fb.bins, fb.area ')
dic_wc_select.set('2','select array_agg(bid) as level_id, array_agg(layer) as layers, id_fuentes_bio, layer, (fb.fuente || \' - \' || fb.descripcion) as  descripcion, fb.bins, fb.area, rb."label"')
dic_wc_select.set('3','select bid as level_id, tag, id_fuentes_bio, layer, icat, (fb.fuente || \' - \' || fb.descripcion) as  descripcion, fb.bins, fb.area, rb."label"')

let dic_wc_group = new Map();
dic_wc_group.set('1','group by id_fuentes_bio, fb.fuente, fb.descripcion, fb.bins, fb.area ')
dic_wc_group.set('2','group by id_fuentes_bio, layer, fb.fuente, fb.descripcion, fb.bins, fb.area, rb."label"')
dic_wc_group.set('3','')

let dic_wc_order = new Map();
dic_wc_order.set('1','order by id_fuentes_bio')
dic_wc_order.set('2','order by id_fuentes_bio, layer')
dic_wc_order.set('3','order by bid')

const MAX_LIMIT = 1000
const MAX_LEVELS = 500

let valid_filters = ["idfuente","idlayer","idrange", "descripcion"]

let dic_labeltocolumns = new Map();
dic_labeltocolumns.set('fuente','descripcion')
dic_labeltocolumns.set('idfuente','idfuente')

dic_labeltocolumns.set('layer','idlayer')
dic_labeltocolumns.set('rango','idrange')
dic_labeltocolumns.set('Fuente','descripcion')
dic_labeltocolumns.set('Layer','idlayer')
dic_labeltocolumns.set('Rango','idrange')

let dic_wc_db = new Map();
dic_wc_db.set('idfuente','id_fuentes_bio')
dic_wc_db.set('idlayer','layer')
dic_wc_db.set('idrange','bid')
dic_wc_db.set('descripcion','descripcion')


let dic_secuencia_db = new Map();
dic_secuencia_db.set('Fuente','fuente')
dic_secuencia_db.set('Layer','layer')
dic_secuencia_db.set('Rango','tag')

let fuente_bios = ['bio001','bio002','bio003','bio004','bio005','bio006','bio007','bio008','bio009','bio010','bio011','bio012','bio013','bio014','bio015','bio016','bio017','bio018','bio019']

exports.get_sourceinfo = async function get_sourceinfo(req, res) {
  // Si quieres solo lectura real, deja únicamente GET
  if (req.method !== 'GET') {
    return res.status(405).json({
      message: 'Método no permitido'
    });
  }

  try {
    const data = await pool.oneOrNone(`
      SELECT name, description, source_url, download_url, dict_url
      FROM data_source_info
      ORDER BY updated_at DESC, id DESC
      LIMIT 1
    `);

    if (!data) {
      return res.status(404).json({
        message: 'No se encontró la fuente de datos.'
      });
    }

    return res.status(200).json({ data });
  } catch (error) {
    debug(error);
    return res.status(500).json({
      message: 'Error interno al obtener la fuente de datos.'
    });
  }
};



exports.variables = async function variables(req, res) {
  try {
    const data = await pool.any(`
      with available_wc as (
        select
          coalesce(
            array_agg(distinct grids.grid_id order by grids.grid_id) filter (where grids.grid_id is not null),
            array[]::int[]
          ) as available_grids
        from fuentes_bioclimaticas fb
        left join lateral unnest(coalesce(fb.available_grids, array[]::int[])) as grids(grid_id) on true
      ),
      fuentes_wc as (
        select id_fuentes_bio
        from raster_bins rb
        group by id_fuentes_bio
      )
      select 1 as id, 'Fuente' as variable, count(*) level_size,
             ('{"idfuente":"string"}')::jsonb filter_fields,
             (select available_grids from available_wc) as available_grids
      from fuentes_wc

      union all

      (
        with layers_wc as (
          select layer
          from raster_bins rb
          group by layer
        )
        select 2 as id, 'Layer' as variable, count(*) level_size,
               ('{"idfuente":"string","idlayer":"string"}')::jsonb filter_fields,
               (select available_grids from available_wc) as available_grids
        from layers_wc
      )

      union all

      (
        with ranges_wc as (
          select id_fuentes_bio, layer, icat
          from raster_bins rb
          group by id_fuentes_bio, layer, icat
        )
        select 3 as id, 'Rango' as variable, count(*) level_size,
               ('{"idfuente":"string","idlayer":"string","idrange":"string"}')::jsonb filter_fields,
               (select available_grids from available_wc) as available_grids
        from ranges_wc
      )

      order by id;
    `);

    return res.status(200).json({ data });
  } catch (error) {
    debug(error);
    return res.status(500).json({
      message: "Error interno al obtener catálogo",
      error: error.message
    });
  }
};



exports.secuencia = async function secuencia(req, res) {
  try {
    const {
      variableLevel,
      variableValue,
      nextVariableLevel
    } = req.body || {};

    if (!variableLevel || !variableValue || !nextVariableLevel) {
      return res.status(400).json({
        message: "Parámetros requeridos: variableLevel, variableValue, nextVariableLevel"
      });
    }

    const current = String(variableLevel).trim().toLowerCase();
    const next = String(nextVariableLevel).trim().toLowerCase();

    // Transiciones soportadas por el endpoint
    const validTransition =
      (current === "fuente" && next === "layer") ||
      (current === "layer" && next === "rango");

    if (!validTransition) {
      return res.status(400).json({
        message: "Transición inválida. Usa Fuente->Layer o Layer->Rango."
      });
    }

    let data = [];

    if (current === "fuente") {
      // variableValue = id de fuente
      data = await pool.any(
        `
        select distinct
          rb.layer as value,
          rb.label
        from fuentes_bioclimaticas fb
        join raster_bins rb on fb.id = rb.id_fuentes_bio
        where fb.id = $1
        order by rb.layer;
        `,
        [variableValue]
      );
    } else {
      // current === "layer", variableValue = nombre de capa (ej. bio018)
      data = await pool.any(
        `
        select distinct
          rb.bid    as value,
          rb.tag,
          rb.icat,
          rb.layer,
          rb.label
        from raster_bins rb
        where rb.layer = $1
        order by rb.icat;
        `,
        [variableValue]
      );
    }

    return res.status(200).json({ data });
  } catch (error) {
    debug(error);
    return res.status(500).json({
      message: "Error interno al obtener catálogo",
      error: error.message
    });
  }
};



exports.get_variable_byid = async function get_variable_byid(req, res) {
  try {
    const variable_id = String(req.params.id || "").trim();
    const q = String(verb_utils.getParam(req, "q", "") || "").trim();

    const offset = Number(verb_utils.getParam(req, "offset", 0));
    const limit = Number(verb_utils.getParam(req, "limit", 10));

    if (!dic_wc_select.has(variable_id)) {
      return res.status(400).json({
        message: "variable_id inválido. Valores permitidos: 1, 2, 3"
      });
    }

    if (!Number.isInteger(offset) || offset < 0 || !Number.isInteger(limit) || limit <= 0 || limit > MAX_LIMIT) {
      return res.status(400).json({
        message: `offset/limit inválidos. limit máximo permitido: ${MAX_LIMIT}`
      });
    }

    const whereClauses = [];
    const values = [];
    let p = 1;

    if (q !== "") {
      const filters = q.split(";").map(s => s.trim()).filter(Boolean);

      for (const filter of filters) {
        const pair = filter.split("=");
        if (pair.length !== 2) {
          return res.status(400).json({
            message: `Filtro inválido: "${filter}". Formato esperado: campo=valor`
          });
        }

        const rawKey = pair[0].trim();
        const rawValue = pair[1].trim();

        const canonicalKey = dic_labeltocolumns.get(rawKey);
        if (!canonicalKey || valid_filters.indexOf(canonicalKey) === -1) {
          return res.status(400).json({
            message: `Filtro no válido: "${rawKey}"`
          });
        }

        const dbColumn = dic_wc_db.get(canonicalKey);
        const groupValues = rawValue.split(",").map(v => v.trim()).filter(Boolean);

        if (groupValues.length === 0) {
          return res.status(400).json({
            message: `Filtro sin valores: "${rawKey}"`
          });
        }

        if (canonicalKey === "idlayer") {
          // Buscar tanto por identificador (bio001) como por nombre humano (Annual Mean Temperature)
          const likeParts = groupValues.map(v => {
            values.push(`${v}%`);
            const idPos = p++;
            values.push(`${v}%`);
            const labelPos = p++;
            return `(${dbColumn} ILIKE $${idPos} OR rb."label" ILIKE $${labelPos})`;
          });
          whereClauses.push(`(${likeParts.join(" OR ")})`);
        } else if (canonicalKey === "descripcion") {
          const likeParts = groupValues.map(v => {
            values.push(`${v}%`);
            return `${dbColumn} ILIKE $${p++}`;
          });
          whereClauses.push(`(${likeParts.join(" OR ")})`);
        } else {
          const eqParts = groupValues.map(v => {
            values.push(v);
            return `${dbColumn} = $${p++}`;
          });
          whereClauses.push(`(${eqParts.join(" OR ")})`);
        }
      }
    }

    const selectSql = dic_wc_select.get(variable_id);
    const groupSql = dic_wc_group.get(variable_id);
    const orderSql = dic_wc_order.get(variable_id);

    const whereSql = whereClauses.length ? `WHERE ${whereClauses.join(" AND ")}` : "";

    values.push(limit);
    const limitPos = p++;
    values.push(offset);
    const offsetPos = p++;

    const query = `
      ${selectSql}
      FROM fuentes_bioclimaticas fb
      JOIN raster_bins rb ON fb.id = rb.id_fuentes_bio
      ${whereSql}
      ${groupSql}
      ${orderSql}
      LIMIT $${limitPos}
      OFFSET $${offsetPos}
    `;

    const resp = await pool.any(query, values);

    if (resp.length === 0) {
      return res.status(200).json({ data: [] });
    }

    const response_array = resp.map(item => {
      const temp = {
        id: Number(variable_id),
        level_id: item.level_id,
        data: {
          descripcion: item.descripcion,
          bins: item.bins,
          area: item.area,
          idfuente: item.id_fuentes_bio
        }
      };

      if (variable_id === "2" || variable_id === "3") {
        temp.data.layer = item.layer;
        temp.data.label = item.label;
      }

      if (variable_id === "3") {
        temp.data.tag = item.tag;
        temp.data.icat = item.icat;
      }

      return temp;
    });

    return res.status(200).json({ data: response_array });
  } catch (error) {
    debug(error);
    return res.status(500).json({
      message: "Error interno al obtener datos",
      error: error.message
    });
  }
};




exports.get_data_byid = async function get_data_byid(req, res) {
  debug("get_data_byid");

  const toArray = (v) => {
    if (Array.isArray(v)) return v;
    if (v == null || v === "") return [];
    if (typeof v === "string") return v.split(",").map(s => s.trim()).filter(Boolean);
    return [v];
  };

  const isSafeIdentifier = (s) => /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(String(s || ""));

  try {
    const variable_id = String(req.params.id || "").trim();
    if (!dic_wc_select.has(variable_id)) {
      return res.status(400).json({ message: "variable_id inválido. Valores permitidos: 1,2,3" });
    }

    const grid_id = Number(verb_utils.getParam(req, "grid_id", 1));
    if (!Number.isInteger(grid_id) || grid_id <= 0) {
      return res.status(400).json({ message: "grid_id inválido" });
    }

    const levels_id_raw = toArray(verb_utils.getParam(req, "levels_id", []));
    const levels_id = levels_id_raw
      .map(v => Number(v));

    if (levels_id.length === 0 || levels_id.some(v => !Number.isInteger(v) || v <= 0)) {
      return res.status(400).json({ message: "levels_id debe contener solo enteros positivos." });
    }
    if (levels_id.length > MAX_LEVELS) {
      return res.status(400).json({ message: `levels_id excede el máximo permitido (${MAX_LEVELS}).` });
    }

    const filter_names = toArray(verb_utils.getParam(req, "filter_names", []));
    const filter_values = toArray(verb_utils.getParam(req, "filter_values", []));
    if (filter_names.length !== filter_values.length) {
      return res.status(400).json({ message: "filter_names y filter_values deben tener la misma longitud." });
    }
    if (!filter_names.every(f => typeof f === "string")) {
      return res.status(400).json({ message: "filter_names debe contener solo strings." });
    }

    const selectSql = dic_wc_select.get(variable_id);
    const groupSql = dic_wc_group.get(variable_id);
    const orderSql = dic_wc_order.get(variable_id);

    const whereParts = ["rb.bid = ANY($1::int[])"];
    const params = [levels_id];
    let p = 2;

    for (let i = 0; i < filter_names.length; i++) {
      const fName = String(filter_names[i] || "").trim();
      const fValue = String(filter_values[i] || "").trim();

      const col = dic_wc_db.get(fName);
      if (!fName || valid_filters.indexOf(fName) === -1 || !col) {
        return res.status(400).json({ message: `Filtro no válido: ${fName}` });
      }
      if (fValue === "") {
        return res.status(400).json({ message: `Filtro sin valor: ${fName}` });
      }

      if (fName === "idlayer" || fName === "descripcion") {
        whereParts.push(`${col} ILIKE $${p}`);
        params.push(`${fValue}%`);
      } else {
        whereParts.push(`${col} = $${p}`);
        params.push(fValue);
      }
      p++;
    }

    const queryLevels = `
      ${selectSql}
      FROM fuentes_bioclimaticas fb
      JOIN raster_bins rb ON fb.id = rb.id_fuentes_bio
      WHERE ${whereParts.join(" AND ")}
      ${groupSql}
      ${orderSql}
    `;

    const levelsRows = await pool.any(queryLevels, params);
    if (levelsRows.length === 0) {
      return res.status(404).json({ message: "No se encontraron niveles." });
    }

    const queryBioParts = [];

    for (const item of levelsRows) {
      const meta = {
        descripcion: item.descripcion,
        bins: item.bins,
        area: item.area,
        idfuente: item.id_fuentes_bio
      };

      let polygonResult = null;

      if (variable_id === "1") {
        const fuenteId = Number(item.id_fuentes_bio);
        const q = fuenteId === 1 ? "_q20" : fuenteId === 2 ? "_q10" : null;
        if (!q) {
          queryBioParts.push({ bid: item.id_fuentes_bio, union_geom: null, datos: meta });
          continue;
        }

        const unions = [];
        const unionParams = [];
        let up = 1;

        for (const fuente_bio of fuente_bios) {
          const tableBio = `${fuente_bio}${q}`;
          if (!isSafeIdentifier(tableBio)) continue;

          unions.push(
            `SELECT ST_AsText(ST_SetSRID(ST_Union(the_geom),4326)) AS union_geom FROM ${pgp.as.name(tableBio)}`
          );
        }

        if (unions.length === 0) {
          queryBioParts.push({ bid: item.id_fuentes_bio, union_geom: null, datos: meta });
          continue;
        }

        const qUnion = `
          WITH bios AS (${unions.join(" UNION ALL ")})
          SELECT $1 AS bid, $2::jsonb AS datos, ST_AsText(ST_Union(ST_GeomFromText(union_geom))) AS union_geom
          FROM bios
          WHERE union_geom IS NOT NULL
        `;
        unionParams.push(item.id_fuentes_bio, JSON.stringify(meta));
        polygonResult = await pool.oneOrNone(qUnion, unionParams);
      }

      if (variable_id === "2" || variable_id === "3") {
        const layer = String(item.layer || "").trim();
        const bins = Number(item.bins);
        const tableBio = `${layer}_q${bins}`;

        if (!isSafeIdentifier(tableBio)) {
          queryBioParts.push({ bid: item.level_id, union_geom: null, datos: meta });
          continue;
        }

        if (variable_id === "2") {
          const qPoly = `
            SELECT $1 AS bid,
                   ST_AsText(ST_SetSRID(ST_Union(the_geom),4326)) AS union_geom,
                   $2::jsonb AS datos
            FROM ${pgp.as.name(tableBio)}
            WHERE categoria = $3
          `;
          polygonResult = await pool.oneOrNone(qPoly, [item.level_id, JSON.stringify({ ...meta, layer, label: item.label }), layer]);
        } else {
          const icat = Number(item.icat);
          // Build a human-readable label for the range (rounded to 2 decimals)
          const tagParts = String(item.tag || '').split(':');
          const roundedTag = tagParts.length === 2
            ? `${parseFloat(tagParts[0]).toFixed(2)} : ${parseFloat(tagParts[1]).toFixed(2)}`
            : String(item.tag || '');
          const layerName = String(item.label || '').trim() || layer;
          const rangoLabel = layerName ? `${layerName} [${roundedTag}]` : roundedTag;

          const qPoly = `
            SELECT $1 AS bid,
                   ST_AsText(ST_SetSRID(ST_Union(the_geom),4326)) AS union_geom,
                   $2::jsonb AS datos
            FROM ${pgp.as.name(tableBio)}
            WHERE categoria = $3 AND icat = $4
          `;
          polygonResult = await pool.oneOrNone(qPoly, [
            item.level_id,
            JSON.stringify({ ...meta, layer, tag: item.tag, icat, label: rangoLabel }),
            layer,
            icat
          ]);
        }
      }

      if (!polygonResult || !polygonResult.union_geom) {
        // For Rango items the enriched datos is inside polygonResult.datos (if query ran)
        // Fall back gracefully preserving whatever metadata we have
        const fallbackDatos = (polygonResult && polygonResult.datos)
          ? (typeof polygonResult.datos === 'string' ? JSON.parse(polygonResult.datos) : polygonResult.datos)
          : meta;
        queryBioParts.push({
          bid: item.level_id,
          union_geom: null,
          datos: fallbackDatos
        });
      } else {
        queryBioParts.push(polygonResult);
      }
    }

    const catGrid = await pool_mallas.oneOrNone(
      `SELECT region_id, table_cell_name, table_view_name FROM cat_grid WHERE grid_id = $1`,
      [grid_id]
    );

    if (!catGrid) {
      return res.status(404).json({ message: "No se encontró configuración para grid_id." });
    }

    const tablename = String(catGrid.table_cell_name || "").trim();
    const tableViewName = String(catGrid.table_view_name || "").trim();
    const region_id = catGrid.region_id;

    if (!isSafeIdentifier(tablename) || !isSafeIdentifier(tableViewName)) {
      return res.status(500).json({ message: "Configuración de malla inválida." });
    }

    let columnName = tablename.replace(/grid_/g, "").replace(/_aoi/g, "");
    columnName = `gridid_${columnName}`;
    if (!isSafeIdentifier(columnName)) {
      return res.status(500).json({ message: "Columna de malla inválida." });
    }

    const response_array = [];

    for (const polygon of queryBioParts) {
      if (!polygon.union_geom) {
        response_array.push({
          id: variable_id,
          grid_id,
          level_id: polygon.bid,
          cells: [],
          n: 0,
          metadata: polygon.datos
        });
        continue;
      }

      const qIntersect = `
        WITH regionarea AS (
          SELECT g.${pgp.as.name(columnName)} AS cell, g.the_geom
          FROM ${pgp.as.name(tablename)} g
          JOIN ${pgp.as.name(tableViewName)} vg ON ST_Intersects(g.the_geom, vg.border)
          WHERE vg.region_id = $1
        ),
        intersectCells AS (
          SELECT DISTINCT $2 AS bid, g.cell
          FROM regionarea g
          JOIN (SELECT ST_SetSRID(ST_GeomFromText($3), 4326) AS geom) p
            ON ST_Intersects(g.the_geom, p.geom)
        )
        SELECT bid, array_agg(cell) AS cells
        FROM intersectCells
        GROUP BY bid
      `;

      const inter = await pool_mallas.oneOrNone(qIntersect, [region_id, polygon.bid, polygon.union_geom]);

      response_array.push({
        id: variable_id,
        grid_id,
        level_id: polygon.bid,
        cells: inter?.cells || [],
        n: inter?.cells?.length || 0,
        metadata: polygon.datos
      });
    }

    return res.status(200).json(response_array);
  } catch (error) {
    debug(error);
    return res.status(500).json({
      error: "Error al procesar la solicitud.",
      message: error.message
    });
  }
};
