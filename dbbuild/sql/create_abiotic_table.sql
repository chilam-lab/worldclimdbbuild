-- DROP TABLE IF EXISTS raster_bins;

CREATE TABLE IF NOT EXISTS raster_bins (
  bid serial,
  tag character varying,
  layer character varying,
  icat integer,
  label character varying,
  id_fuentes_bio integer,
  coeficiente float8 NULL DEFAULT 1.0,
  unidad varchar(20) NULL,
  UNIQUE (tag, layer)
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM raster_bins LIMIT 1) THEN
    ALTER SEQUENCE raster_bins_bid_seq RESTART WITH 300000;
  END IF;
END $$;


