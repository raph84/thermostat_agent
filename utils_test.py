from utils import utcnow, minute_floor, ceil_dt,tz


def test_15():
    dt = utcnow().replace(minute=12)
    test = ceil_dt(dt, 15)
    assert test.minute == 15
    assert test.tzinfo == tz


def test_30():
    dt = utcnow().replace(minute=22)
    test = ceil_dt(dt, 15)
    assert test.minute == 30
    assert test.tzinfo == tz


def test_45():
    dt = utcnow().replace(minute=33)
    test = ceil_dt(dt, 15)
    assert test.minute == 45
    assert test.tzinfo == tz


def test_00():
    dt = utcnow().replace(minute=46)
    test = ceil_dt(dt, 15)
    assert test.minute == 0
    assert test.tzinfo == tz