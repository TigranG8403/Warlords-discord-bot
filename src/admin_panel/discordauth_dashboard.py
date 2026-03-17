from __future__ import annotations

import time
from urllib.parse import urlencode

from .render import (
    DiscordAuthChartPointView,
    DiscordAuthEventView,
    DiscordAuthMetricsView,
    DiscordAuthPlayerView,
    DiscordAuthSummaryView,
)
from modules.discordauth.service import DiscordAuthService

VALID_DISCORDAUTH_FILTERS = {"all", "linked", "blocked", "banned", "pending", "online"}

def _format_unix_timestamp(timestamp: int) -> str:
    if timestamp <= 0:
        return "Не было"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def _normalize_discordauth_filter(filter_value: str) -> str:
    normalized = filter_value.strip().lower()
    return normalized if normalized in VALID_DISCORDAUTH_FILTERS else "all"


def build_dashboard_location(
    *,
    tab: str = "server",
    player_uuid: str = "",
    search: str = "",
    filter_value: str = "all",
) -> str:
    params: list[tuple[str, str]] = []
    if tab:
        params.append(("tab", "panel" if tab == "panel" else "server"))
    if player_uuid:
        params.append(("player_uuid", player_uuid))
    if search:
        params.append(("discordauth_search", search))
    normalized_filter = _normalize_discordauth_filter(filter_value)
    if normalized_filter != "all":
        params.append(("discordauth_filter", normalized_filter))
    query = urlencode(params)
    return f"/?{query}" if query else "/"


def _build_access_view(access_state: str) -> tuple[str, str]:
    normalized = access_state.strip().upper()
    mapping = {
        "AUTO": ("По роли", "player-tag-auto"),
        "ALLOWED": ("Разрешён", "player-tag-allowed"),
        "BLOCKED": ("Запрещён", "player-tag-blocked"),
    }
    return mapping.get(normalized, ("Неизвестно", "player-tag-muted"))


def _matches_discordauth_filter(player: DiscordAuthPlayerView, filter_value: str) -> bool:
    if filter_value == "linked":
        return player.linked
    if filter_value == "blocked":
        return player.access_state == "BLOCKED"
    if filter_value == "banned":
        return player.temp_ban_active
    if filter_value == "pending":
        return player.pending_session_active
    if filter_value == "online":
        return player.is_online
    return True


def _build_restriction_event_view(event) -> DiscordAuthEventView:
    event_type = str(getattr(event, "event_type", "")).strip().lower()
    player_name = str(getattr(event, "player_name", "")).strip() or str(getattr(event, "player_uuid", "")).strip() or "Игрок"
    reason = str(getattr(event, "reason", "")).strip()
    expires_at = int(getattr(event, "expires_at", 0) or 0)
    created_at = int(getattr(event, "created_at", 0) or 0)

    if event_type == "ban":
        title = f"Перманентный бан: {player_name}"
        subtitle = _format_unix_timestamp(created_at)
        badge_class = "player-tag-blocked"
    elif event_type == "unban":
        title = f"Снят бан: {player_name}"
        subtitle = _format_unix_timestamp(created_at)
        badge_class = "player-tag-allowed"
    elif event_type == "tempban":
        until_label = _format_unix_timestamp(expires_at)
        title = f"Темпбан: {player_name}"
        subtitle = f"До {until_label}"
        badge_class = "player-tag-warn"
    elif event_type == "tempunban":
        title = f"Снят темпбан: {player_name}"
        subtitle = _format_unix_timestamp(created_at)
        badge_class = "player-tag-allowed"
    else:
        title = player_name
        subtitle = _format_unix_timestamp(created_at)
        badge_class = "player-tag-muted"

    return DiscordAuthEventView(
        event_type=event_type,
        title=title,
        subtitle=subtitle,
        reason=reason,
        badge_class=badge_class,
    )


