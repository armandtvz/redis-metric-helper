from datetime import datetime, timedelta

from redis.exceptions import ResponseError

from metric_helper.connections import (
    get_redis_connection,
    get_redis_version,
)
from metric_helper.exceptions import MetricNotFound

redis_version = get_redis_version()

TIMESERIES_RETENTION_MSECS = (3600 * 24 * 61) * 1000 # 61 days




class Metric:

    unsupported_operation = 'This metric does not support this operation.'


    def __init__(self, name):
        self.key = name
        self.name = name
        self.redis = get_redis_connection()
        self.ts = self.redis.ts()
        self.retention_msecs = int(TIMESERIES_RETENTION_MSECS)
        self.retention_seconds = int(self.retention_msecs / 1000)


    def handle_write_kwargs(self, **kwargs):
        value = kwargs.get('value', None)
        if value is None:
            raise ValueError('You must provide a value for the metric write method.')
        labels = kwargs.get('labels', {})
        timestamp = kwargs.get('timestamp', '*')
        duplicate_policy = kwargs.get('duplicate_policy', 'SUM')
        pipeline = kwargs.get('pipeline', None)
        round_timestamp_to = kwargs.get('round_timestamp_to', None)
        return {
            'value': value,
            'labels': labels,
            'timestamp': timestamp,
            'duplicate_policy': duplicate_policy,
            'pipeline': pipeline,
            'round_timestamp_to': round_timestamp_to,
        }


    def handle_read_kwargs(self, **kwargs):
        start = kwargs.get('start', None)
        end = kwargs.get('end', None)
        bucket_secs = kwargs.get('bucket_secs', 3600)
        pipeline = kwargs.get('pipeline', None)
        empty = kwargs.get('empty', True)
        aggregation_type = kwargs.get('aggregation_type', 'sum')
        allowed_agg_types = [
            'avg',
            'sum',
            'min',
            'max',
            'range',
            'count',
            'first',
            'last',
            'std.p',
            'std.s',
            'var.p',
            'var.s',
            'twa',
        ]
        if aggregation_type:
            if aggregation_type.lower() not in allowed_agg_types:
                raise ValueError(
                    f'Invalid value, "{aggregation_type}", for "aggregation_type". '
                    f'Must be one of "{allowed_agg_types}".'
                )

        return {
            'start': start,
            'end': end,
            'bucket_secs': bucket_secs,
            'pipeline': pipeline,
            'empty': empty,
            'aggregation_type': aggregation_type,
        }


    def expire(self):
        if not self.retention_seconds:
            return
        if (
            redis_version >= 7
            and self.retention_seconds
        ):
            self.redis.expire(
                name=self.key,
                time=self.retention_seconds,
                nx=True, # Set expiry only when the key has no expiry.
            )


    #######
    # Write
    #######

    def incr(self):
        raise NotImplementedError(self.unsupported_operation)


    def decr(self):
        raise NotImplementedError(self.unsupported_operation)


    def add_sample(self):
        raise NotImplementedError(self.unsupported_operation)


    ######
    # Read
    ######

    def get(self, pipeline):
        raise NotImplementedError(self.unsupported_operation)


    def range(self, start, end, bucket_secs, pipeline):
        raise NotImplementedError(self.unsupported_operation)




class Timeseries(Metric):

    def process_timestamp(self, timestamp, round_timestamp_to):
        dt = timestamp
        timestamp = timestamp.timestamp()

        if not round_timestamp_to:
            round_timestamp_to = ''
        round_timestamp_to = round_timestamp_to.lower().strip()

        if round_timestamp_to == 'second':
            timestamp = int(timestamp)

        elif round_timestamp_to == 'minute':
            dt = dt.replace(microsecond=0, second=0)
            timestamp = dt.timestamp()

        elif round_timestamp_to == 'hour':
            dt = dt.replace(
                microsecond=0,
                second=0,
                minute=0
            )
            timestamp = dt.timestamp()
        timestamp_msecs = int(timestamp * 1000)
        return timestamp_msecs


    def expire(self):
        raise NotImplementedError(self.unsupported_operation)


    def add_sample(self, **kwargs):
        values = self.handle_write_kwargs(**kwargs)
        value = values['value']
        labels = values['labels']
        timestamp = values['timestamp']
        duplicate_policy = values['duplicate_policy']
        pipeline = values['pipeline']
        round_timestamp_to = values['round_timestamp_to']

        ts = self.ts
        if pipeline:
            ts = pipeline.ts()

        if timestamp == '*':
            # The asterisk means that Redis will automatically set the
            # timestamp for us; however if we want to include the extra
            # rounding functionality then we need to handle that here.
            timestamp = datetime.now()

        timestamp_msecs = self.process_timestamp(
            timestamp,
            round_timestamp_to,
        )
        ts.add(
            key=self.key,
            timestamp=timestamp_msecs,
            value=value,
            retention_msecs=self.retention_msecs,
            duplicate_policy=duplicate_policy,
            labels=labels,
        )


    def range(self, **kwargs):
        values = self.handle_read_kwargs(**kwargs)
        start = values['start']
        end = values['end']
        bucket_secs = values['bucket_secs']
        pipeline = values['pipeline']
        empty = values['empty']
        aggregation_type = values['aggregation_type']

        ts = self.ts
        if pipeline:
            ts = pipeline.ts()

        start = start.timestamp() * 1000
        end = end.timestamp() * 1000
        bucket_msecs = bucket_secs * 1000

        data = []
        start = int(start)
        end = int(end)
        bucket_msecs = int(bucket_msecs)
        try:
            data = ts.range(
                key=self.key,
                from_time=start,
                to_time=end,
                aggregation_type=aggregation_type,
                bucket_size_msec=bucket_msecs,
                empty=empty,
            )
        except ResponseError:
            # TSDB: the key does not exist
            pass
        if not isinstance(data, list):
            data = []
        return data




class Counter(Metric):

    def incr(self, amount=1, **kwargs):
        self.redis.incr(
            self.key,
            amount=amount,
        )
        self.expire()


    def get(self, **kwargs):
        value = self.redis.get(self.key)
        return value




class Gauge(Metric):

    def incr(self, amount=1, **kwargs):
        self.redis.incr(
            self.key,
            amount=amount,
        )
        self.expire()


    def decr(self, amount=1, **kwargs):
        self.redis.decr(
            self.key,
            amount=amount,
        )


    def get(self, **kwargs):
        value = self.redis.get(self.key)
        return value




class PositiveGauge(Metric):

    def incr(self, amount=1, **kwargs):
        self.redis.incr(
            self.key,
            amount=amount,
        )
        self.expire()


    def decr(self, amount=1, **kwargs):
        current_value = self.redis.get(self.key)
        try:
            current_value = int(current_value)
        except:
            current_value = 0

        if current_value <= 0:
            # Don't decrement this value.
            # A positive gauge cannot be smaller than 0.
            return
        self.redis.decr(
            self.key,
            amount=amount,
        )


    def get(self, **kwargs):
        value = self.redis.get(self.key)
        return value
