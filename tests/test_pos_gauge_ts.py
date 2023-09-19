import random

import pytest

from metric_helper import metrics, chunk, pipeline

metric = metrics.get('pos_gauge_ts', 'pos_gauge_ts')



def test_pos_gauge_ts():
    metric.decr(1)
    metric.incr(1)

    metric.decr()
    metric.incr()

    dt, value = metric.get()
