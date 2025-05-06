# -*- coding: utf-8 -*-
#!/usr/bin/env python
"""Reclassify continuous raster values to discrete values using quantiles.

Example:
    To reclassify ``input.tif`` using the percentiles 20, 40, 60, 80, 100
    use the following::

        $ python reclassify_raster.py -srcfile input.tif -o output.tif -n 5
        $ python reclassify_raster.py -t -srcfile input.tif -o output.tif -n 5

"""
__author__ = 'Juan M Barrios'
__email__ = 'juan.barrios@conabio.gob.mx'
__version__ = '0.1'

# Importando módulos necesarios
from os import path
import argparse  # Para manejar argumentos de línea de comandos
import csv  # Para trabajar con archivos CSV

import numpy as np  # Para operaciones numéricas en matrices
from osgeo import gdal  # Para manipulación de datos geoespaciales
from osgeo.gdalconst import GA_ReadOnly  # Constantes de GDAL

# Diccionario para mapear tipos de datos de numpy a GDAL
NP2GDAL_DTYPE = {
    'int8': 1,
    'complex128': 11,
    'complex64': 10,
    'float64': 7,
    'float32': 6,
    'int16': 3,
    'int32': 5,
    'int64': 5,
    'uint8': 1,
    'uint16': 2,
    'uint32': 4,
    'uint64': 4
}

def get_raster_info(gdal_dataset):
    """Retorna un diccionario con información básica de un raster.

    Devuelve el tamaño en x, tamaño en y, transformación geográfica y proyección
    de un conjunto de datos GDAL.
    """
    return {
        'xsize': gdal_dataset.RasterXSize,  # Ancho del raster
        'ysize': gdal_dataset.RasterYSize,  # Alto del raster
        'geo_transformation': gdal_dataset.GetGeoTransform(),  # Transformación geográfica
        'projection': gdal_dataset.GetProjection()  # Proyección del raster
    }

def write_2darray_raster(array, fn, **kwargs):
    """Escribe una matriz 2D en un archivo raster dado.

    Guarda el array en un raster con el nombre `fn`. Si se pasan opciones, 
    el raster escrito tendrá la proyección y la información de transformación 
    geográfica.
    """
    rows, cols = array.shape  # Obtiene el número de filas y columnas del array
    if 'xsize' in kwargs:
        if kwargs['xsize'] != cols:
            raise IndexError('Array size and destination size not equal')  # Verifica coincidencia de tamaño
    if 'ysize' in kwargs:
        if kwargs['ysize'] != rows:
            raise IndexError('Array size and destination size not equal')  # Verifica coincidencia de tamaño

    # Obtiene proyección y transformación geográfica de las opciones
    projection = kwargs.get('projection', '')
    geo_transformation = kwargs.get('geo_transformation', '')

    # Crea un controlador para el formato GTiff
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(fn, cols, rows, 1, NP2GDAL_DTYPE[array.dtype.name])  # Crea un nuevo raster

    # Configura transformación geográfica y proyección si están disponibles
    if geo_transformation:
        ds.SetGeoTransform(geo_transformation)
    if projection:
        ds.SetProjection(projection)

    # Maneja valores "no data"
    if np.ma.is_masked(array):  # Si el array tiene valores enmascarados
        nodata = array.fill_value  # Asigna el valor "no data"
        array = array.filled()  # Rellena el array
    else:
        try:
            nodata = np.iinfo(array.dtype).max  # Obtiene el valor máximo según el tipo de dato
        except ValueError:
            nodata = np.finfo(array.dtype).max  # Para flotantes

    band = ds.GetRasterBand(1)  # Obtiene la banda del raster
    band.WriteArray(array)  # Escribe el array en la banda

    # Si hay un valor "no data", lo establece
    if nodata:
        band.SetNoDataValue(float(nodata))

    band.FlushCache()  # Guarda los cambios en disco

    return fn  # Retorna el nombre del archivo escrito


