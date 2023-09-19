import calendar
from datetime import datetime, timezone, timedelta

import pytz

from metric_helper.conf import settings




def get_tz():
    return pytz.timezone(settings.TIME_ZONE)




def get_utc():
    return pytz.timezone('UTC')




# Copied and modified from:
# https://github.com/django/django/blob/main/django/utils/timezone.py#L211
def is_aware(value) -> bool:
    return value.utcoffset() is not None




def now():
    now_utc = datetime.now(tz=timezone.utc)
    tz = get_tz()
    return convert(now_utc, tz)




def override(value, tz):
    if is_aware(value):
        raise ValueError(f'"override_with_utc" expects a naive datetime, got {value.isoformat()}')
    if isinstance(tz, str):
        # This might already be a valid pytz timezone instance
        tz = pytz.timezone(tz)
    return tz.localize(value)




def convert(value, tz):
    if not is_aware(value):
        raise ValueError(f'"convert" expects an aware datetime, got {value.isoformat()}')
    if isinstance(tz, str):
        # This might already be a valid pytz timezone instance
        tz = pytz.timezone(tz)
    return value.astimezone(tz)




def fromtimestamp(value, ms=False):
    if not isinstance(value, (int, float,)):
        _type = type(value)
        raise ValueError(
            f'"fromtimestamp" expects an integer in milliseconds, got "{_type}".'
        )
    if ms:
        value = value / 1000

    naive = datetime.utcfromtimestamp(value)
    tz = get_tz()
    aware = override(naive, 'utc')
    return convert(aware, tz)








def get_last_hour_range():
    today = now()
    start = today.replace(
        hour=(today.hour - 1),
        minute=0,
        second=0,
        microsecond=0,
    )
    end = today.replace(
        hour=today.hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    return start, end




def get_week_daterange(today=None):
    if not today:
        today = now()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end.replace(hour=23, minute=59, second=59, microsecond=999_999)
    return start, end




def get_last_week_daterange(today=None):
    if not today:
        today = now()
    weekday_index = today.weekday()
    start = today - timedelta(days=(weekday_index + 7))
    end = start + timedelta(days=6)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end.replace(hour=23, minute=59, second=59, microsecond=999_999)
    return start, end




def get_month_range(month=None):
    today = now()
    if month is None:
        month = today.month
    year = today.year
    if not (0 < month <= 12):
        raise ValueError(
            f'Invalid value, "{month}", for "month". '
            f'Must be value of: "0 < month <= 12"'
        )

    _, last_day = calendar.monthrange(year, month)

    start = datetime(year=year, month=month, day=1, tzinfo=today.tzinfo)
    end = datetime(year=year, month=month, day=last_day, tzinfo=today.tzinfo)

    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end.replace(hour=23, minute=59, second=59, microsecond=999_999)
    return start, end




def get_year_range(year=None):
    today = now()
    if not year:
        year = today.year

    start = datetime(year=year, month=1, day=1, tzinfo=today.tzinfo)
    end = datetime(year=year, month=12, day=31, tzinfo=today.tzinfo)

    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end.replace(hour=23, minute=59, second=59, microsecond=999_999)
    return start, end
