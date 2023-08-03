from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured




class MetricHelperConfig(AppConfig):
    name = 'metric_helper'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from metric_helper import setup
        setup()
