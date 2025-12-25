
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, Optional

import pytz


IST = pytz.timezone("Asia/Kolkata")


def now_ist() -> dt.datetime:
    return dt.datetime.now(tz=IST)


def to_ist(ts: dt.datetime) -> dt.datetime:
    if ts.tzinfo is None:
        return IST.localize(ts)
    return ts.astimezone(IST)


def floor_time(ts: dt.datetime, minutes: int) -> dt.datetime:
    ts = to_ist(ts)
    discard = dt.timedelta(minutes=ts.minute % minutes, seconds=ts.second, microseconds=ts.microsecond)
    return ts - discard


def next_weekly_expiry(base: dt.date, weekday: int = 3) -> dt.date:
    '''
    Weekly expiry default: Thursday (weekday=3).
    If today is after expiry weekday, move to next week.
    '''
    days_ahead = (weekday - base.weekday()) % 7
    expiry = base + dt.timedelta(days=days_ahead)
    if expiry < base:
        expiry = expiry + dt.timedelta(days=7)
    return expiry


def format_nfo_expiry(expiry: dt.date) -> str:
    # Standard broker symbol formats vary; resolver adapts.
    return expiry.strftime("%y%m%d")
