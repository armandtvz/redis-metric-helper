from datetime import datetime

import pytest

from metric_helper.conf import settings

from metric_helper import timezone as tz




def test_now():
    now = tz.now()
    assert now.tzinfo is not None
    assert now.tzinfo.tzname(now) == settings.TIME_ZONE




# def test_override():
#     now = tz.now()
#     with pytest.raises(ValueError):
#         tz.make_aware(now)
#     dt = datetime(2023, 9, 5, 0, 0, 0)
#     assert dt.utcoffset() is None
#
#     dt = tz.make_aware(dt)
#     assert dt.utcoffset() is not None




def test_last_hour_range():
    start, end = tz.get_last_hour_range()
    assert start.tzinfo is not None
    assert end.tzinfo is not None




def test_last_week_daterange():
    start, end = tz.get_last_week_daterange()
    assert start.tzinfo is not None
    assert end.tzinfo is not None




def test_month_range():
    start, end = tz.get_month_range()

    with pytest.raises(ValueError):
        start, end = tz.get_month_range(month=0)

    with pytest.raises(ValueError):
        start, end = tz.get_month_range(month=13)

    start, end = tz.get_month_range(month=1)
    assert start.month == 1
    assert end.month == 1
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=2)
    assert start.month == 2
    assert end.month == 2
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=3)
    assert start.month == 3
    assert end.month == 3
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=4)
    assert start.month == 4
    assert end.month == 4
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=5)
    assert start.month == 5
    assert end.month == 5
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=6)
    assert start.month == 6
    assert end.month == 6
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=7)
    assert start.month == 7
    assert end.month == 7
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=8)
    assert start.month == 8
    assert end.month == 8
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=9)
    assert start.month == 9
    assert end.month == 9
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=10)
    assert start.month == 10
    assert end.month == 10
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=11)
    assert start.month == 11
    assert end.month == 11
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_month_range(month=12)
    assert start.month == 12
    assert end.month == 12
    assert start.tzinfo is not None
    assert end.tzinfo is not None




def test_year_range():
    start, end = tz.get_year_range()
    assert start.year == datetime.now().year
    assert end.year == datetime.now().year
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_year_range(year=1997)
    assert start.year == 1997
    assert end.year == 1997
    assert start.tzinfo is not None
    assert end.tzinfo is not None

    start, end = tz.get_year_range(year=2022)
    assert start.year == 2022
    assert end.year == 2022
    assert start.tzinfo is not None
    assert end.tzinfo is not None
