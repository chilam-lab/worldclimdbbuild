import os
import logging
from colorlog import ColoredFormatter

def setup_logger():
    """
        Logger de colores
    """
    formatter = ColoredFormatter(
        "%(log_color)s [%(levelname)s - %(asctime)s] %(reset)s %(blue)s%(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        reset=True,
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red',
        }
    )

    logger = logging.getLogger('')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger

def get_sql(name):
    """
        Procedimiento para obtener el sql
    """
    with open(name, 'r') as f:
        sql = f.read()
    return sql

def reading_environment_vars():
    """
        Funcion para leer credenciales del ambiente
    """
    DBNICHEHOST = os.environ['DBNICHEHOST']
    DBNICHEPORT = os.environ['DBNICHEPORT']
    DBNICHEUSER = os.environ['DBNICHEUSER']
    DBNICHEPASSWD = os.environ['DBNICHEPASSWD']
    DBNICHENAME = os.environ['DBNICHENAME']
    return DBNICHEHOST, DBNICHEPORT, DBNICHEUSER, DBNICHEPASSWD, DBNICHENAME

def get_basename(info):
    """
    Funcion para obtener el nombre de un archivo sin extension
    """
    aux_list = info.split('.')
    N = len(aux_list)
    return '.'.join(aux_list[:N-1])

def get_three_digits_number_var(n):
    """
    Funcion para obtener el numero de una variable abiotica a tres digitos
    """
    return str(n).zfill(3)