from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


UTC = dt.timezone.utc


def _build_moscow_timezone() -> dt.tzinfo:
    try:
        return ZoneInfo("Europe/Moscow")
    except ZoneInfoNotFoundError:
        return dt.timezone(dt.timedelta(hours=3))


MOSCOW_TIMEZONE = _build_moscow_timezone()


def get_moscow_time() -> dt.datetime:
    return dt.datetime.now(MOSCOW_TIMEZONE)


def get_utc_time() -> dt.datetime:
    return dt.datetime.now(UTC)


def convert_to_moscow(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(MOSCOW_TIMEZONE)