def build_discordauth_dashboard(
    *,
    search: str,
    filter_value: str,
    selected_player_uuid: str | None,
) -> tuple[
    DiscordAuthSummaryView | None,
    DiscordAuthMetricsView | None,
    tuple[DiscordAuthPlayerView, ...],
    DiscordAuthPlayerView | None,
    tuple[DiscordAuthEventView, ...],
    tuple[DiscordAuthEventView, ...],
]:
    try:
        from modules.discordauth.service import DiscordAuthService
    except ImportError:
        return None, None, (), None, (), ()

    try:
        service = DiscordAuthService()
        summary = service.build_dashboard_summary()
        metrics = service.build_dashboard_metrics()
        players = service.list_players()
        pending_sessions = service.list_pending_login_sessions()
        recent_restrictions = service.list_recent_restrictions(limit=10)
    except Exception:
        fallback = DiscordAuthSummaryView(
            total_players=0,
            linked_players=0,
            pending_codes=0,
            active_sessions=0,
            online_players=0,
        )
        return fallback, None, (), None, (), ()

    pending_by_player: dict[str, object] = {}
    for pending_session in pending_sessions:
        pending_by_player.setdefault(pending_session.player_uuid, pending_session)

    normalized_search = search.strip().casefold()
    normalized_filter = _normalize_discordauth_filter(filter_value)
    player_views: list[DiscordAuthPlayerView] = []
    for player in players:
        access_label, badge_class = _build_access_view(player.access_state)
        pending_session = pending_by_player.get(player.player_uuid)
        pending_session_id = getattr(pending_session, "session_id", None)
        pending_session_active = pending_session is not None
        pending_session_label = (
            f"Ждёт подтверждения до {_format_unix_timestamp(int(getattr(pending_session, 'expires_at', 0)))}"
            if pending_session_active
            else "Нет активного запроса"
        )
        pending_ip = str(getattr(pending_session, "ip_address", "")).strip()
        pending_address = str(getattr(pending_session, "address", "")).strip()
        discord_label_parts = []
        if player.discord_display_name:
            discord_label_parts.append(player.discord_display_name)
        if player.discord_username and player.discord_username != player.discord_display_name:
            discord_label_parts.append(f"@{player.discord_username}")
        discord_label_parts.append(str(player.discord_user_id or "—"))
        view = DiscordAuthPlayerView(
            player_uuid=player.player_uuid,
            player_name=player.player_name,
            discord_user_id=str(player.discord_user_id or ""),
            discord_label=" · ".join(part for part in discord_label_parts if part),
            discord_profile_url=(
                f"https://discord.com/users/{player.discord_user_id}"
                if player.discord_user_id
                else None
            ),
            linked=player.linked,
            access_state=player.access_state,
            access_label=access_label,
            access_badge_class=badge_class,
            last_ip=player.last_ip,
            last_authenticated_label=_format_unix_timestamp(player.last_authenticated_at),
            pending_session_active=pending_session_active,
            pending_session_id=str(pending_session_id) if pending_session_id else None,
            pending_session_label=pending_session_label,
            pending_session_address=pending_ip or pending_address,
            temp_ban_active=player.temp_ban_until > int(time.time()),
            temp_ban_until_label=_format_unix_timestamp(player.temp_ban_until),
            temp_ban_reason=player.temp_ban_reason,
            block_reason=player.admin_note,
            is_online=player.is_online,
            online_since_label=_format_unix_timestamp(player.online_since),
            last_seen_label=_format_unix_timestamp(player.last_seen_at),
        )
        if normalized_search:
            search_blob = " ".join(
                (
                    view.player_name,
                    view.player_uuid,
                    view.discord_user_id,
                    view.discord_label,
                )
            ).casefold()
            if normalized_search not in search_blob:
                continue
        if not _matches_discordauth_filter(view, normalized_filter):
            continue
        player_views.append(view)

    player_views.sort(key=lambda item: (item.player_name.casefold(), item.player_uuid))
    selected_player = next((player for player in player_views if player.player_uuid == selected_player_uuid), None)
    summary_view = DiscordAuthSummaryView(
        total_players=summary.total_players,
        linked_players=summary.linked_players,
        pending_codes=summary.pending_codes,
        active_sessions=summary.active_sessions,
        online_players=summary.online_players,
        blocked_players=summary.blocked_players,
        temp_banned_players=summary.temp_banned_players,
    )
    metrics_view = DiscordAuthMetricsView(
        online_now=metrics.online_now,
        peak_online_24h=metrics.peak_online_24h,
        last_sample_label=_format_unix_timestamp(metrics.last_sample_at),
        online_history=tuple(
            DiscordAuthChartPointView(
                label=time.strftime("%H:%M", time.localtime(point.timestamp)),
                primary_value=point.online_players,
                title=f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(point.timestamp))}: {point.online_players}",
            )
            for point in metrics.online_history
        ),
        activity_history=tuple(
            DiscordAuthChartPointView(
                label=time.strftime("%d.%m", time.localtime(point.timestamp)),
                primary_value=point.login_count,
                secondary_value=point.link_count,
                title=time.strftime("%Y-%m-%d", time.localtime(point.timestamp)),
            )
            for point in metrics.activity_history
        ),
        sanction_history=tuple(
            DiscordAuthChartPointView(
                label=time.strftime("%d.%m", time.localtime(point.timestamp)),
                primary_value=point.moderation_count,
                title=time.strftime("%Y-%m-%d", time.localtime(point.timestamp)),
            )
            for point in metrics.sanction_history
        ),
    )
    selected_restrictions = ()
    if selected_player is not None:
        selected_restrictions = tuple(
            _build_restriction_event_view(event)
            for event in service.list_recent_restrictions(limit=8, player_uuid=selected_player.player_uuid)
        )

    return (
        summary_view,
        metrics_view,
        tuple(player_views),
        selected_player,
        tuple(_build_restriction_event_view(event) for event in recent_restrictions),
        selected_restrictions,
    )
