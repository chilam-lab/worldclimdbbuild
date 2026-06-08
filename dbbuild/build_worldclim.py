#!/usr/bin/env python
import os
import time
import sys
import csv
import psycopg2
import subprocess
import argparse
import glob
from osgeo import gdal
from shutil import copyfile
from aux_functions import *
from pathlib import Path

from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv, dotenv_values

create_extensions       = './sql/create_extensions.sql'
create_aoi_table    = './sql/create_aoi_table.sql'
geom_aoi_data       = './sql/geom_aoi.sql'
get_aoi        = './sql/get_aoi.sql'

sources_file         = './data/sources.csv'
shapefile_name = './data/aoi_extent.shp'

data_folder          = './data/'
input_folder        = './data/input/'
output_folder        = './data/output/'
output_shape_folder        = './data/output/shapes/'

create_sources_table = './sql/create_source_vars_table.sql'
create_abiotic_table = './sql/create_abiotic_table.sql'
copy_tags            = './sql/copy_tags.sql'
calculos_abio        = './sql/calculos_abio.sql'
# create_grid_indexes  = './sql/create_grid_indexes.sql'
# insert_info_grid     = './sql/insert_info_grid.sql'
bioclim_vars_info    = './sql/bioclim_vars_info.sql'
update_label_var     = './sql/update_label_var.sql'
create_wc_data_source = './sql/create_wc_data_source.sql'
seed_wc_data_source_worldclim = './sql/seed_wc_data_source_worldclim.sql'
create_mesh_fdw = './sql/02_create_mesh_fdw.sql'
update_available_grids = './sql/03_update_available_grids.sql'

logger = setup_logger()
load_dotenv() 

def env_first(*names):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None

DBNICHENAME=os.getenv("DBNICHENAME")
DBNICHEHOST=os.getenv("DBNICHEHOST")
DBNICHEPORT=os.getenv("DBNICHEPORT")
DBNICHEUSER=os.getenv("DBNICHEUSER")
DBNICHEPASSWD=os.getenv("DBNICHEPASSWD")

DBMESHNAME=env_first("DBMESHNAME", "DBNAME_MALLAS")
DBMESHHOST=env_first("DBMESHHOST", "DBHOST_MALLAS")
DBMESHPORT=env_first("DBMESHPORT", "DBPORT_MALLAS")
DBMESHUSER=env_first("DBMESHUSER", "DBUSER_MALLAS")
DBMESHPASSWD=env_first("DBMESHPASSWD", "DBPWD_MALLAS")

os.chdir(output_folder)

# layers_sqls = glob.glob('bio*.sql')
layers_tags = glob.glob('bio*.tags')

os.chdir('../../')

# valor para delimitar el área del raster, así como delimiar los valores de cobertura con los que se calculan los rangos (bins)
aoi_value = "Americas"

# numero de rangos (bins) en los que se dividen los valores de la cobertura del raster
default_nbins = '10'

# id insertado en el catalogo de variables worldclim
id_catalogo = 0


# # Obteniendo variables de ambiente
# try:
    
#     logger.info('lectura de USUARIO: {0} en el HOST: {1}, BASE: {2} y PUERTO: {3}'.format(DBNICHEUSER, DBNICHEHOST, DBNICHENAME, DBNICHEPORT))
# except Exception as e:
#     logger.error('No se pudieron obtener las variables de entorno requeridas : {0}'.format(str(e)))
#     sys.exit()


# Creando tabla aoi (area de interes) contempla todos los países con la columna de continente por continente
try:

    logger.info('Instalando extensiones y Creando tabla aoi a nivel mundial')
    create_extensions_sql = get_sql(create_extensions) 
    create_aoi_table_sql = get_sql(create_aoi_table) 
    geom_aoi_data_sql = get_sql(geom_aoi_data) 

    conn = psycopg2.connect('dbname={0} host={1} port={2} user={3} password={4}'.format(DBNICHENAME, DBNICHEHOST, DBNICHEPORT, DBNICHEUSER, DBNICHEPASSWD))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    cur.execute(create_extensions_sql)
    logger.info('create_extensions_sql')

    cur.execute(create_aoi_table_sql)
    logger.info('create_aoi_table_sql')

    cur.execute(geom_aoi_data_sql)
    logger.info('geom_aoi_data_sql')

    logger.info('Termina creacion de tabla aoi con datos mundiales')

    cur.close()
    conn.close()

