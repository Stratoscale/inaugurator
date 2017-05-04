import logging
from inaugurator import consts
import sys

FORMAT = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

def getRootLogger():
    return logging.getLogger()

def addStdoutHandler():
    logging.info("Logger - Adding stdout handler")
    log = getRootLogger()
    log.setLevel(logging.INFO)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(FORMAT)
    log.addHandler(ch)
    logging.info("Logger - stdout handler has been added")

def addFileHandler(filename):
    logging.info("Logger - Adding file handler %s", filename)
    log = getRootLogger()
    log.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(filename, maxBytes=(1048576 * 5), backupCount=7)
    fh.setFormatter(FORMAT)
    log.addHandler(fh)
    logging.info("Logger - File handler %s has been added", filename)

def removeAllFileHandlers():
    log = getRootLogger()
    for handler in log.handlers[:]:
        if handler.stream.name not in ['<stdout>', '<stderr>']:
            logging.info("Logger - Removing file handler %s", handler.stream.name)
            log.removeHandler(handler)
