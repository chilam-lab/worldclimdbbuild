DROP TABLE IF EXISTS aoi;

CREATE TABLE aoi (
	aoi_id serial4 NOT NULL,
	fgid int4 NULL,
	cve_iso varchar(3) NULL,
	country varchar(200) NULL,
	continent varchar(200) NULL,
	geom public.geometry(multipolygon, 4326) NULL
);