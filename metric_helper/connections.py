from redis import (
    StrictRedis,
    ConnectionPool,
    BlockingConnectionPool,
    ConnectionError,
)

from metric_helper.conf import settings




class _RedisProxy:

    def __init__(self):
        self.redis = None
        self.connection_dict = {}


    def configure(self, connection_dict=None):
        if not connection_dict:
            connection_dict = {
                'host': settings.REDIS_HOST,
                'port': settings.REDIS_PORT,
                'password': settings.REDIS_PASSWORD,
                'socket_connect_timeout': settings.REDIS_SOCKET_CONNECT_TIMEOUT,
                'health_check_interval': settings.REDIS_HEALTH_CHECK_INTERVAL,
            }
        self.connection_dict = connection_dict


    def connect(self):
        if self.redis:
            return self.redis
        if not self.connection_dict:
            self.configure()

        config = self.connection_dict
        host = config.get('host', 'localhost')
        port = config.get('port', 6379)
        password = config.get('password', '')
        decode_responses = config.get('decode_responses', True)
        socket_connect_timeout = config.get('socket_connect_timeout', 5)
        health_check_interval = config.get('health_check_interval', 30)

        port = int(port)
        decode_responses = bool(decode_responses)
        socket_connect_timeout = int(socket_connect_timeout)
        health_check_interval = int(health_check_interval)

        self.redis = StrictRedis(
            host=host,
            port=port,
            password=password,
            socket_connect_timeout=socket_connect_timeout,
            health_check_interval=health_check_interval,
            decode_responses=decode_responses,
            db=0,
        )
        return self.redis


    def get_connection(self):
        return self.redis


_redis_proxy = _RedisProxy()




def get_redis_connection(decode_responses=True):
    return redis_proxy.connect()




def get_redis():
    return redis_proxy.connect()




def get_redis_pipe():
    redis = redis_proxy.connect()
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
