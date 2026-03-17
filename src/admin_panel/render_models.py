from __future__ import annotations

from dataclasses import dataclass

from .git_ops import GitSnapshot


@dataclass(frozen=True)
class FlashMessage:
    level: str
    title: str
    output: str


@dataclass(frozen=True)
class LoginPageData:
    title: str
    error: str | None = None
    discord_login_url: str | None = None
    password_enabled: bool = False


@dataclass(frozen=True)
class CurrentUserView:
    user_id: str
    display_name: str
    username: str
    avatar_url: str | None


@dataclass(frozen=True)
class AllowedUserView:
    user_id: str
    display_name: str
    username: str
    avatar_url: str | None
    removable: bool = True


@dataclass(frozen=True)
class BotModuleCardView:
    name: str
    description: str
    state: str
    meta: str


@dataclass(frozen=True)
class DiscordAuthSummaryView:
    total_players: int
    linked_players: int
    pending_codes: int
    active_sessions: int
    online_players: int = 0
    blocked_players: int = 0
    temp_banned_players: int = 0


@dataclass(frozen=True)
class DiscordAuthChartPointView:
    label: str
    primary_value: int
    secondary_value: int = 0
    title: str = ""


@dataclass(frozen=True)
class DiscordAuthMetricsView:
    online_now: int
    peak_online_24h: int
    last_sample_label: str
    online_history: tuple[DiscordAuthChartPointView, ...] = ()
    activity_history: tuple[DiscordAuthChartPointView, ...] = ()
    sanction_history: tuple[DiscordAuthChartPointView, ...] = ()


@dataclass(frozen=True)
class DiscordAuthEventView:
    event_type: str
    title: str
    subtitle: str
    reason: str = ""
    badge_class: str = "player-tag-muted"


@dataclass(frozen=True)
class DiscordAuthPlayerView:
    player_uuid: str
    player_name: str
    discord_user_id: str
    discord_label: str
    discord_profile_url: str | None
    linked: bool
    access_state: str
    access_label: str
    access_badge_class: str
    last_ip: str
    last_authenticated_label: str
    pending_session_active: bool
    pending_session_id: str | None
    pending_session_label: str
    pending_session_address: str
    temp_ban_active: bool
    temp_ban_until_label: str
    temp_ban_reason: str
    block_reason: str
    is_online: bool
    online_since_label: str
    last_seen_label: str


@dataclass(frozen=True)
class DashboardPageData:
    csrf_token: str
    service_name: str
    service_data: dict[str, str]
    git_data: GitSnapshot
    tracking_status: str
    logs: str
    flash: FlashMessage | None
    current_user: CurrentUserView | None
    allowed_users: tuple[AllowedUserView, ...]
    discord_auth_enabled: bool
    bot_modules: tuple[BotModuleCardView, ...] = ()
    active_tab: str = "server"
    discordauth_summary: DiscordAuthSummaryView | None = None
    discordauth_metrics: DiscordAuthMetricsView | None = None
    discordauth_players: tuple[DiscordAuthPlayerView, ...] = ()
    discordauth_selected_player: DiscordAuthPlayerView | None = None
    discordauth_recent_restrictions: tuple[DiscordAuthEventView, ...] = ()
    discordauth_selected_restrictions: tuple[DiscordAuthEventView, ...] = ()
    discordauth_search: str = ""
    discordauth_filter: str = "all"


HERO_DESCRIPTION = "Единая панель для управления сервером, ботом и привязками игроков."
