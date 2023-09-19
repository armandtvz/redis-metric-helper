"""
Only used for testing.

Example usage::

    data = generate(
        interval_secs=60,
        min_value=0,
        max_value=150,
    )
    print('Generated data:', data)
"""
import time
import random
from decimal import Decimal
from datetime import datetime, timedelta

from metric_helper import timezone
from metric_helper.conf import settings
from metric_helper.connections import get_redis

redis = get_redis()




def generate(
    start=None,
    end=None,
    interval_secs=3600,
    min_value=0,
    max_value=150,
):
    now = timezone.now()
    if not start:
        start = datetime(year=2023, month=8, day=15, hour=0, minute=0, second=0)
    if not end:
        end = datetime(year=2023, month=8, day=15, hour=10, minute=0, second=0)

    start = int(start.timestamp() * 1000)
    end = int(end.timestamp() * 1000)

    interval = interval_secs * 1000
    for timestamp in range(start, end, interval):
        value = 1
        timestamp = timestamp / 1000
        timestamp = datetime.fromtimestamp(timestamp)
        yield [timestamp, value]




def insert_data(metric):
    data = generate()
    buffer = []
    counter = 0
    for timestamp, value in data:
        counter += 1
        buffer.append([timestamp, value])
        if len(buffer) >= 8000:
            metric.bulk_add(buffer, duplicate_policy='first')
            buffer = []
    if len(buffer) != 0:
        counter += len(buffer)
        metric.bulk_add(buffer, duplicate_policy='first')
        buffer = []
