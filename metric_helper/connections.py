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