except Exception as e:
    logger.error('No se pudo instalar las extensiones necesarias o crear y llenar la tabla aoi a nivel mundial: {0}'.format(str(e)))
    sys.exit()


# Creación de tabla de fuente de datos y registro base
try:

    logger.info('Creación de tabla data_source_info y carga de registro base')

    create_wc_data_source_sql = get_sql(create_wc_data_source)
    seed_wc_data_source_worldclim_sql = get_sql(seed_wc_data_source_worldclim)

    conn = psycopg2.connect('dbname={0} host={1} port={2} user={3} password={4}'.format(DBNICHENAME, DBNICHEHOST, DBNICHEPORT, DBNICHEUSER, DBNICHEPASSWD))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    cur.execute(create_wc_data_source_sql)
    logger.info('create_wc_data_source_sql')

    cur.execute(seed_wc_data_source_worldclim_sql)
    logger.info('seed_wc_data_source_worldclim_sql')

    cur.close()
    conn.close()

except Exception as e:
    logger.error('No se pudo crear/cargar la tabla data_source_info: {0}'.format(str(e)))
    sys.exit()



# Preprocesamiento de datos raster. Generación de shapefile y uso para recorte del raster de worldclim
# Si se desea un area diferente editar el archivo que guarda la variable get_aoi. Por default esta por continente y valor America
try:
    logger.info('Obteniendo geometrias de la DB {0}'.format(DBNICHENAME))
    sources = get_sql(sources_file).splitlines()
    get_aoi_sql = get_sql(get_aoi)
    get_aoi_sql = get_aoi_sql.format(aoi_value)
    
    # logger.info('get_aoi_sql: ' + get_aoi_sql)


    # este comando genera un shapefile <shapefile_name> con base a la consulta generada 
    # en la tabla aoi en su defecto lo que venga en el archivo <get_aoi_sql> 
    # en la proyección EPSG:4326
    args = [ 'ogr2ogr', '-f', 'ESRI Shapefile', shapefile_name, 
           'PG:dbname={0} host={1} port={2} user={3} password={4}'.format(DBNICHENAME, DBNICHEHOST, DBNICHEPORT, DBNICHEUSER, DBNICHEPASSWD),
           '-s_srs', 'EPSG:4326', '-t_srs', 'EPSG:4326',
           '-sql', get_aoi_sql]
    
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    logger.info('ogr2ogr: {0}'.format(p.communicate()[0]))

    # mover indice al numero de variables existentes
    number_var = 1
    for source in sources:
        info = source.split(',')
        
        raster_name = '{0}{1}'.format(input_folder, info[0])
        logger.info('raster_name: ' + raster_name)

        final_name = '{0}{1}_{2}_final.tif'.format(output_folder, get_basename(info[0]), get_three_digits_number_var(number_var))
        logger.info('final_name: ' + final_name)

        
        logger.info('Cortando raster: {0} usando shapefile: {1}'.format(raster_name, shapefile_name))
        src_ds = gdal.Open(raster_name)
        src_band = src_ds.GetRasterBand(1)
        nodata = src_band.GetNoDataValue()
        src_ds = None
        src_band = None 

        # este comando solcita un raster de entrada que sera cortado o delimitado 
        # por la entrada del shapefile <shapefile_name> y entregara como salida 
        # un raster recortado <final_name>
        args = ['gdalwarp', '-overwrite', '-s_srs', 'EPSG:4326', '-srcnodata', str(nodata), 
                '-dstnodata', str(nodata), '-crop_to_cutline', '-cutline', shapefile_name,
                raster_name,  final_name]

        p = subprocess.Popen(args, stdout=subprocess.PIPE)
        logger.info('gdalwarp: {0}'.format(p.communicate()[0]))
        number_var += 1

except Exception as e:
    logger.error('No se pudieron obtener las geometrias: {0}'.format(str(e)))
    sys.exit()



# Creación de tablas catálogo

