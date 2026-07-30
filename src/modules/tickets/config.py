from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

from core.clock import (
    convert_to_moscow as convert_to_msk,
    get_moscow_time as get_msk_time,
    get_utc_time,
)
from core.time_of_day import pick_banner_asset_path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = (PROJECT_ROOT / "data").resolve()
ASSETS_DIR = (PROJECT_ROOT / "assets").resolve()
DEFAULT_TICKETS_DATABASE_PATH = (DATA_DIR / "tickets.sqlite3").resolve()


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


def get_panel_banner_asset_path(current_time: datetime.datetime | None = None) -> Path | None:
    return pick_banner_asset_path(
        assets_dir=ASSETS_DIR,
        stem="minecraft",
        current_time=current_time or get_msk_time(),
    )
