from metric_helper.conf import settings
from metric_helper.base import Timeseries, Counter, Gauge, PositiveGauge
from metric_helper.connections import get_redis_connection
from metric_helper.exceptions import MetricNotFound


metric_classes = [
    Timeseries,
    Counter,
    Gauge,
    PositiveGauge,
]
# These string names may not change unless extreme caution is used
# and the consequences are understood.
mapping = {
    'timeseries': Timeseries,
    'counter': Counter,
    'gauge': Gauge,
    'positive_gauge': PositiveGauge,
}
reverse_mapping = {
    Timeseries: 'timeseries',
    Counter: 'counter',
    Gauge: 'gauge',
    PositiveGauge: 'positive_gauge',
}




class Registry:

    def __init__(self):
        self.key = 'metrics:registry' # redis hash
        self.redis = get_redis_connection()
        self.metric_list = []
        self.metrics = {}

        # Get the metrics that already exist in the registry on Redis.
        metrics = self.redis.hgetall(self.key)
        for name, metric_type in metrics.items():
            try:
                metric_class = mapping[metric_type]
            except KeyError:
                continue
            self._add(name, metric_class)


    def _add(self, name, metric_class):
        metric = metric_class(name)
        self.metric_list.append(metric)
        self.metrics[name] = metric
        return metric


    def get(self, name):
        metric = None
        try:
            metric = self.metrics[name]
        except KeyError:
            raise MetricNotFound(name)
        return metric


    def get_or_add(self, name, metric_class):
        """
        If a metric is requested and does not exist; it will be created
        in the registry instead of raising ``MetricNotFound``.
        """
        metric = None
        try:
            metric = self.get(name)
        except MetricNotFound:
            self.add(name, metric_class)
            metric = self.get(name)
        return metric


    def add(self, name, metric_class):
        """
        Add a metric to the registry.
        """
        if metric_class not in metric_classes:
            raise ValueError(f'metric_class arg must be one of {metric_classes}')
        metric_type = reverse_mapping[metric_class]
        self.redis.hsetnx(
            self.key,
            key=name,
            value=metric_type,
        )
        metric = self._add(name, metric_class)
        return metric




registry = Registry()