# se definen variables para la divsión de bins para esta y la siguiente sección
parser = argparse.ArgumentParser()
parser.add_argument('-nbins', '--number-bins', default=default_nbins, help='Numero de bins en los que se discretizaran los rasters')
args = parser.parse_args()

# Obteniendo el numero de bins
nbins = args.number_bins
logger.info('nbins: {0}'.format(nbins))

try:

    logger.info('Creación de tablas catalogo en DB: {0}'.format(DBNICHENAME))

    create_cource_vars_table_sql =  get_sql(create_sources_table) # crea tabla fuentes_bioclimaticas
    create_abiotic_table_sql = get_sql(create_abiotic_table) # crea tabla raster_bins
    bioclim_vars_info_sql = get_sql(bioclim_vars_info) # inserción del catalogo
    
    conn = psycopg2.connect('dbname={0} host={1} port={2} user={3} password={4}'.format(DBNICHENAME, DBNICHEHOST, DBNICHEPORT, DBNICHEUSER, DBNICHEPASSWD))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    cur.execute(create_cource_vars_table_sql)
    logger.info('create_cource_vars_table_sql')

    cur.execute(create_abiotic_table_sql)
    logger.info('create_abiotic_table_sql')

    with open(sources_file, 'r') as f:
        reader = csv.reader(f)
        for line in reader:
                source = line[2]
                description = line[3]

    # poner la lista de gridids existentes
    available_grids = "ARRAY[]::integer[]"
    # available_grids = "ARRAY[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]"
    filter_fields = '{"area": "string", "bins": "integer", "categoria": "string"}'
            
    cur.execute(bioclim_vars_info_sql.format(source=source, bins="{}".format(default_nbins), area="{}".format(aoi_value), description=description, available_grids=available_grids, filter_fields="{}".format(filter_fields) ))
    id_catalogo = cur.fetchone()[0]
    logger.info('id_catalogo: {}'.format(id_catalogo))

    cur.close()
    conn.close()

except Exception as e:
    logger.error('No se pudo crear la tabla de fuentes climaticas y/o raster bins: {}'.format(str(e)))
    sys.exit()





# discretización de raster en un número definido de bins 
# Generación de un raster discretizado con el número de bins de entrada configurado. Además genera los rangos (tags) donde se divide cada bin
# Se comenta código que genera la tabla de base de datos que contine la conversion de raster a sql. (No necesaria)
# Se agregan scripts necesarios para la creación de tablas de poligonos (vectorizados)
logger.info('Inicio de proceso de discretización de raster en bins')

os.chdir(output_folder)
final_names = glob.glob('*_final.tif')

os.chdir('../../')

sources = get_sql(sources_file).splitlines()

