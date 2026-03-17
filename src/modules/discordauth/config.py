from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

from core.time_of_day import pick_banner_asset_path
from modules.tickets.config import get_msk_time


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = (PROJECT_ROOT / "data").resolve()
ASSETS_DIR = (PROJECT_ROOT / "assets").resolve()
DEFAULT_DATABASE_PATH = (DATA_DIR / "discordauth.sqlite3").resolve()
LINK_CODE_TTL_SECONDS = 15 * 60
LOGIN_SESSION_TTL_SECONDS = 90


@dataclass(slots=True, frozen=True)
class DiscordAuthGuildSettings:
    guild_id: int
    verify_role_id: int
    start_message_channel_id: int
    admin_command_channel_id: int
    admin_command_role_id: int


@dataclass(slots=True, frozen=True)
class DiscordAuthPlayerRecord:
    player_uuid: str
    player_name: str
    discord_user_id: int = 0
    discord_username: str = ""
    discord_display_name: str = ""
    access_state: str = "AUTO"
    admin_status: str = ""
    temp_ban_until: int = 0
    temp_ban_reason: str = ""
    admin_note: str = ""
    last_ip: str = ""
    last_authenticated_at: int = 0
    is_online: bool = False
    online_since: int = 0
    last_seen_at: int = 0

    @property
    def linked(self) -> bool:
        return self.discord_user_id != 0


@dataclass(slots=True, frozen=True)
class LinkCodeRecord:
    code: str
    player_uuid: str
    player_name: str
    created_at: int
    expires_at: int


@dataclass(slots=True, frozen=True)
class LoginSessionRecord:
    session_id: str
    player_uuid: str
    player_name: str
    discord_user_id: int
    address: str
    ip_address: str
    status: str
    created_at: int
    expires_at: int
    message_id: int = 0

    @property
    def is_finished(self) -> bool:
        return self.status in {"APPROVED", "DENIED", "TIMEOUT", "DM_FAILED", "CANCELLED"}


@dataclass(slots=True, frozen=True)
class DiscordAuthDashboardSummary:
    total_players: int
    configured: bool
    guild_id: int | None
    verify_role_id: int | None
    start_message_channel_id: int | None
    admin_command_channel_id: int | None
    admin_command_role_id: int | None
    linked_players: int
    pending_codes: int
    active_sessions: int
    online_players: int = 0
    blocked_players: int = 0
    temp_banned_players: int = 0


@dataclass(slots=True, frozen=True)
class DiscordAuthPresenceRecord:
    player_uuid: str
    player_name: str
    ip_address: str = ""


@dataclass(slots=True, frozen=True)
class DiscordAuthOnlineHistoryPoint:
    timestamp: int
    online_players: int


@dataclass(slots=True, frozen=True)
class DiscordAuthActivityHistoryPoint:
    timestamp: int
    login_count: int
    link_count: int


@dataclass(slots=True, frozen=True)
class DiscordAuthSanctionHistoryPoint:
    timestamp: int
    moderation_count: int


@dataclass(slots=True, frozen=True)
class DiscordAuthEventRecord:
    event_type: str
    player_uuid: str
    player_name: str
    reason: str = ""
    expires_at: int = 0
    created_at: int = 0


@dataclass(slots=True, frozen=True)
class DiscordAuthDashboardMetrics:
    online_now: int
    peak_online_24h: int
    last_sample_at: int
    online_history: tuple[DiscordAuthOnlineHistoryPoint, ...]
    activity_history: tuple[DiscordAuthActivityHistoryPoint, ...]
    sanction_history: tuple[DiscordAuthSanctionHistoryPoint, ...] = ()


def get_panel_banner_asset_path(current_time: datetime.datetime | None = None) -> Path | None:
    return pick_banner_asset_path(
        assets_dir=ASSETS_DIR,
        stem="minecraft",
        current_time=current_time or get_msk_time(),
    )
