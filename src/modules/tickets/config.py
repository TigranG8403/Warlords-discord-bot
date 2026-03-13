from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.time_of_day import pick_banner_asset_path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = (PROJECT_ROOT / "data").resolve()
ASSETS_DIR = (PROJECT_ROOT / "assets").resolve()
DEFAULT_TICKETS_DATABASE_PATH = (DATA_DIR / "tickets.sqlite3").resolve()
UTC = datetime.timezone.utc


def _build_msk_timezone() -> datetime.tzinfo:
    try:
        return ZoneInfo("Europe/Moscow")
    except ZoneInfoNotFoundError:
        return datetime.timezone(datetime.timedelta(hours=3))


MSK_TIMEZONE = _build_msk_timezone()


@dataclass(slots=True, frozen=True)
class TicketGuildSettings:
    guild_id: int
    ticket_category_id: int
    fraction_category_id: int
    rp_category_id: int
    log_channel_id: int
    support_role_id: int
    staff_call_cooldown_minutes: int = 5


@dataclass(slots=True)
class TicketsSettings:
    embed_color: int = 0x831818
    main_color: int = 0x831818
    rp_color: int = 0x27AE60
    fraction_color: int = 0x3498DB
    database_path: Path = DEFAULT_TICKETS_DATABASE_PATH


def load_tickets_settings() -> TicketsSettings:
    return TicketsSettings()


def get_msk_time() -> datetime.datetime:
    return datetime.datetime.now(MSK_TIMEZONE)


def get_utc_time() -> datetime.datetime:
    return datetime.datetime.now(UTC)


def convert_to_msk(utc_time: datetime.datetime) -> datetime.datetime:
    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=UTC)
    return utc_time.astimezone(MSK_TIMEZONE)


def get_panel_banner_asset_path(current_time: datetime.datetime | None = None) -> Path | None:
    return pick_banner_asset_path(
        assets_dir=ASSETS_DIR,
        stem="minecraft",
        current_time=current_time or get_msk_time(),
    )
