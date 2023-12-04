import re
from datetime import timedelta
from decimal import Decimal

from metric_helper.base import (
    Timeseries,
    Counter,
    Gauge,
    GaugeTS,
    PositiveGauge,
    PositiveGaugeTS,
    TDigest,
)
from metric_helper.conf import settings


__version__ = '0.7.4'

TIMESERIES = 'timeseries'
TS = 'ts'

COUNTER = 'counter'

GAUGE = 'gauge'
POSITIVE_GAUGE = 'positive_gauge'
POS_GAUGE = 'pos_gauge'

GAUGE_TS = 'gauge_ts'
POSITIVE_GAUGE_TS = 'positive_gauge_ts'
POS_GAUGE_TS = 'pos_gauge_ts'

T_DIGEST = 't_digest'
TDIGEST = 'tdigest'


metric_classes = [
    Timeseries,
    Counter,

    Gauge,
    PositiveGauge,

    GaugeTS,
    PositiveGaugeTS,

    TDigest,
]
mapping = {
    TIMESERIES: Timeseries,
    TS: Timeseries,

    COUNTER: Counter,

    GAUGE: Gauge,
    POS_GAUGE: PositiveGauge,
    POSITIVE_GAUGE: PositiveGauge,

    GAUGE_TS: GaugeTS,
    POSITIVE_GAUGE_TS: PositiveGaugeTS,
    POS_GAUGE_TS: PositiveGaugeTS,

    T_DIGEST: TDigest,
    TDIGEST: TDigest,
}
reverse_mapping = {
    Timeseries: TIMESERIES,
    Counter: COUNTER,

    Gauge: GAUGE,
    PositiveGauge: POS_GAUGE,

    GaugeTS: GAUGE_TS,
    PositiveGaugeTS: POSITIVE_GAUGE_TS,

    TDigest: T_DIGEST,
}
from metric_helper.logging import configure_logging
configure_logging()



def setup(connection_dict=None, timezone=None, trim_ms=False):
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
    from metric_helper.connections import _redis_proxy

    if not timezone:
        timezone = 'UTC'
    settings.set_tz(timezone)
    settings.TRIM_MS = trim_ms

    # if _redis_proxy.is_configured:
    #     return

    # Only configure our Redis proxy object.
    # Do not connect to Redis. If we try to connect here
    # and the connection fails/hangs there's a risk that
    # we mess other things up for the user of this package.
    _redis_proxy.configure(connection_dict=connection_dict)




def chunk(the_list, chunk_size):
    for i in range(0, len(the_list), chunk_size):
        yield the_list[i:i + chunk_size]




def pipeline(commands, batch_size=100):
    from metric_helper.connections import get_redis
    from metric_helper.base import Command
    from metric_helper.dataset import Dataset

    redis = get_redis()
    pipe = redis.pipeline()
    results = []

    def _pipe(_commands):
        for command in _commands:
            if not isinstance(command, Command):
                raise TypeError(
                    'Operation on metric in pipeline was not deferred. '
                    'You must set "defer=True" on all operations used in '
                    '"pipeline()". If that does not work the operation might '
                    'not be deferrable.'
                )
            command.execute(pipe)
        return pipe.execute()

    chunks = chunk(commands, batch_size)
    for _chunk in chunks:
        partial = _pipe(_chunk)
        results.extend(partial)

    _results = []
    for result in results:
        if isinstance(result, list):
            try:
                first_result = result[0]
                if isinstance(first_result, list):
                    if len(first_result) == 2:
                        result = Dataset(result)
            except IndexError:
                pass
        _results.append(result)

    results = _results
    return results




