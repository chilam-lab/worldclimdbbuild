INSERT INTO data_source_info (name, description, source_url, download_url, dict_url)
VALUES (
  'WorldClim 2.1 Historical Climate Data',
  'Fuente de datos climáticos históricos WorldClim version 2.1 para 1970-2000; incluye variables mensuales y 19 variables bioclimáticas en formato GeoTIFF.',
  'https://www.worldclim.org/data/worldclim21.html',
  'https://www.worldclim.org/data/worldclim21.html',
  'https://www.worldclim.org/data/bioclim.html'
)
ON CONFLICT (name) DO UPDATE SET
  description = EXCLUDED.description,
  source_url = EXCLUDED.source_url,
  download_url = EXCLUDED.download_url,
  dict_url = EXCLUDED.dict_url,
  updated_at = now();
