import random

import pytest

from metric_helper import metrics, chunk, pipeline

metric = metrics.get('app:tdigest', 'tdigest')




def gen_latencies(num_responses=1000, min_time=50.0, max_time=5000.0):
    return [random.uniform(min_time, max_time) for _ in range(num_responses)]




def test_add():
    values = gen_latencies()
    chunks = chunk(values, 200)
    for part in chunks:
        metric.add(part)




def test_trimmed_mean():
    metric.trimmed_mean()
    metric.trimmed_mean(40, 80)




def test_quantile():
    metric.quantile(99)




def test_min():
    metric.min()




def test_max():
    metric.max()




def test_pipeline():
    results = pipeline([
        metric.add(200, defer=True),
        metric.trimmed_mean(defer=True),
        metric.trimmed_mean(40, 80, defer=True),
        metric.quantile(99, defer=True),
        metric.percentile(99, defer=True),
        metric.min(defer=True),
        metric.max(defer=True),
    ])




def test_reset():
    metric.reset()



def test_delete():
    metric.delete()
    assert metric.exists() is False
