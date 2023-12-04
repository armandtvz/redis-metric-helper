import math
import time
from functools import wraps, cached_property, lru_cache
from collections import namedtuple
from datetime import datetime, timedelta

from redis.exceptions import ResponseError

from metric_helper.connections import (
    get_redis_connection,
    get_redis_version,
)
from metric_helper.exceptions import MetricNotFound
from metric_helper import timezone
from metric_helper.dataset import Dataset
from metric_helper.conf import settings

TIMESERIES_RETENTION_DAYS  = 8
TIMESERIES_RETENTION_MSECS = (3600 * 24 * TIMESERIES_RETENTION_DAYS) * 1000




class Command:
    def __init__(self, metric, attr, *args, **kwargs):
        self.metric = metric
        self.attr = attr
        self.args = args
        self.kwargs = kwargs


    def execute(self, pipe=None):
        self.kwargs.pop('defer', None)
        self.kwargs['pipeline'] = pipe
        func = getattr(self.metric, self.attr)
        return func(*self.args, **self.kwargs)




class Rule:

    def __init__(self, **kwargs):
        self.key = kwargs['key']
        self.source_key = kwargs['source_key']
        self.bucket_msecs = kwargs['bucket_msecs']
        self.bucket_secs = kwargs['bucket_secs']
        self.agg_type = kwargs['agg_type']

        self.redis = get_redis_connection()
        self.ts = self.redis.ts()


    def exists(self) -> bool:
        if self.redis.exists(self.key):
            return True
        return False


    def deleterule(self):
        self.ts.deleterule(self.source_key, self.key)


    def delete(self):
        self.redis.delete(self.key)
        self.deleterule()




def deferrable(function):
    @wraps(function)
    def decorator(self, *args, **kwargs):
        defer = kwargs.get('defer', None)
        if defer:
            return Command(self, function.__name__, *args, **kwargs)
        if not 'pipeline' in kwargs:
            kwargs['pipeline'] = None
        return function(self, *args, **kwargs)
    return decorator




class Metric:

    unsupported_operation = 'This metric does not support this operation.'


    def __init__(self, name):
        self.key = name
        self.name = name
        self.redis = get_redis_connection()
        self.ts = self.redis.ts()
        self.tdigest = self.redis.tdigest()
        # self.retention_msecs = int(TIMESERIES_RETENTION_MSECS)
        # self.retention_seconds = int(self.retention_msecs / 1000)
        self.retention_msecs = None
        self.retention_seconds = None
        self.key_exists = False


    def get_redis_or_pipe(self, **kwargs):
        pipe = kwargs.get('pipeline', None)
        if pipe:
            return pipe
        return self.redis


    def expire(self, ttl_seconds=None):
        redis_version = get_redis_version()
        ttl = ttl_seconds
        if not redis_version >= 7:
            # Redis versions smaller than 7 don't support ``nx=True``.
            # Which is to "set expiry only when the key has no expiry".
            return
        if ttl is None:
            ttl = self.retention_seconds
        if not ttl:
            return
        self.redis.expire(
            name=self.key,
            time=ttl,
            nx=True, # Set expiry only when the key has no expiry.
        )


    def ttl(self):
        return self.redis.ttl(self.key)


    def exists(self, cached=False) -> bool:
        if self.key_exists and cached:
            return True
        result = self.redis.exists(self.key)
        if result:
            self.key_exists = True
            return True
        self.key_exists = False
        return False


    def get_type(self):
        return self.redis.type(self.key)


    def delete(self):
        self.redis.delete(self.key)




