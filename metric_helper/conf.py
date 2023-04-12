from decouple import config


class Settings:
    REDIS_HOST = config('REDIS_HOST', default='localhost')
    REDIS_PORT = config('REDIS_PORT', default=6379, cast=int)

    retention_msecs = (3600 * 24 * 61) * 1000 # 61 days
    TIMESERIES_RETENTION_MSECS = config(
        'TIMESERIES_RETENTION_MSECS',
        default=retention_msecs,
        cast=int,
    )


settings = Settings
