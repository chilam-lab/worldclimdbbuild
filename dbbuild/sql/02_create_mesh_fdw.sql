CREATE EXTENSION IF NOT EXISTS postgres_fdw;

DROP SERVER IF EXISTS wc_mesh_server CASCADE;

CREATE SERVER wc_mesh_server
FOREIGN DATA WRAPPER postgres_fdw
OPTIONS (
  host '__MESHDB_HOST__',
  port '__MESHDB_PORT__',
  dbname '__MESHDB_NAME__'
);

CREATE SCHEMA IF NOT EXISTS wc_mesh_fdw;

DROP USER MAPPING IF EXISTS FOR CURRENT_USER SERVER wc_mesh_server;

CREATE USER MAPPING FOR CURRENT_USER
SERVER wc_mesh_server
OPTIONS (
  user '__MESHDB_USER__',
  password '__MESHDB_PASS__'
);

IMPORT FOREIGN SCHEMA public
LIMIT TO (
  cat_grid,
  grid_geojson_64km_aoi,
  grid_geojson_32km_aoi,
  grid_geojson_16km_aoi,
  grid_geojson_8km_aoi,
  grid_geojson_state_aoi,
  grid_geojson_mun_aoi,
  grid_geojson_ageb_aoi,
  grid_geojson_cue_aoi
)
FROM SERVER wc_mesh_server
INTO wc_mesh_fdw;