def main(realfile, fn, srcfile, no_of_quantiles, tags):
    """Función principal que maneja la lógica de reclasificación de raster."""
    # Imprime información sobre los archivos de entrada y salida
    print('\nInput real raster file: ' + str(realfile))
    print('\nOutput raster file: ' + str(fn))
    print('\nInput raster file: ' + str(srcfile))
    print('\nno_of_quantiles: ' + str(no_of_quantiles))
    print('\ntags: ' + str(tags))

    # Abre el archivo raster real y obtiene su información
    src_ds = gdal.Open(realfile)
    options = get_raster_info(src_ds)

    print(options)  # Imprime opciones del raster

    src_band = src_ds.GetRasterBand(1)  # Obtiene la banda del raster
    data = src_band.ReadAsArray()  # Lee los datos como un array
    data = np.ma.masked_equal(data, value=src_band.GetNoDataValue())  # Enmascara valores "no data"

    # Crea una serie de percentiles
    p = np.linspace(start=0, stop=100, num=no_of_quantiles+1)
    percentiles = np.nanpercentile(np.where(np.logical_not(data.mask), data, np.NAN), p)

    # Abre el archivo raster fuente que se va a reclasificar
    src_ds = gdal.Open(srcfile)
    options = get_raster_info(src_ds)

    src_band = src_ds.GetRasterBand(1)  # Obtiene la banda del raster
    data = src_band.ReadAsArray()  # Lee los datos como un array
    data = np.ma.masked_equal(data, value=src_band.GetNoDataValue())  # Enmascara valores "no data"

    # Asigna rangos para cada etiqueta
    labels = ['{}:{}'.format(*interval) for interval in zip(percentiles[:-1], percentiles[1:])]

    # Reclasifica los datos según los percentiles
    reclass = np.searchsorted(percentiles[1:], data.filled(percentiles[-1] + 1))  # Encuentra en qué intervalo está cada valor
    reclass += 1  # Ajusta el índice para que empiece desde 1
    reclass = np.ma.masked_equal(reclass, value=percentiles.shape[0] + 1)  # Enmascara valores fuera de rango

    # Escribe el array reclasificado en el archivo de salida
    write_2darray_raster(reclass, fn, **options)

    # Si se solicitan etiquetas, crea un archivo de etiquetas
    if tags:
        tag_fn = path.splitext(fn)[0] + '.tags'  # Genera el nombre del archivo de etiquetas
        print('Output tags file: {}'.format(tag_fn))
        info = list(zip(labels, np.arange(percentiles.shape[0]) + 1))  # Crea una lista de etiquetas
        info.insert(0, ('interval', 'percentile'))  # Agrega encabezados
        with open(tag_fn, 'w', newline='\n') as f:  # Abre el archivo de etiquetas
            writer = csv.writer(f)  # Crea un escritor CSV
            writer.writerows(info)  # Escribe la información de las etiquetas

if __name__ == '__main__':
    # Configura el análisis de argumentos de línea de comandos
    parser = argparse.ArgumentParser()
    parser.add_argument('-realfile', '--real-file',
                        help='Input raster to get the labels')  # Archivo raster de entrada para obtener etiquetas
    parser.add_argument('-srcfile', '--source-file',
                        help='Input raster to reclassify in percentiles')  # Archivo raster fuente a reclasificar
    parser.add_argument('-o', '--output-file',
                        help='Name of the reclassified raster output')  # Nombre del archivo de salida reclasificado
    parser.add_argument('-n', '--num-bins', default='10', type=int,
                        help='Number of percentile intervals')  # Número de intervalos percentiles
    parser.add_argument('-t', '--tags', action='store_true',
                        help='Generate a file with the percentiles intervals')  # Opción para generar un archivo de etiquetas

    args = parser.parse_args()  # Analiza los argumentos
    # Llama a la función principal con los argumentos proporcionados
    main(args.real_file, args.output_file, args.source_file, args.num_bins, args.tags)
