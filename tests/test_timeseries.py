from datetime import datetime, timedelta

import pytest

from metric_helper.conf import settings
from metric_helper import (
    timezone,
    pipeline,
    metrics,
)
from tests.load import insert_data
from metric_helper.connections import get_redis

redis = get_redis()
metric = metrics.get('app:sent')
retention_seconds = 365 * 24 * 60 * 60
retention_msecs = retention_seconds * 1000
retention_delta = timedelta(hours=8760)

alternate_retention_seconds = retention_seconds * 2
alternate_retention_msecs = alternate_retention_seconds * 1000




def setup_function():
    metric.delete(everything=True)
    assert metric.retention() is None
    assert not metric.is_compaction

    insert_data(metric)

    assert metric.exists() is True
    assert metric.rules() == []
    assert metric.count() == 10
    assert metric.is_compaction is False

    metric.auto_add_rules()
    assert metric.rules() != []




def teardown_function():
    metric.delete(everything=True)
    assert metric.exists() is False
    assert metric.rules() == []




def test_create_if_not_exists():
    key = 'app:nonexistent'
    redis.delete(key)
    met = metrics.get(key)
    assert met.exists() is False

    met.add()
    assert met.exists() is True
    met.delete()
    assert met.exists() is False




def test_get_type():
    _type = metric.get_type()
    assert _type == 'TSDB-TYPE'




def test_backfill():
    metric.backfill()
    keys = [
        'app:sent',
        'app:sent--agg_60_sum',
        'app:sent--agg_900_sum',
        'app:sent--agg_3600_sum',
        'app:sent--agg_86400_sum',
    ]
    ts = redis.ts()
    counts = []
    for key in keys:
        data = ts.range(
            key=key,
            from_time='-',
            to_time='+',
            aggregation_type='sum',
            bucket_size_msec=86400,
        )
        counter = 0
        for item in data:
            counter += item[1]
        counts.append(counter)

    counts = set(counts)
    assert len(counts) == 1

    count = list(counts)[0]
    for key in keys:
        met = metrics.get(key)
        _count = met.count()
        assert _count == count




def test_rule_exists():
    rules = metric.rules()
    for rule in rules:
        assert rule.exists() is True
        _compacted_metric = metrics.get(rule.key)
        _compacted_metric.is_compaction is True




def test_rules_show_compacted():
    rules = metric.rules()
    for rule in rules:
        rule_metric = metrics.get(rule.key)
        assert rule_metric.is_compaction is True




def test_info():
    assert metric._info()
    assert metric.first_timestamp is not None
    assert metric.last_timestamp is not None




def test_get_retention():
    assert metric.retention() is not None




def test_add():
    metric.add()




def test_add_sample():
    metric.add_sample(value=1)
    metric.add_sample(value=1, round_timestamp_to='second')
    metric.add_sample(value=1, round_timestamp_to='minute')
    metric.add_sample(value=1, round_timestamp_to='hour')

    settings.TRIM_MS = True
    metric.add_sample(value=1)
    settings.TRIM_MS = False

    assert metric.exists() is True
    assert metric.is_compaction is False

    with pytest.raises(ValueError):
        metric.add_sample()




def test_pipeline():
    end = datetime.now()
    start = end - timedelta(hours=1)
    results = pipeline([
        metric.range(start='-', end='+', bucket_secs=3600, defer=True),
        metric.range(start=start, end=end, bucket_secs=3600, defer=True),
        metric.add_sample(value=1, defer=True),
        metric.add_sample(value=1, defer=True),
        metric.add(defer=True),
        metric.change_retention(retention_seconds, defer=True),
        metric.hour(defer=True),
        metric.hours(24, defer=True),
        metric.today(defer=True),
        metric.yesterday(defer=True),
        metric.days(7, defer=True),
        metric.last_week(defer=True),
        metric.month(defer=True),
        metric.year(defer=True),
        metric.get(defer=True),
    ])
    # with pytest.raises(TypeError):
    #     pipeline([
    #         metric.count(start=start, end=end),
    #     ])




def test_range():
    end = timezone.now()
    start = end - timedelta(hours=1)

    metric.range(
        start='-',
        end='+',
        bucket_secs=3600,
    )
    metric.range(start='-')
    metric.range(end='+')
    metric.range()

    with pytest.raises(ValueError):
        metric.range(
            start='+',
            end='+',
            bucket_secs=3600,
        )

    with pytest.raises(ValueError):
        metric.range(
            start='-',
            end='-',
            bucket_secs=3600,
        )

    with pytest.raises(ValueError):
        metric.range(agg_type='non_existent_aggregation')

    key = metric._get_best_key(7200)
    data = metric.hour()
    data = metric.hours(24)
    data = metric.today()
    data = metric.yesterday()
    data = metric.days(7)
    data = metric.last_week()
    data = metric.month()
    data = metric.year()

    count = metric.count(start=start, end=end)
    count = metric.count(start='-', end='+')

    for item in data:
        pass




def test_get():
    dt, value = metric.get()




def test_get_pages():
    bucket_size_msec = 60_000
    buckets_per_page = 200
    expected_distance = (bucket_size_msec * buckets_per_page) - 1

    pages = metric.get_pages(bucket_size_msec)
    for start, end in pages:
        diff = bucket_size_msec * buckets_per_page
        diff = diff - 1
        assert diff == expected_distance




def test_get_buckets():
    end = timezone.now()
    start = end - timedelta(hours=1)
    start = start.timestamp() * 1000
    end = end.timestamp() * 1000

    bucket_size = 60_000

    buckets = metric._get_buckets(start, end, bucket_size)
    for bucket in buckets:
        assert (bucket % bucket_size) == 0




def test_get_bucket_start():
    # 1917-08-29 20:45:33.796000
    start_msecs = -1651727666204

    # Expected: 1917-08-29 20:00:00
    hour = metric._get_bucket_start(start_msecs, 3_600_000)

    # Expected: 1917-08-29 20:45:00
    second = metric._get_bucket_start(start_msecs, 60_000)




def test_change_retention():
    metric.change_retention(retention_seconds)
    assert metric._info().retention_msecs == retention_msecs

    metric.change_retention(retention_delta)
    assert metric._info().retention_msecs == retention_msecs

    metrics.change_primary_retention(alternate_retention_seconds)
    assert metric._info().retention_msecs == alternate_retention_msecs




def test_expire():
    metric.expire(ttl_seconds=retention_seconds)
    metric.expire()
    ttl = metric.ttl()
    assert ttl == retention_seconds
