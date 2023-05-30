from redis import (
    StrictRedis,
    ConnectionPool,
    BlockingConnectionPool,
    ConnectionError,
)

from metric_helper.conf import settings




class RedisWrapper:

    def __init__(self):
        self.redis = None


    def connect(self):
        if self.redis is None:
            self.redis = StrictRedis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=0,
                decode_responses=True,
            )


    def get_connection(self):
        return self.redis




redis = RedisWrapper()




def get_redis_connection(decode_responses=True):
    redis.connect()
    return redis.get_connection()




def get_redis_version():
    """
    Returns the major version of the Redis instance for the connection.

    :rtype: int
    """
    conn = get_redis_connection()
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
