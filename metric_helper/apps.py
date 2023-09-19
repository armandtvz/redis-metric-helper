from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured




class MetricHelperConfig(AppConfig):
    name = 'metric_helper'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from metric_helper import setup
        from django.conf import settings

        host = getattr(settings, 'METRICS_REDIS_HOST', 'localhost')
        port = getattr(settings, 'METRICS_REDIS_PORT', 6379)
        password = getattr(settings, 'METRICS_REDIS_PASSWORD', '')

        setup(
            connection_dict={
                'host': host,
                'port': port,
                'password': password,
            },
            timezone=settings.TIME_ZONE,
        )
