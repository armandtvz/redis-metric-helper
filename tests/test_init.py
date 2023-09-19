from datetime import datetime, timedelta

import pytest

from metric_helper import metrics
from metric_helper.conf import settings




# def setup_function():
#     metrics.setup()
#
#
#
#
#
# def teardown_function():
#     metrics.setup()




def test_setup():
    metrics.setup()
    metrics.setup(
        connection_dict={},
        trim_ms=True,
        timezone='Africa/Johannesburg',
    )
    metrics.setup()
    metrics.setup()




def test_get():
    with pytest.raises(ValueError):
        metrics.get('app:sent', 'nonexistent_metric_type')




def test_metrics_ask():
    periods = [
        '24h',
        '30m',
        '3600s',
    ]
    for period in periods:
        metrics.ask('app:sent', period=period, gt=30)
        metrics.ask('app:sent', period=period, lt=30)
        metrics.ask('app:sent', period=period, ge=30)
        metrics.ask('app:sent', period=period, gte=30)
        metrics.ask('app:sent', period=period, le=30)
        metrics.ask('app:sent', period=period, lte=30)
        metrics.ask('app:sent', period=period, eq=30)

        with pytest.raises(ValueError):
            metrics.ask('app:sent', period=period, nonexistent=30)

        with pytest.raises(ValueError):
            metrics.ask('app:sent', period=period, gt='30')

    with pytest.raises(ValueError):
        metrics.ask('app:sent', period='invalidperiod', eq=30)

    with pytest.raises(ValueError):
        metrics.ask('app:sent', period='24days', eq=30)

    metrics.ask('app:sent', period='today', gt=30)
    metrics.ask('app:sent', period='week', gt=30)
    metrics.ask('app:sent', period='month', gt=30)
    metrics.ask('app:sent', period='year', gt=30)
