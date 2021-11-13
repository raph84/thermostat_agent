'''
pip install -U pytest

> pytest
'''

from .utils import utcnow, ceil_dt, tz, utc_to_toronto
from datetime import datetime
from pytz import timezone
import pytz


def test_ceil_dt_15():
    dt = utcnow().replace(minute=12)
    test = ceil_dt(dt, 15)
    assert test.minute == 15
    assert test.tzinfo == tz


def test_ceil_dt_30():
    dt = utcnow().replace(minute=22)
    test = ceil_dt(dt, 15)
    assert test.minute == 30
    assert test.tzinfo == tz


def test_ceil_dt_45():
    dt = utcnow().replace(minute=33)
    test = ceil_dt(dt, 15)
    assert test.minute == 45
    assert test.tzinfo == tz


def test_ceil_dt_00():
    dt = utcnow().replace(minute=46)
    test = ceil_dt(dt, 15)
    assert test.minute == 0
    assert test.tzinfo == tz

def test_naive_to_toronto():
    dt = datetime.strptime("20201223 101010","%Y%m%d %H%M%S")
    assert dt.tzinfo is None

    dt = utc_to_toronto(dt)

    assert dt.tzname() == 'EST'

    assert datetime.utcoffset(dt).seconds == 68400


def test_naive_to_toronto():
    dt = pytz.timezone('America/Chicago').localize(datetime.strptime("20201223 101010", "%Y%m%d %H%M%S"))

    assert dt.tzinfo is not None

    dt = utc_to_toronto(dt)

    assert dt.tzname() == 'EST'

    assert datetime.utcoffset(dt).seconds == 68400