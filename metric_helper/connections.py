from redis import (
    StrictRedis,
    ConnectionPool,
    BlockingConnectionPool,
    ConnectionError,
)




class _RedisProxy:

    def __init__(self):
        self.redis = None
        self.connection_dict = {}


    def configure(self, connection_dict=None):
        if not connection_dict:
            return
        self.connection_dict = connection_dict


    @property
    def is_configured(self):
        if self.connection_dict:
            return True
        return False


    def connect(self):
        if self.redis:
            return self.redis
        if not self.connection_dict:
            raise ValueError(
                'Redis "connection_dict" not configured. '
                'Did you call "metrics.setup()"?'
            )
        config = self.connection_dict
        host = config.get('host', 'localhost')
        port = config.get('port', 6379)
        password = config.get('password', '')
        socket_connect_timeout = config.get('socket_connect_timeout', 5)
        health_check_interval = config.get('health_check_interval', 30)

        if not host:
            host = 'localhost'
        if not port:
            port = 6379
        if not password:
            password = ''

        port = int(port)
        socket_connect_timeout = int(socket_connect_timeout)
        health_check_interval = int(health_check_interval)

        self.redis = StrictRedis(
            host=host,
            port=port,
            password=password,
            socket_connect_timeout=socket_connect_timeout,
            health_check_interval=health_check_interval,
            decode_responses=True,
            db=0,
        )
        return self.redis


    def get_connection(self):
        return self.redis


_redis_proxy = _RedisProxy()




def get_redis_connection():
    return _redis_proxy.connect()




def get_redis():
    return _redis_proxy.connect()




def get_redis_pipe():
    redis = _redis_proxy.connect()
    return redis.pipeline()




def get_redis_version():
    """
    Returns the major version of the Redis instance for the connection.

    :rtype: int
    """
    conn = get_redis()
    version = conn.info()['redis_version']
    version = version[0]
    try:
        version = int(version)
    except ValueError:
        # If first character of version
        # cannot be cast to an integer;
        # rather play it safe and set
        # the version to 0
        version = 0
    return version
