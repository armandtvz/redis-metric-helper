from decouple import config


class Settings:
    REDIS_HOST = config('METRICS_REDIS_HOST', default='localhost')
    REDIS_PORT = config('METRICS_REDIS_PORT', default=6379, cast=int)
    REDIS_PASSWORD = config('METRICS_REDIS_PASSWORD', default='')
    REDIS_SOCKET_CONNECT_TIMEOUT = config('REDIS_SOCKET_CONNECT_TIMEOUT', default=5, cast=int)
    REDIS_HEALTH_CHECK_INTERVAL = config('REDIS_HEALTH_CHECK_INTERVAL', default=30, cast=int)

    retention_msecs = (3600 * 24 * 61) * 1000 # 61 days
    TIMESERIES_RETENTION_MSECS = config(
        'TIMESERIES_RETENTION_MSECS',
        default=retention_msecs,
        cast=int,
    )


settings = Settings