try:
    number_var = 1
    for source in sources:
        info = source.split(',')
        innecesarios = []
        
        raster_name = '{0}{1}'.format(input_folder, info[0])
        logger.info('raster_name: ' + raster_name)

        final_name = '{0}_{1}_final.tif'.format(get_basename(info[0]), get_three_digits_number_var(number_var))
        logger.info('final_name: ' + final_name)        
        
        bio_var_name = '{0}bio{1}_final.tif'.format(output_folder, get_three_digits_number_var(number_var))
        logger.info('bio_var_name: ' + bio_var_name)
        innecesarios.append(bio_var_name)

        outfile = '{0}bio{1}_final_q{2}.tif'.format(output_folder, get_three_digits_number_var(number_var), nbins)
        logger.info('outfile: {0}'.format(outfile))
        innecesarios.append(outfile)

        tags = '{0}bio{1}_final_q{2}.tags'.format(output_folder, get_three_digits_number_var(number_var), nbins)
        logger.info('tags: {0}'.format(tags))

        # archivos para vectorización de rasters y guardado en DB
        final_namex100 = '{0}bio{1}_finalx100.tif'.format(output_folder, get_three_digits_number_var(number_var))
        logger.info('final_namex100: ' + final_namex100)
        innecesarios.append(final_namex100)


        final_shape = '{0}bio{1}_final.shp'.format(output_shape_folder, get_three_digits_number_var(number_var))
        logger.info('final_shape: ' + final_shape)
        innecesarios.append(final_shape)

        final_shape_name = 'bio{0}_final'.format(get_three_digits_number_var(number_var))
        logger.info('final_shape_name: ' + final_shape_name)

        final_table_name = 'bio{0}_q{1}'.format(get_three_digits_number_var(number_var), nbins)
        logger.info('final_table_name: ' + final_table_name)

        final_shape_decimal = '{0}bio{1}_final_decimal.shp'.format(output_shape_folder, get_three_digits_number_var(number_var))
        logger.info('final_shape_decimal: ' + final_shape_decimal)
        # innecesarios.append(final_shape_decimal)

        

        if final_name in final_names:
            copyfile('{0}{1}'.format(output_folder, final_name), bio_var_name)
        else:
            copyfile(raster_name, bio_var_name)

        logger.info('Preparando capa {0}'.format(get_three_digits_number_var(number_var)))


        # Discretizando variable
        args = ['python3', './abiotic/reclassify_raster.py', '-t', '-n', str(nbins), '-srcfile', bio_var_name,
                        '-o', outfile, '-realfile', output_folder + final_name]

        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            logger.error('Error al reclasificar raster: {}'.format(stderr.decode('utf-8')))
            raise RuntimeError('Falló reclassify_raster.py para {}'.format(bio_var_name))

        if stdout:
            logger.info('reclassify_raster.py: {}'.format(stdout.decode('utf-8')))

        if not os.path.exists(tags):
            raise RuntimeError('No se generó archivo de etiquetas: {}'.format(tags))
        
        tags_file = open(tags, 'r')
        tags_file = tags_file.read().splitlines()

        with open(tags, 'w') as f:
            f.write('tag,icat,layer\n')

        with open(tags, 'a') as f:
            for line in tags_file[1:]:
                f.write('{0},{1}\n'.format(line, 'bio{0}'.format(get_three_digits_number_var(number_var))))
        
        # proceso para crear archivo y division de rangos 
        copy_tags_sql = get_sql(copy_tags)

        # se abre conexión para inserción en tabla raster bins
        conn = psycopg2.connect('dbname={0} host={1} port={2} user={3} password={4}'.format(DBNICHENAME, DBNICHEHOST, DBNICHEPORT, DBNICHEUSER, DBNICHEPASSWD))
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        contador = 0
        with open(tags, 'r') as f:
            reader = csv.reader(f)
            contador = sum(1 for _ in reader)
            f.seek(0)
        logger.info('contador: {}'.format(contador))

        contador = contador-1

	    # for tags in layers_tags:
        with open(tags, 'r') as f:
            reader = csv.reader(f)
            next(reader)

            ifelse_query_layer = "CASE "

            for indice, line in enumerate(reader):
                tag = line[0]
                icat = line[1]
                layer = line[2]
                # inserta en catalogo raster bins
                cur.execute(copy_tags_sql.format(tag=tag, icat=icat, layer=layer))

                minval = tag.split(":")[0]
                maxval = tag.split(":")[1]
                
                if contador-1 > indice:
                      ifelse_query_layer = ifelse_query_layer + " WHEN (DN / 100.0) BETWEEN " + minval + " AND " + maxval + " THEN '" + layer + "' "
                else:
                      ifelse_query_layer = ifelse_query_layer + " ELSE '" + layer + "' "

            ifelse_query_layer = ifelse_query_layer + " END AS categoria, "
            f.seek(0)

        with open(tags, 'r') as f:
            reader = csv.reader(f)
            next(reader)
            
            ifelse_query_icat = "CASE "

            # TODO: agregar la división para el icat
            for indice, line in enumerate(reader):
                tag = line[0]
                icat = line[1]
                minval = tag.split(":")[0]
                maxval = tag.split(":")[1]
                
                if contador-1 > indice:
                    ifelse_query_icat = ifelse_query_icat + " WHEN (DN / 100.0) BETWEEN " + minval + " AND " + maxval + " THEN " + icat + " "
                else:
                    ifelse_query_icat = ifelse_query_icat + " ELSE " + icat + " "

            ifelse_query_icat = ifelse_query_icat + " END AS icat "

        logger.info('Se insertan etiquetas (rangos)')
        logger.info('ifelse_query_layer: {}'.format(ifelse_query_layer))
        logger.info('ifelse_query_icat: {}'.format(ifelse_query_icat))

        cur.close()
        conn.close()


        # ********* Inicia proceso de vectorización *********
        # 1. multiplicar raster final por 100
        # 2. realizar vectorización (conversión a shape)
        # 3. division de shape entre 100 para tener valores reales decimales
        # 4. guardado en base de datos
        # 5. borrado de archivos innecesarios

        # paso 1. multiplicación de raster final por 100
        args = ['gdal_calc.py', '-A', output_folder + final_name,  # Raster de entrada
            '--outfile={0}'.format(final_namex100),  # Nombre del archivo de salida
            '--calc="A*100"',  # La expresión para multiplicar cada valor por 100
            '--NoDataValue=0',  # Valor NoData (ajusta según tu necesidad)
            '--type=Float32',  # Tipo de datos para el raster de salida
            '--overwrite']  # Sobreescribir si el archivo ya existe
             

        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()

        if p.returncode != 0:
              logger.error('Error al convertir valor raster x100: {}'.format(stderr.decode('utf-8')))
              raise RuntimeError('Falló gdal_calc.py para {}'.format(final_namex100))
        else:
             logger.info('Multiplicación x100 completada. Archivo de salida: {}'.format(final_namex100))


        # paso 2. Vectorización del raster
        args = ['gdal_polygonize.py', final_namex100, 
        		'-f', 'ESRI Shapefile', final_shape, 
		        '-b', '1'] # Banda del raster que se va a usar

        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()

        if p.returncode != 0:
             logger.error('Error al vectorizar el raster: {}'.format(stderr.decode('utf-8')))
             raise RuntimeError('Falló gdal_polygonize.py para {}'.format(final_shape))
        else:
             logger.info('Vectorización completada. Archivo de salida: {}'.format(final_shape))
        

        # paso 3. División shape entre 100 (Se realiza un recorte para quitar datos fuera de las celdas y se enlazan valores de icat y layer)
        query_shape = 'SELECT *, ' + nbins + ' as nbins, (DN / 100.0) AS value, ' + ifelse_query_layer +  ifelse_query_icat +' FROM ' + final_shape_name + ' WHERE DN < 1000000 and DN > -1000000'
        logger.info('query_shape: {}'.format(query_shape))

        args = ['ogr2ogr', '-f', 'ESRI Shapefile',  # Formato de salida
			    final_shape_decimal,  # Nombre del archivo de salida
			    final_shape,  # Archivo de entrada
			    '-dialect', 'SQLite',
			    '-sql', query_shape ] # Consulta SQL

        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()

        if p.returncode != 0:
             logger.error('Error al dividir Shapefile: {}'.format(stderr.decode('utf-8')))
             raise RuntimeError('Falló ogr2ogr al dividir Shapefile para {}'.format(final_shape_decimal))
        else:
             logger.info('División completada. Archivo de salida: {}'.format(final_shape_decimal))


        # paso 4. Guardado en base de datos
        args = [ 'ogr2ogr', '-f', 'PostgreSQL',
           'PG:dbname={0} host={1} port={2} user={3} password={4}'.format(DBNICHENAME, DBNICHEHOST, DBNICHEPORT, DBNICHEUSER, DBNICHEPASSWD),
           final_shape_decimal,
           "-nln", final_table_name,  # Nombre de la tabla de destino
		    "-overwrite",  # Sobrescribe la tabla si ya existe
		    "-lco", "GEOMETRY_NAME=the_geom",  # Nombre de la columna de geometría
		    "-lco", "FID=id",  # Nombre de la columna ID
		    "-lco", "PRECISION=NO"]  # No restringe precisión en campos numéricos

        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()

        if p.returncode != 0:
             logger.error('Error al guardar Shapefile en DB: {}'.format(stderr.decode('utf-8')))
             raise RuntimeError('Falló ogr2ogr al guardar tabla {}'.format(final_table_name))
        else:
             logger.info('Guardado completado. Tabla de salida: {}'.format(final_table_name))


        # paso 5. Removiendo archivos inecesarios
        innecesarios.append(output_shape_folder+"out.shp")
        for file_inn in innecesarios:
             if os.path.exists(file_inn):
                os.remove(file_inn)
                logger.info("Archivo {} eliminado.".format(file_inn))
                logger.info("extension: {}".format(Path(file_inn).suffix))

                if Path(file_inn).suffix == ".shp":
                    shpfile_name = os.path.splitext(file_inn)[0]
                    logger.info('shpfile_name: {}'.format(shpfile_name))

                    for othr_ext in ['.dbf','.prj','.shx']:
                        sidecar_file = shpfile_name + othr_ext
                        if os.path.exists(sidecar_file):
                            os.remove(sidecar_file)
                            logger.info("Archivo '{}' eliminado.".format(sidecar_file))
                        else:
                            logger.info("El archivo '{}' no existe.".format(sidecar_file))
             else:
                  logger.info("El archivo '{}' no existe.".format(file_inn))

        number_var += 1

