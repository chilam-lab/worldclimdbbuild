-- DROP TABLE IF EXISTS raster_bins;

CREATE TABLE IF NOT EXISTS raster_bins (
  bid serial,
  tag character varying,
  layer character varying,
  icat integer,
  label character varying,
  id_fuentes_bio integer,
  coeficiente float8 NULL DEFAULT 1.0,
  unidad varchar(20) NULL
) WITH (OIDS=FALSE);

-- SOLO EJECITAR CUANDO SEA LA PRIMERA VEZ
-- ALTER sequence raster_bins_bid_seq restart WITH 300000;
-- UPDATE raster_bins SET bid = nextval('raster_bins_bid_seq');


