INSERT INTO fuentes_bioclimaticas(fuente, bins, area, descripcion, available_grids, filter_fields) VALUES('{source}', '{bins}', '{area}', '{description}', {available_grids},'{filter_fields}')
ON CONFLICT (fuente, area, bins) DO UPDATE SET descripcion = EXCLUDED.descripcion
RETURNING id