except Exception as e:
    logger.error('Error al obtener archivos a discretizar: {0}'.format(str(e)))
    sys.exit()


# Se insertan metadatos de las variables abioticas
try:

    logger.info('Se insertan metadatos de las variables abioticas')

    bioclim_vars_info_sql = get_sql(bioclim_vars_info)
    update_label_var_sql = get_sql(update_label_var)

    conn = psycopg2.connect('dbname={0} host={1} port={2} user={3} password={4}'.format(DBNICHENAME, DBNICHEHOST, DBNICHEPORT, DBNICHEUSER, DBNICHEPASSWD))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    with open(sources_file, 'r') as f:
        reader = csv.reader(f)

        layerid = 0

        for line in reader:

            logger.info('linea: {0} - {1} - {2} - {3}'.format(line[0], line[1], line[2], line[3]))
            print(line[0], line[1], line[2], line[3])
            layerid += 1
            
            # se comenta linea que hace update en la tabla raster_bins
            cur.execute(update_label_var_sql.format(label=line[1], type=id_catalogo, layer='bio{0}'.format(get_three_digits_number_var(layerid))))

    cur.close()
    conn.close()

except Exception as e:
    logger.error('No se pudo crear la tabla de variables abioticas: {0}'.format(str(e)))
    sys.exit()


