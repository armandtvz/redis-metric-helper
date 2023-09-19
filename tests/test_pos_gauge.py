import random

import pytest

from metric_helper import metrics, chunk, pipeline

metric = metrics.get('pos_gauge', 'pos_gauge')



def test_pos_gauge():
    metric.decr()
    metric.incr()
    value = metric.get()
