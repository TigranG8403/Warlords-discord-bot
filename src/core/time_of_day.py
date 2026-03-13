from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, TypeVar


DayPeriod = Literal["morning", "day", "evening", "night"]
T = TypeVar("T")

_PERIOD_FALLBACKS: dict[DayPeriod, tuple[DayPeriod, ...]] = {
    "morning": ("morning", "day", "evening", "night"),
    "day": ("day", "morning", "evening", "night"),
    "evening": ("evening", "day", "morning", "night"),
    "night": ("night", "evening", "day", "morning"),
}


def period_key(current_time: dt.datetime) -> DayPeriod:
    hour = current_time.hour
    if 6 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 17:
        return "day"
    if 18 <= hour <= 22:
        return "evening"
    return "night"


def period_fallbacks(current_time: dt.datetime) -> tuple[DayPeriod, ...]:
    return _PERIOD_FALLBACKS[period_key(current_time)]


def pick_by_period(current_time: dt.datetime, values: Mapping[DayPeriod, T | None]) -> T | None:
    for period in period_fallbacks(current_time):
        value = values.get(period)
        if value is not None:
            return value
    return None


def pick_banner_asset_path(*, assets_dir: Path, stem: str, current_time: dt.datetime) -> Path | None:
    return pick_by_period(
        current_time,
        {
            "morning": _existing_path(assets_dir / f"{stem}_morning_1500x500.png"),
            "day": _existing_path(assets_dir / f"{stem}_day_1500x500.png"),
            "evening": _existing_path(assets_dir / f"{stem}_evening_1500x500.png"),
            "night": _existing_path(assets_dir / f"{stem}_night_1500x500.png"),
        },
    )


def _existing_path(path: Path) -> Path | None:
    if path.exists():
        return path
    return None
