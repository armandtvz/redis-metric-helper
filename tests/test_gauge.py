import random

import pytest

from metric_helper import metrics, chunk, pipeline

metric = metrics.get('normal_gauge', 'gauge')



def test_gauge():
    metric.decr()
    metric.incr()
    value = metric.get()