class Timeseries(Metric):

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_compaction = False


    def _handle_write_kwargs(self, **kwargs):
        value = kwargs.get('value', None)
        if value is None:
            raise ValueError('You must provide a value for the metric write method.')
        labels = kwargs.get('labels', {})
        timestamp = kwargs.get('timestamp', '*')
        if timestamp == '*':
            # The asterisk means that Redis will automatically set the
            # timestamp for us; however if we want to include the extra
            # rounding functionality then we need to handle that here.
            timestamp = datetime.now()
        duplicate_policy = kwargs.get('duplicate_policy', 'SUM')
        pipeline = kwargs.get('pipeline', None)
        round_timestamp_to = kwargs.get('round_timestamp_to', None)
        if not round_timestamp_to and settings.TRIM_MS:
            round_timestamp_to = 'second'

        timestamp_msecs = self._process_timestamp(
            timestamp,
            round_timestamp_to,
        )
        return {
            'value': value,
            'labels': labels,
            'timestamp': timestamp,
            'timestamp_msecs': timestamp_msecs,
            'duplicate_policy': duplicate_policy,
            'pipeline': pipeline,
            'round_timestamp_to': round_timestamp_to,
        }


    def _handle_read_kwargs(self, **kwargs):
        start = kwargs.get('start', None)
        if not start:
            start = '-'

        end = kwargs.get('end', None)
        if not end:
            end = '+'

        if isinstance(start, str):
            start = start.strip()
            if start == '+':
                raise ValueError(
                    '"start" kwarg value cannot be "+". Must be a datetime or "-"'
                )

        if isinstance(end, str):
            end = end.strip()
            if end == '-':
                raise ValueError(
                    '"end" kwarg value cannot be "-". Must be a datetime or "+"'
                )

        if start != '-':
            # timezone.is_aware(start) is True
            # if not timezone.is_aware(start):
            #     print('start', start)
            start = start.timestamp() * 1000
            start = int(start)

        if end != '+':
            # assert timezone.is_aware(end) is True
            # if not timezone.is_aware(start):
            #     print('end', end)
            end = end.timestamp() * 1000
            end = int(end)

        bucket_secs = kwargs.get('bucket_secs', 3600)
        bucket_msecs = int(bucket_secs * 1000)
        pipeline = kwargs.get('pipeline', None)
        empty = kwargs.get('empty', False)
        latest = kwargs.get('latest', False)
        agg_type = kwargs.get('agg_type', 'sum')

        if agg_type:
            agg_type = agg_type.lower()
            if agg_type not in self.allowed_agg_types:
                raise ValueError(
                    f'Invalid value, "{agg_type}", for "agg_type". '
                    f'Must be one of "{self.allowed_agg_types}".'
                )

        key = self.key
        if not self.is_compaction:
            # Can only select a key if this is not a compaction
            key = self._get_best_key(bucket_secs)

        return {
            'start': start,
            'end': end,
            'key': key,
            'bucket_secs': bucket_secs,
            'bucket_msecs': bucket_msecs,
            'pipeline': pipeline,
            'empty': empty,
            'latest': latest,
            'agg_type': agg_type,
        }


    def _process_timestamp(self, timestamp, round_timestamp_to):
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


    def _get_buckets(self, query_start, query_end, bucket_msecs):
        start = 0 # Unix epoch start
        counter = 0
        start = self._get_bucket_start(query_start, bucket_msecs)

        while start <= query_end:
            counter += 1
            bucket_start = start
            start += bucket_msecs
            if start < query_start:
                continue
            yield bucket_start


    # TODO DRY
    def _info(self):
        info = None
        try:
            info = self.ts.info(self.key)
        except ResponseError:
            if not self.exists():
                return
            raise
        return info


    def retention(self):
        info = self._info()
        if info:
            return info.retention_msecs
        return


    @property
    def info(self):
        return self.ts.info(self.key)


    @property
    def is_compaction(self):
        if self._is_compaction:
            # If we already know this is a compaction return early.
            return True

        compaction = False
        info = self._info()
        srckey = None
        try:
            srckey = info.source_key or info.sourceKey
        except AttributeError:
            compaction = False

        if srckey:
            compaction = True

        self._is_compaction = compaction
        return self._is_compaction


    @property
    def first_timestamp(self):
        info = self._info()
        return self.info.first_timestamp or self.info.first_time_stamp


    @property
    def last_timestamp(self):
        info = self._info()
        return info.last_timestamp or info.last_time_stamp


    @property
    def oldest_timestamp(self):
        info = self._info()
        first = info.first_timestamp or info.first_time_stamp
        last = info.last_timestamp or info.last_time_stamp
        if first < last:
            return first
        return last


    # @property
    # def retention_msecs(self):
    #     info = self._info()
    #     return info.retention_msecs


    @deferrable
    def change_retention(self, retention_seconds, pipeline=None):
        if isinstance(retention_seconds, timedelta):
            retention_seconds = int(retention_seconds.total_seconds())
        retention_msecs = retention_seconds * 1000

        ts = self.ts
        if pipeline:
            ts = pipeline.ts()

        ts.alter(
            key=self.key,
            retention_msecs=retention_msecs,
        )


    @deferrable
    def add_sample(self, **kwargs):
        values = self._handle_write_kwargs(**kwargs)
        value = values['value']
        labels = values['labels']
        timestamp_msecs = values['timestamp_msecs']
        duplicate_policy = values['duplicate_policy']
        pipeline = values['pipeline']

        ts = self.ts
        if pipeline:
            ts = pipeline.ts()

        if not self.exists(cached=True):
            self.ts.create(
                key=self.key,
                retention_msecs=self.retention_msecs,
            )

        ts.add(
            key=self.key,
            timestamp=timestamp_msecs,
            value=value,
            retention_msecs=self.retention_msecs,
            duplicate_policy=duplicate_policy,
            labels=labels,
        )


    @deferrable
    def add(self, value=1, **kwargs):
        kwargs['value'] = value
        self.add_sample(**kwargs)


    @classmethod
    def madd(cls, keys: list, value=1, **kwargs):
        """
        This method is likely to change and is not considered to be
        part of the public API even though it is not a private method.
        """
        from metric_helper import metrics

        redis = get_redis_connection()
        pipeline = redis.pipeline()
        kwargs['value'] = value
        kwargs['pipeline'] = pipeline
        for key in keys:
            metric = metrics.get(key, metric_type='timeseries')
            metric.add(**kwargs)
        pipeline.execute()


    @deferrable
    def range(self, **kwargs):
        """
        The start time is inclusive and the end time is exclusive.

        Also, if you ask RedisTimeSeries for hourly buckets for the
        hours between 3PM and 7PM and your input start timestamp is,
        for example 3:15PM, then Redis' result set will start at 3PM.
        This applies to all aggregations: Redis will select the first
        bucket start time that lands before your query start time.
        """
        values = self._handle_read_kwargs(**kwargs)
        key = values['key']
        start = values['start']
        end = values['end']
        bucket_msecs = values['bucket_msecs']
        pipeline = values['pipeline']
        empty = values['empty']
        latest = values['latest']
        agg_type = values['agg_type']

        # print('')
        # if isinstance(start, int):
        #     s = timezone.fromtimestamp(start, ms=True)
        #     print(s.isoformat())
        #
        # if isinstance(end, int):
        #     e = timezone.fromtimestamp(end, ms=True)
        #     print(e.isoformat())
        #
        # print(f'TS.RANGE {key} {start} {end} AGGREGATION {agg_type} {bucket_msecs}')

        ts = self.ts
        if pipeline:
            ts = pipeline.ts()

        data = []
        try:
            data = ts.range(
                key=key,
                from_time=start,
                to_time=end,
                aggregation_type=agg_type,
                bucket_size_msec=bucket_msecs,
                empty=empty,
                latest=latest,
            )
        except ResponseError:
            # TSDB: the key does not exist
            pass

        if not isinstance(data, list) and pipeline:
            data = []

        if not pipeline:
            dataset = Dataset(data)
            return dataset
        return data


    @deferrable
    def get(self, **kwargs):
        data = None
        pipeline = kwargs.get('pipeline', None)

        ts = self.ts
        if pipeline:
            ts = pipeline.ts()

        try:
            data = ts.get(self.key)
        except ResponseError:
            # TSDB: the key does not exist
            pass

        return data


    #######################
    # Methods using range()
    #######################

    def count(self, seconds=None, **kwargs):
        kwargs.pop('bucket_secs', None)
        start = kwargs.get('start', None)
        end = kwargs.get('end', None)
        now = timezone.now()

        if seconds:
            start = now - timedelta(seconds=seconds)
            end = now

        if not start:
            start = '-'
        if not end:
            end = '+'

        bucket_secs = 2592000
        if isinstance(start, datetime) and isinstance(end, datetime):
            bucket_secs = (end - start).total_seconds() + 3600

        kwargs['bucket_secs'] = bucket_secs
        kwargs['start'] = start
        kwargs['end'] = end
        kwargs['latest'] = True
        data = self.range(**kwargs)

        total = 0
        if not data:
            return total

        for item in data:
            total += item[1]

        if (total % int(total)) == 0:
            # Prevent returning something like 7.0.
            # Return 7 instead.
            return int(total)
        return total


    def rate(self, window=60, **kwargs):
        kwargs['bucket_secs'] = window
        end = kwargs.get('end', None)
        start = kwargs.get('start', None)

        if not end:
            end = timezone.now()

        if not start:
            window = window * 20
            start = end - timedelta(seconds=window)

        kwargs['start'] = start
        kwargs['end'] = end

        period = (end - start).total_seconds()
        data = self.range(**kwargs)
        count = data.count() / period
        return data.mean


    @deferrable
    def seconds(self, number, **kwargs):
        now = timezone.now()
        start = now - timedelta(seconds=number)
        kwargs['start'] = start
        kwargs['end'] = now
        return self.range(**kwargs)


    @deferrable
    def hour(self, **kwargs):
        now = timezone.now()
        start = None
        end = None
        start, end = timezone.get_last_hour_range()
        kwargs['start'] = start
        kwargs['end'] = end
        return self.range(**kwargs)


    @deferrable
    def hours(self, number, **kwargs):
        now = timezone.now()
        start = now - timedelta(hours=number)
        kwargs['start'] = start
        kwargs['end'] = now
        return self.range(**kwargs)


    @deferrable
    def today(self, **kwargs):
        now = timezone.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        kwargs['start'] = midnight
        kwargs['end'] = now
        return self.range(**kwargs)


    @deferrable
    def yesterday(self, **kwargs):
        now = timezone.now()
        start = now - timedelta(days=1)
        end = start
        start = start.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        end = end.replace(
            hour=23,
            minute=59,
            second=59,
            microsecond=999_999,
        )
        kwargs['start'] = start
        kwargs['end'] = end
        return self.range(**kwargs)


    @deferrable
    def days(self, number, **kwargs):
        now = timezone.now()
        start = now - timedelta(days=number)
        kwargs['start'] = start
        kwargs['end'] = now
        return self.range(**kwargs)


    @deferrable
    def last_week(self, **kwargs):
        start, end = timezone.get_last_week_daterange()
        kwargs['start'] = start
        kwargs['end'] = end
        return self.range(**kwargs)


    @deferrable
    def week(self, **kwargs):
        start, end = timezone.get_week_daterange()
        kwargs['start'] = start
        kwargs['end'] = end
        return self.range(**kwargs)


    @deferrable
    def month(self, month_number=None, **kwargs):
        start, end = timezone.get_month_range(month=month_number)
        kwargs['start'] = start
        kwargs['end'] = end
        return self.range(**kwargs)


    @deferrable
    def year(self, year_number=None, **kwargs):
        start, end = timezone.get_year_range(year=year_number)
        kwargs['start'] = start
        kwargs['end'] = end
        return self.range(**kwargs)


    @deferrable
    def start_from(self, delta, **kwargs):
        end = timezone.now()
        if not isinstance(delta, timedelta):
            _type = type(delta)
            raise ValueError(
                f'Value for "delta" argument must be a "timedelta". Got "{_type}"'
            )
        start = end - delta
        kwargs['start'] = start
        kwargs['end'] = end
        return self.range(**kwargs)


    #####################################
    # Method related to compaction rules.
    #####################################

    def add_rule(
        self,
        agg_type=None,
        bucket_secs=None,
        retention_days=None,
    ):
        """
        Compaction rules destination key naming conventions::

            {source_key}--agg_{bucket_seconds}_{agg_type}

            posfix:sent:sender:123:test_emails
            posfix:sent:sender:123:test_emails--agg_60_sum
            posfix:sent:sender:123:test_emails--agg_900_sum
            posfix:sent:sender:123:test_emails--agg_3600_sum
            posfix:sent:sender:123:test_emails--agg_86400_sum
            posfix:sent:sender:123:test_emails--agg_604800_sum

            posfix:sent:sender:123:test_emails
            posfix:sent:sender:123:test_emails--agg_60_avg
            posfix:sent:sender:123:test_emails--agg_900_avg
            posfix:sent:sender:123:test_emails--agg_3600_avg
            posfix:sent:sender:123:test_emails--agg_86400_avg
            posfix:sent:sender:123:test_emails--agg_604800_avg

            posfix:sent:sender:123:test_emails
            posfix:sent:sender:123:test_emails--agg_60_std.p
            posfix:sent:sender:123:test_emails--agg_900_std.p
            posfix:sent:sender:123:test_emails--agg_3600_std.p
            posfix:sent:sender:123:test_emails--agg_86400_std.p
            posfix:sent:sender:123:test_emails--agg_604800_std.p
        """
        agg_type = agg_type.lower()
        if agg_type not in self.allowed_agg_types:
            # TODO DRY
            raise ValueError(
                f'Invalid value, "{agg_type}", for "agg_type". '
                f'Must be one of "{self.allowed_agg_types}".'
            )

        if retention_days is None:
            retention_days = 61
        retention_msecs = int(retention_days * 24 * 60 * 60 * 1000)
        bucket_msecs = bucket_secs * 1000

        dest_key = f'{self.key}--agg_{bucket_secs}_{agg_type}'
        exists = self.redis.exists(dest_key)
        if exists:
            rules = self.rules()
            if isinstance(rules, list):
                for rule in rules:
                    if rule.key == dest_key:
                        raise ValueError(
                            f'Rule for "{dest_key}" already exists.'
                        )
            # The key exists but is not related to a rule.
            # Make sure the retention is set correctly before
            # creating the rule.
            self.ts.alter(
                key=dest_key,
                retention_msecs=retention_msecs,
            )
        else:
            self.ts.create(
                dest_key,
                retention_msecs,
            )
        self.ts.createrule(
            self.key,
            dest_key,
            agg_type,
            bucket_size_msec=bucket_msecs,
        )


    def auto_add_rules(self, agg_type='sum', **kwargs):
        """
        A very opinionated method to automatically create compaction rules
        for a metric.
        """
        self.add_rule(
           agg_type=agg_type,
           bucket_secs=60,
           retention_days=8,
        )
        self.add_rule(
           agg_type=agg_type,
           bucket_secs=900,
           retention_days=128,
        )
        self.add_rule(
           agg_type=agg_type,
           bucket_secs=3600,
           retention_days=367,
        )
        self.add_rule(
           agg_type=agg_type,
           bucket_secs=86400,
           retention_days=734,
        )


    def rules(self) -> list:
        """
        Return the currently existing compaction rules for a metric.

        For example::

            rules = metric.rules()
            for rule in rules:
                print(rule.key)
                print(rule.bucket_msecs)
                print(rule.bucket_secs)
                print(rule.agg_type)
        """
        # [['namespace:metric--agg_3600_sum', 3600000, 'SUM']]
        info = self._info()
        if not self.exists():
            # print('does not exist')
            return []
        rules = info.rules
        if not rules:
            # print('no rules')
            return []
        _list = []
        for rule in rules:
            key = rule[0]
            bucket_msecs = rule[1]
            bucket_secs = int(bucket_msecs / 1000)
            agg_type = rule[2]
            rule = Rule(
                key=key,
                source_key=self.key,
                bucket_msecs=bucket_msecs,
                bucket_secs=bucket_secs,
                agg_type=agg_type,
            )
            _list.append(rule)
        return _list


    def delete_all_rules(self):
        rules = self.rules()
        for rule in rules:
            try:
                rule.delete()
            except ResponseError:
                pass


    def delete(self, everything=False):
        if everything:
            self.delete_all_rules()
        super().delete()


    def _get_best_key(self, query_bucket_secs):
        """
        When querying aggregated data, use this method to automatically
        figure out which key will yield the best performance by querying
        compaction rules in line with the bucket duration being queried
        instead of getting raw data. This means that the user never has
        to use the compaction rule keys directly.
        """
        rules = self.rules()
        if not rules:
            return self.key

        best_key = None
        for rule in rules:
            if rule.bucket_secs <= query_bucket_secs:
                matching_bucket = rule.bucket_secs
                best_key = rule.key

        if best_key:
            return best_key
        return self.key


    @classmethod
    def _get_bucket_start(cls, start_msecs, bucket_msecs):
        """
        Given a start time in milliseconds and the bucket in milliseconds:
        calculates the start time of the bucket that Redis will select.

        Without this, knowing where a bucket starts given the start time
        being queried you'd have to iterate through many timestamps all
        the way from the Unix epoch.

        This does not account for ``ALIGN`` in RedisTimeSeries.
        """
        return start_msecs // bucket_msecs * bucket_msecs


    def get_pages(self, bucket_msecs):
        """
        Generator method to calculate the ``start`` and ``end`` times for all
        possible "pages" of this metric given the bucket size in milliseconds.

        This is used while backfilling the rules (destination keys) for a
        timeseries (source key).

        :param bucket_msecs: Bucket in milliseconds used to calculate the pages.

        :returns: Yields a tuple containing the start and end for each page.
        """
        end = self.last_timestamp
        start = self._get_bucket_start(self.oldest_timestamp, bucket_msecs)

        # print('\n')
        # print('oldest_timestamp', datetime.fromtimestamp(self.oldest_timestamp/1000))
        # print('start', datetime.fromtimestamp(start/1000))

        buckets_per_page = 200
        page_size = bucket_msecs * buckets_per_page

        while start <= end:
            page_start = start
            page_end = start + page_size
            start = page_end

            # print('page_start', datetime.fromtimestamp(page_start/1000))
            # print('page_end', datetime.fromtimestamp(page_end/1000))
            yield (page_start, page_end)


    def bulk_add(self, data, key=None, duplicate_policy=None):
        if not key:
            # Key might not be the source key; might be adding data
            # to a destination key (compaction rule).
            key = self.key
        pipe = self.redis.pipeline()
        ts = pipe.ts()
        number_of_commands = 0

        if not self.exists():
            ts.create(
                key=self.key,
                retention_msecs=self.retention_msecs,
            )

        for timestamp, value in data:
            if isinstance(timestamp, datetime):
                timestamp = int(timestamp.timestamp() * 1000)
            ts.add(
                key=key,
                timestamp=timestamp,
                value=value,
                duplicate_policy=duplicate_policy,
            )
            number_of_commands += 1
            if number_of_commands >= 2000:
                pipe.execute()
        # Execute any remaining commands in the pipeline
        pipe.execute()


    def backfill(self, duplicate_policy=None):
        """
        Backfill all compaction rules for this metric. Will not overwrite
        or alter existing data.

        :param duplicate_policy: Default is ``first`` which according to the Redis
                                 docs means: "ignore any newly reported value".
                                 Only ``first`` and ``block`` are allowed values
                                 as they are the only safe duplicate policies
                                 for an operation like this.
        """
        if self.is_compaction:
            return

        rules = self.rules()
        if not rules:
            return

        # duplicate policies:
        # block == ignore any newly reported value and reply with an error
        # first == ignore any newly reported value
        if not duplicate_policy:
            duplicate_policy = 'first'
        if not duplicate_policy.lower() in ['block', 'first']:
            raise ValueError(
                '"duplicate_policy" must be either "block" or "first".'
            )

        for rule in rules:
            source_key = self.key
            pages = self.get_pages(rule.bucket_msecs)
            for start, end in pages:
                data = self.ts.range(
                    key=source_key,
                    from_time=start,
                    to_time=end,
                    aggregation_type=rule.agg_type,
                    bucket_size_msec=rule.bucket_msecs,
                    empty=False,
                )
                self.bulk_add(
                    data,
                    key=rule.key,
                    duplicate_policy=duplicate_policy,
                )




