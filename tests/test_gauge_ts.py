import random

import pytest

from metric_helper import metrics, chunk, pipeline

metric = metrics.get('gauge_ts', 'gauge_ts')



def test_gauge_ts():
    metric.decr(1)
    metric.incr(1)

    metric.decr()
    metric.incr()

    dt, value = metric.get()
