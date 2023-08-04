__version__ = '0.3.2'




def setup(connection_dict=None):
    """
    Example of ``connection_dict``::

        {
            'host': 'localhost',
            'port': 6379, # Default
            'password': 'SuperS3kr!t',
            'socket_connect_timeout': 5, # Default
            'health_check_interval': 30, # Default
        }
    """
    from metric_helper.conf import settings
    from metric_helper.logging import configure_logging
    from metric_helper.connections import _redis_proxy
    configure_logging()

    # Only configure our Redis proxy object.
    # Do not connect to Redis. If we try to connect here
    # and the connection fails/hangs there's a risk that
    # we mess other things up for the user of this package.
    _redis_proxy.configure(connection_dict=connection_dict)