class TDigest(Metric):

    # TODO DRY
    def _info(self):
        tdigest = self.get_redis_or_pipe(**kwargs).tdigest()
        info = None
        try:
            info = tdigest.info(self.key)
        except ResponseError:
            if not self.exists():
                return
            raise
        return info


    @deferrable
    def add(self, values, **kwargs):
        tdigest = self.get_redis_or_pipe(**kwargs).tdigest()
        if not isinstance(values, list):
            values = [values]
        if not self.exists(cached=True):
            tdigest.create(self.key)
        tdigest.add(self.key, values)


    @deferrable
    def trimmed_mean(self, low_cut_quantile=0.2, high_cut_quantile=0.8, **kwargs):
        tdigest = self.get_redis_or_pipe(**kwargs).tdigest()
        if low_cut_quantile > 1:
            low_cut_quantile = low_cut_quantile / 100

        if high_cut_quantile > 1:
            high_cut_quantile = high_cut_quantile / 100

        result = tdigest.trimmed_mean(
            self.key,
            low_cut_quantile,
            high_cut_quantile,
        )
        # TODO: confirm result is number else return None
        return result


    @deferrable
    def quantile(self, value, **kwargs):
        tdigest = self.get_redis_or_pipe(**kwargs).tdigest()
        if value > 1:
            value = value / 100
        result = tdigest.quantile(self.key, value)
        # TODO: confirm result is number else return None
        return result



    @deferrable
    def percentile(self, value, **kwargs):
        result = self.quantile(value, **kwargs)
        # TODO: confirm result is number else return None
        return result


    @deferrable
    def min(self, **kwargs):
        tdigest = self.get_redis_or_pipe(**kwargs).tdigest()
        result = tdigest.min(self.key)
        # TODO: confirm result is number else return None
        return result


    @deferrable
    def max(self, **kwargs):
        tdigest = self.get_redis_or_pipe(**kwargs).tdigest()
        result = tdigest.max(self.key)
        # TODO: confirm result is number else return None
        return result


    @deferrable
    def reset(self, **kwargs):
        tdigest = self.get_redis_or_pipe(**kwargs).tdigest()
        tdigest.reset(self.key)




