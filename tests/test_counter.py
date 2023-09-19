import random

import pytest

from metric_helper import metrics, chunk, pipeline

metric = metrics.get('counter', 'counter')



def test_counter():
    metric.incr()
    value = metric.get()
