from datetime import datetime, timedelta
import math
from pytz import timezone
import pytz
import pandas as pd

tz = timezone('America/Montreal')
tz_utc = timezone('UTC')


def ceil_dt(dt, delta):
    ceil = datetime.min + math.ceil(
        (dt.replace(tzinfo=None) - datetime.min) /
        timedelta(minutes=delta)) * timedelta(minutes=delta)

    return ceil.replace(tzinfo=tz)


def utcnow():
    return datetime.now(tz=timezone('America/Montreal'))

def get_tz():
    return tz


def get_utc_tz():
    return tz_utc