class Counter(Metric):

    @deferrable
    def incr(self, amount=1, **kwargs):
        redis = self.get_redis_or_pipe(**kwargs)
        redis.incr(
            self.key,
            amount=amount,
        )
        self.expire()


    @deferrable
    def get(self, **kwargs):
        redis = self.get_redis_or_pipe(**kwargs)
        value = redis.get(self.key)
        return value




class Gauge(Metric):

    @deferrable
    def incr(self, amount=1, **kwargs):
        redis = self.get_redis_or_pipe(**kwargs)
        redis.incr(
            self.key,
            amount=amount,
        )
        self.expire()


    @deferrable
    def decr(self, amount=1, **kwargs):
        redis = self.get_redis_or_pipe(**kwargs)
        redis.decr(
            self.key,
            amount=amount,
        )


    @deferrable
    def get(self, **kwargs):
        redis = self.get_redis_or_pipe(**kwargs)
        value = redis.get(self.key)
        return value




class PositiveGauge(Metric):

    @deferrable
    def incr(self, amount=1, **kwargs):
        redis = self.get_redis_or_pipe(**kwargs)
        redis.incr(
            self.key,
            amount=amount,
        )
        self.expire()


    @deferrable
    def decr(self, amount=1, **kwargs):
        script = """
        local key = KEYS[1]
        local decrby = tonumber(ARGV[1])
        local value = redis.call('GET', key)

        if value == false then
            value = 0
        else
            value = tonumber(value)
        end
        local new_value = value - decrby

        if new_value >= 0 then
            redis.call('DECRBY', key, decrby)
        else
            redis.call('SET', key, 0)
        end
        """
        numkeys = 1
        redis = self.get_redis_or_pipe(**kwargs)
        redis.eval(script, numkeys, self.key, amount)


    @deferrable
    def get(self, **kwargs):
        redis = self.get_redis_or_pipe(**kwargs)
        return redis.get(self.key)





