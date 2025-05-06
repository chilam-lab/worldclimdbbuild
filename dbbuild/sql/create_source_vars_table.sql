-- DROP TABLE IF EXISTS fuentes_bioclimaticas;

CREATE TABLE IF NOT EXISTS fuentes_bioclimaticas (
	id serial, 
	fuente varchar(100) NOT NULL, 
	area varchar(100) NULL,
	bins varchar(50) NULL,
	descripcion varchar(400) NULL,
	level_size int4 NULL,
	available_grids INTEGER[] NULL,
	filter_fields jsonb NULL
);

CREATE INDEX IF NOT EXISTS idx_id_fuentes_bioclimaticas ON fuentes_bioclimaticas(id);
-- CREATE INDEX IF NOT EXISTS idx_fuente_fuentes_bioclimaticas ON fuentes_bioclimaticas(fuente);