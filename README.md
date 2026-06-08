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

### Variables de entorno para dbbuild

El script `dbbuild/build_worldclim.py` lee variables desde `dbbuild/.env`. Para configurar una ejecución nueva, usar `dbbuild/.env.example` como plantilla.

```env
DBNICHENAME=worldclim_data
DBNICHEHOST=
DBNICHEPORT=5432
DBNICHEUSER=
DBNICHEPASSWD=

DBMESHNAME=meshandregions_db
DBMESHHOST=
DBMESHPORT=5432
DBMESHUSER=
DBMESHPASSWD=
```

Las variables `DBMESH*` se usan para crear un FDW temporal hacia `meshandregions_db` y calcular `available_grids` con base en la intersección espacial entre las capas `bioXXX_qN` y las mallas disponibles. Si estas variables no están definidas, el build continúa y omite el cálculo de `available_grids`.

### Datos resultantes de la ejecución de scripts del proyecto dbbuild

Las tablas que son creadas por estos scripts se componen de la siguiente manera:

- Tabla del area de interes para crear el shape que delimita las tablas que seran generadas a partir de los rstarers.
- Tablas que contienen el proceso de conversion de raster a vector, con la geometria y valor de cada área.
- Tabla catálogo de las fuentes de datos generadas a los diferentes bins.
- Tabla de detalle de cada capa por cada una de las 19 divisiones.
- Metadatos de mallas disponibles en `fuentes_bioclimaticas.available_grids`.

### Metadatos de la fuente

El archivo `dbbuild/sql/seed_wc_data_source_worldclim.sql` registra la fuente oficial WorldClim 2.1 Historical Climate Data:

- Fuente y descarga: `https://www.worldclim.org/data/worldclim21.html`
- Diccionario de variables bioclimáticas: `https://www.worldclim.org/data/bioclim.html`


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

### Configuración

El middleware lee variables de entorno desde `worldclimmiddleware/.env`. Para configurar una instalación nueva, usar `worldclimmiddleware/.env.example` como plantilla.

Variables principales:

```env
PORT=8080
DBHOST=
DBPORT=5432
DBNAME=worldclim_data
DBUSER=
DBPWD=
DBHOST_MALLAS=
DBPORT_MALLAS=5432
DBNAME_MALLAS=meshandregions_db
DBUSER_MALLAS=
DBPWD_MALLAS=
DB_CONNECTION_TIMEOUT_MS=5000
DB_IDLE_TIMEOUT_MS=30000
DB_QUERY_TIMEOUT_MS=60000
DB_STATEMENT_TIMEOUT_MS=60000
```

Las variables de timeout también están expuestas en `docker-compose.yml` para despliegues con Docker o Portainer.

## Rutas del API

Todas las rutas del middleware se publican bajo el prefijo `/wc`.

### Ruta base

```
GET /wc/
```
Respuesta de bienvenida al API WorldClim.

### Salud de base de datos

```
GET /wc/db-health
POST /wc/db-health
```

Valida la conexión PostgreSQL principal del middleware. Responde `status: "UP"` cuando la base está disponible y `status: "DOWN"` cuando no se puede conectar.

### Información de la fuente

```
GET /wc/info
POST /wc/info
```

Devuelve los metadatos de la fuente WorldClim registrados en `data_source_info`.

### Variables disponibles

```
GET /wc/variables
POST /wc/variables
```
Devuelve el catálogo de variables climáticas disponibles.

### Variable por ID

```
GET /wc/variables/:id
POST /wc/variables/:id
```
Obtiene metadatos de una variable específica.

Parámetros opcionales:

- `offset`: entero mayor o igual a `0`.
- `limit`: entero entre `1` y `500`.
- `q`: filtros separados por `;`, usando campos como `idfuente`, `idlayer`, `idrange` o `descripcion`.

### Datos climáticos por variable

```
GET /wc/get-data/:id
POST /wc/get-data/:id
```
Entrega las celdas y valores asociados a la variable solicitada.

Parámetros principales:

- `grid_id`: entero positivo.
- `levels_id`: arreglo o lista de enteros positivos; máximo `500` niveles por solicitud.
- `filter_names` y `filter_values`: arreglos del mismo tamaño. Los filtros permitidos son `idfuente`, `idlayer`, `idrange` y `descripcion`.

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