# Se calculan las mallas disponibles para la fuente creada
try:

    logger.info('Calculando available_grids para la fuente WorldClim')

    required_mesh_env = {
        "DBMESHNAME": DBMESHNAME,
        "DBMESHHOST": DBMESHHOST,
        "DBMESHPORT": DBMESHPORT,
        "DBMESHUSER": DBMESHUSER,
        "DBMESHPASSWD": DBMESHPASSWD,
    }
    missing_mesh_env = [key for key, value in required_mesh_env.items() if not value]

    if missing_mesh_env:
        logger.warning('No se calcula available_grids. Faltan variables: {0}'.format(', '.join(missing_mesh_env)))
    else:
        create_mesh_fdw_sql = get_sql(create_mesh_fdw)
        create_mesh_fdw_sql = create_mesh_fdw_sql.replace("__MESHDB_HOST__", DBMESHHOST)
        create_mesh_fdw_sql = create_mesh_fdw_sql.replace("__MESHDB_PORT__", DBMESHPORT)
        create_mesh_fdw_sql = create_mesh_fdw_sql.replace("__MESHDB_NAME__", DBMESHNAME)
        create_mesh_fdw_sql = create_mesh_fdw_sql.replace("__MESHDB_USER__", DBMESHUSER)
        create_mesh_fdw_sql = create_mesh_fdw_sql.replace("__MESHDB_PASS__", DBMESHPASSWD.replace("'", "''"))

        update_available_grids_sql = get_sql(update_available_grids)
        update_available_grids_sql = update_available_grids_sql.replace("__WC_SOURCE_ID__", str(id_catalogo))

        conn = psycopg2.connect('dbname={0} host={1} port={2} user={3} password={4}'.format(DBNICHENAME, DBNICHEHOST, DBNICHEPORT, DBNICHEUSER, DBNICHEPASSWD))
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        cur.execute(create_mesh_fdw_sql)
        logger.info('create_mesh_fdw_sql')

        cur.execute(update_available_grids_sql)
        logger.info('update_available_grids_sql')

        cur.close()
        conn.close()

except Exception as e:
    logger.error('No se pudo calcular available_grids: {0}'.format(str(e)))
    sys.exit()