class GaugeTS(Timeseries):

    @deferrable
    def incr(self, value=1, **kwargs):
        redis = self.get_redis_or_pipe(**kwargs)
        ts = redis.ts()
        ts.incrby(self.key, value)


    @deferrable
    def decr(self, value=1, **kwargs):
        redis = self.get_redis_or_pipe(**kwargs)
        ts = redis.ts()
        ts.decrby(self.key, value)




class PositiveGaugeTS(Timeseries):

    @deferrable
    def incr(self, value=1, **kwargs):
        redis = self.get_redis_or_pipe(**kwargs)
        ts = redis.ts()
        ts.incrby(self.key, value)


    @deferrable
    def decr(self, value=1, **kwargs):
        script = """
        local key = KEYS[1]
        local decrby = tonumber(ARGV[1])

        local value_tbl = redis.call('TS.GET', key)
        local length = #value_tbl
        local value = 0

        -- Check if this is an empty timeseries.
        if length == 0 or length == nil then
            -- Empty timeseries
            value = 0
        else
            value = value_tbl[2]
            for k, v in pairs(value) do
                value = v
            end
        end

        value = tonumber(value)
        local new_value = value - decrby

        if new_value >= 0 then
            return redis.call('TS.DECRBY', key, decrby)
        else
            return redis.call('TS.ADD', key, '*', 0)
        end
        """
        # If we don't do this beforehand the script will fail.
        if not self.exists(cached=True):
            self.ts.create(
                key=self.key,
                retention_msecs=self.retention_msecs,
            )
        numkeys = 1
        redis = self.get_redis_or_pipe(**kwargs)

        # TODO REVIEW: Potentially catch ResponseError here
        redis.eval(script, numkeys, self.key, value)