class Metrics:

    def __init__(self):
        pass


    def setup(self, **kwargs):
        setup(**kwargs)


    def get(self, name, metric_type='timeseries'):
        try:
            Metric = mapping[metric_type]
        except KeyError:
            raise ValueError(f'Unknown "metric_type", "{metric_type}", provided.')
        return Metric(name)


    def ask(self, key, metric_type='timeseries', period=None, **kwargs):
        """
        This method is still completely unstable and likely to change.

        So to ask "does the API response time 99th quantile exceed 5 seconds?"::

        To ask "does the API error count exceed 30 errors for today"::

        To ask "does the API error count exceed 30 errors in the last 24 hours"::

            is_over = metrics.ask(
                'api:error_count',
                metric_type='timeseries',
                period='24h',
                gt=30,
            )

        Usage::

            is_over = metrics.ask(
                'api:error_count',
                metric_type='timeseries',
                period='24h',
                gt=30,
            )
        """
        functions = [
            'gt',
            'lt',
            'gte',
            'lte',
            'eq',
        ]
        fixed_periods = [
            'today',
            'week',
            'month',
            'year',
            'latest',
        ]
        metric = self.get(key, metric_type)
        unit = None
        period = period.lower()
        if period not in fixed_periods:
            pattern = r'(\d+)(h|m|s)'
            match = re.search(pattern, period)
            if match:
                period = match.group(1)
                unit = match.group(2)
                try:
                    period = int(period)
                except (TypeError, ValueError):
                    period = None
            else:
                period = None

        if not period:
            raise ValueError(f'Invalid period supplied "{period}"')

        delta = None
        if unit == 'h':
            delta = timedelta(hours=period)

        elif unit == 'm':
            delta = timedelta(minutes=period)

        elif unit == 's':
            delta = timedelta(seconds=period)

        data = []
        if delta:
            data = metric.start_from(delta)
        else:
            if period == 'today':
                data = metric.today()

            elif period == 'week':
                data = metric.week()

            elif period == 'month':
                data = metric.month()

            elif period == 'year':
                data = metric.year()

            elif period == 'latest':
                data = metric.get()

        if metric_type == 'timeseries':
            value = data.count()

        method = None
        kwarg = None
        # TODO: allow combining various comparison functions
        if 'gt' in kwargs:
            kwarg = 'gt'
            method = '__gt__'

        elif 'lt' in kwargs:
            kwarg = 'lt'
            method = '__lt__'

        elif 'ge' in kwargs:
            kwarg = 'ge'
            method = '__ge__'

        elif 'gte' in kwargs:
            kwarg = 'gte'
            method = '__ge__'

        elif 'le' in kwargs:
            kwarg = 'le'
            method = '__le__'

        elif 'lte' in kwargs:
            kwarg = 'lte'
            method = '__le__'

        elif 'eq' in kwargs:
            kwarg = 'eq'
            method = '__eq__'

        if not method:
            raise ValueError(
                f'No comparison kwarg in provided kwargs: "{kwargs}"'
            )

        operand = kwargs.get(kwarg, None)
        if not isinstance(operand, (int, float, Decimal,)):
            _type = type(operand)
            raise ValueError(
                f'Value for comparison must be of types '
                f'int, float or Decimal. Got type "{_type}".'
            )

        compare = getattr(value, method)
        return compare(operand)


    def change_primary_retention(self, retention_seconds):
        from metric_helper.connections import get_redis

        redis = get_redis()
        ts = redis.ts()
        pipe = redis.pipeline()

        counter = 0
        keys = redis.scan_iter(_type='TSDB-TYPE')
        for key in keys:
            if '--agg_' in key:
                continue
            counter += 1
            metric = metrics.get(key)
            metric.change_retention(
                retention_seconds=retention_seconds,
                pipeline=pipe,
            )
            if counter >= 100:
                pipe.execute()
        pipe.execute()


    def auto_add_rules(self, agg_type='sum', **kwargs):
        from metric_helper.connections import get_redis

        redis = get_redis()
        keys = redis.scan_iter(_type='TSDB-TYPE')
        for key in keys:
            if '--agg_' in key:
                continue
            metric = metrics.get(key)
            metric.auto_add_rules(agg_type=agg_type, **kwargs)
            metric.backfill()


metrics = Metrics()
