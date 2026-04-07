INSERT INTO data_source_info (name, description, source_url, download_url, dict_url)
VALUES (
  'SNIB Data Source',
  'Esta fuente de datos contiene la información de los datos del Sistema Nacional de Información sobre Biodiversidad de México',
  'https://www.snib.mx/',
  'https://www.snib.mx/ejemplares/descarga/',
  'https://www.snib.mx/ejemplares/docs/CONABIO-SNIB-DiccionarioDatosEstandar202412.pdf'
)
ON CONFLICT (name) DO UPDATE SET
  description = EXCLUDED.description,
  source_url = EXCLUDED.source_url,
  download_url = EXCLUDED.download_url,
  dict_url = EXCLUDED.dict_url,
  updated_at = now();
