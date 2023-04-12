import json




class MetricNotFound(Exception):

    def __init__(self, name, message=None):
        if not message:
            message = f'The metric with name {name} was not found.'
        super().__init__(message)
