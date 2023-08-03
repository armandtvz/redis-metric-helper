import logging



def configure_logging():
    loggers = [
        'metric_helper',
    ]
    for logger in loggers:
        logging.getLogger(logger).addHandler(logging.NullHandler())
