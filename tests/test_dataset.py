import statistics as stats

import pytest

from metric_helper.dataset import Dataset


timestamps = [
    1694165001169,
    1694165002731,
    1694165003737,
    1694165015149,
    1694165016183,
]
values = [
    1,
    4,
    9,
    16,
    25,
]

@pytest.fixture
def sample_data():
    return [
        (1694165001169, 1),
        (1694165002731, 4),
        (1694165003737, 9),
        (1694165015149, 16),
        (1694165016183, 25),
    ]


@pytest.fixture
def data(sample_data):
    return Dataset(sample_data)


def test_init(data, sample_data):
    assert isinstance(data, Dataset)
    assert data.data == sample_data


def test_init_with_non_list():
    with pytest.raises(TypeError):
        Dataset('not_a_list')


def test_str(data):
    assert str(data) == str(data.data)


def test_iter(data, sample_data):
    for index, value in enumerate(data):
        assert value == sample_data[index]


def test_len(data, sample_data):
    assert len(data) == len(sample_data)


def test_values(data):
    assert data.values == values


def test_timestamps(data):
    assert data.timestamps == timestamps


def test_stdev(data):
    data.stdev


def test_variance(data):
    data.variance


def test_mean(data):
    data.mean


def test_avg(data):
    data.avg


def test_median(data):
    data.median


def test_mode(data):
    data.mode


def test_percentile(data):
    data.percentile(99)


def test_count(data):
    data.count()


def test_min(data):
    data.min()


def test_max(data):
    data.max()


def test_subscriptable(data):
    assert data[0] == (1694165001169, 1)
