# Repositorio para la creación de la fuente de datos de Wordlclim (10m) y middleware la entrega de información.

> Rev. 1.0

## Resumen

Este proyecto automatiza el procesamiento y transformación de datos climáticos provenientes de [WorldClim](https://www.worldclim.org/data/index.html), convirtiéndolos en una nueva fuente de datos bajo la nueva estructura de SPECIES y proyectos relacionados. Además, contiene una capa de servicios que disponibilizan la información generada.

Los scripts para la generación de la base de datos, se encuentran en el directorio dbbuild y contemplan el procesamiento de las 19 capas raster de variables bioclimaticas del promedio de los años 1970 al 2000 en formato GeoTiff (.tiff). Como resultado se obtiene una base de datos georeferenciada de cada capa con la división que sea configurada en el proyecto (Bins).

El proyecto de servicios, se encuentra dentro de la carpeta worldclimmiddleware, este proyecto esta desarrollado en Node JS con Express. El proyecto despliega los serivicios de bienvenida, el catalogo de fuentes disponibles, servicio de visualización de metadatos y el servicio de envio de celdas sobre la fuente solicitada. La entrega de información esta bajo la especificación: [Propuesta de arquitectura](https://github.com/CONABIO/species_v3.0)


## Proyecto dbbuild

### Información requerida para la creación de esta fuente de datos

Para la generación de esta fuente de datos se debe contar con las 19 capas raster de las variables Bioclimaticas descargables en el enlace de la sección de resumen. Estas capas deben estar dentro del dicrectorio data/input.

Dentro de la carpeta de data, se requiere crear el archivo `sources.csv` Este archivo debe contener las siguientes columnas: 1. La ruta relativa del archivo a este directorio, 2. El nombre de la capa raster, 3. La fuente de datos, y 4. La descripción breve de la fuente de datos. Se agrega un ejemplo de archivo.

Dentro del script debemos definir el valor de la variable `default_nbins`, este parámetro es para seleccionar el número de bins al cual queremos dividir nuestras capas raster. Por default el valro es 10 bins.

Dentro del script debemos definir el valor de la variable `aoi_value`, este parámetro es para delimitar o recortar el archivos raster que viene de forma global. Por default, se en cuentra delimitado por contientes, y asignado el valor para America. Si se desea delimitar por otro tipo de región, se debe modificar el archivo que se encuentra en /sql/get_aoi.sql.

### Datos resultantes de la ejecución de scripts del proyecto dbbuild

Las tablas que son creadas por estos scripts se componen de la siguiente manera:

- Tabla del area de interes para crear el shape que delimita las tablas que seran generadas a partir de los rstarers.
- Tablas que contienen el proceso de conversion de raster a vector, con la geometria y valor de cada área.
- Tabla catálogo de las fuentes de datos generadas a los diferentes bins.
- Tabla de detalle de cada capa por cada una de las 19 divisiones.


## Proyecto worldclimmiddleware

Proyecto que implementa la capa de servicios web (API REST) que expone la información procesada para su consumo de WorldClim, variables bioclimáticas que describen patrones climáticos históricos.

### Objetivo

Exponer los datos climáticos procesados mediante una **API REST**, siguiendo el estándar de SPECIES v3.0, permitiendo su integración con:

- Análisis de nicho ecológico
- Cruce con ocurrencias biológicas
- Visualización geoespacial

---

## Arquitectura general

```
worldclim/
├── dbbuild/                 # Construcción de la base de datos
├── worldclimmiddleware/     # API REST (Node.js + Express)
│   └── src/
│       ├── controllers/
│       │   └── wc_controller.js
│       ├── routes/
│       │   └── worldclimrouter.js
│       └── server.js
├── README.md
```

---

### Tecnologías

- Node.js
- Express
- PostgreSQL / PostGIS
- Arquitectura MVC

## Rutas del API

### Ruta base

```
GET /
```
Respuesta de bienvenida al API WorldClim.

### Variables disponibles

```
GET /variables
POST /variables
```
Devuelve el catálogo de variables climáticas disponibles.

### Variable por ID

```
GET /variables/:id
POST /variables/:id
```
Obtiene metadatos de una variable específica.

### Datos climáticos por variable

```
GET /get-data/:id
POST /get-data/:id
```
Entrega las celdas y valores asociados a la variable solicitada.

---

## Estándar de interoperabilidad

Este proyecto sigue la especificación definida en:

🔗 https://github.com/CONABIO/species_v3.0

Esto garantiza que la fuente WorldClim pueda combinarse con otras fuentes como:

- SNIB
- GBIF
- WorldClim
- Otras fuentes compatibles

---

## Casos de uso

- Modelado de nicho ecológico
- Análisis de correlación clima–especie
- Visualización de capas climáticas discretizadas
- Integración con plataformas SPECIES

---

## Licencia

Este proyecto se distribuye bajo la licencia definida en el archivo `LICENSE` del repositorio.

---

## Créditos

- Datos climáticos: **WorldClim**
- Arquitectura y estándar: **SPECIES v3.0**
- Implementación: CONABIO / Chilam Lab

