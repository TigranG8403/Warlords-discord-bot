from __future__ import annotations

import sqlite3

from .config import (
    DiscordAuthActivityHistoryPoint,
    DiscordAuthDashboardMetrics,
    DiscordAuthDashboardSummary,
    DiscordAuthOnlineHistoryPoint,
    DiscordAuthSanctionHistoryPoint,
)


METRICS_BUCKET_SECONDS = 5 * 60
ONLINE_HISTORY_HOURS = 24
ACTIVITY_HISTORY_DAYS = 7
SANCTION_HISTORY_DAYS = 7


class DiscordAuthDashboardMixin:
    def build_dashboard_summary(self) -> DiscordAuthDashboardSummary:
        settings = self.get_primary_guild_settings()
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            now = self._now()
            counts = self._collect_counts_locked(connection)
            self._record_metrics_snapshot_locked(connection, now, counts=counts)
        return DiscordAuthDashboardSummary(
            total_players=counts["total_players"],
            configured=settings is not None,
            guild_id=settings.guild_id if settings is not None else None,
            verify_role_id=settings.verify_role_id if settings is not None else None,
            start_message_channel_id=settings.start_message_channel_id if settings is not None else None,
            admin_command_channel_id=settings.admin_command_channel_id if settings is not None else None,
            admin_command_role_id=settings.admin_command_role_id if settings is not None else None,
            linked_players=counts["linked_players"],
            pending_codes=counts["pending_codes"],
            active_sessions=counts["active_sessions"],
            online_players=counts["online_players"],
            blocked_players=counts.get("blocked_players", 0),
            temp_banned_players=counts.get("temp_banned_players", 0),
        )

    def build_dashboard_metrics(self) -> DiscordAuthDashboardMetrics:
        now = self._now()
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            counts = self._collect_counts_locked(connection)
            self._record_metrics_snapshot_locked(connection, now, counts=counts)
            online_history = self._build_online_history_locked(connection, now)
            activity_history = self._build_activity_history_locked(connection, now)
            sanction_history = self._build_sanction_history_locked(connection, now)

        peak_online = max((point.online_players for point in online_history), default=counts["online_players"])
        return DiscordAuthDashboardMetrics(
            online_now=counts["online_players"],
            peak_online_24h=max(peak_online, counts["online_players"]),
            last_sample_at=now,
            online_history=tuple(online_history),
            activity_history=tuple(activity_history),
            sanction_history=tuple(sanction_history),
        )

    def build_sanction_history(self) -> tuple[DiscordAuthSanctionHistoryPoint, ...]:
        now = self._now()
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            return tuple(self._build_sanction_history_locked(connection, now))

    def _collect_counts_locked(self, connection: sqlite3.Connection) -> dict[str, int]:
        now = self._now()
        return {
            "total_players": int(
                connection.execute(
                    "SELECT COUNT(*) AS count_value FROM player_records"
                ).fetchone()["count_value"]
            ),
            "linked_players": int(
                connection.execute(
                    "SELECT COUNT(*) AS count_value FROM player_records WHERE discord_user_id != 0"
                ).fetchone()["count_value"]
            ),
            "pending_codes": int(
                connection.execute("SELECT COUNT(*) AS count_value FROM link_codes").fetchone()["count_value"]
            ),
            "active_sessions": int(
                connection.execute(
                    "SELECT COUNT(*) AS count_value FROM login_sessions WHERE status = 'PENDING'"
                ).fetchone()["count_value"]
            ),
            "online_players": int(
                connection.execute(
                    "SELECT COUNT(*) AS count_value FROM player_records WHERE is_online = 1"
                ).fetchone()["count_value"]
            ),
            "blocked_players": int(
                connection.execute(
                    "SELECT COUNT(*) AS count_value FROM player_records WHERE access_state = 'BLOCKED'"
                ).fetchone()["count_value"]
            ),
            "temp_banned_players": int(
                connection.execute(
                    "SELECT COUNT(*) AS count_value FROM player_records WHERE temp_ban_until > ?",
                    (now,),
                ).fetchone()["count_value"]
            ),
        }

    def _record_metrics_snapshot_locked(
        self,
        connection: sqlite3.Connection,
        now: int,
        *,
        counts: dict[str, int] | None = None,
    ) -> None:
        snapshot = counts or self._collect_counts_locked(connection)
        bucket_start = now - (now % METRICS_BUCKET_SECONDS)
        connection.execute(
            """
            INSERT INTO metrics_snapshots (
                bucket_start,
                total_players,
                linked_players,
                pending_codes,
                active_sessions,
                online_players,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bucket_start) DO UPDATE SET
                total_players = excluded.total_players,
                linked_players = excluded.linked_players,
                pending_codes = excluded.pending_codes,
                active_sessions = excluded.active_sessions,
                online_players = excluded.online_players,
                updated_at = excluded.updated_at
            """,
            (
                bucket_start,
                snapshot["total_players"],
                snapshot["linked_players"],
                snapshot["pending_codes"],
                snapshot["active_sessions"],
                snapshot["online_players"],
                now,
            ),
        )

    def _record_event_locked(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        player_uuid: str,
        player_name: str,
        now: int,
        *,
        reason: str = "",
        expires_at: int = 0,
    ) -> None:
        connection.execute(
            """
            INSERT INTO auth_events (event_type, player_uuid, player_name, reason, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_type.strip().lower(), player_uuid, player_name, reason.strip(), max(int(expires_at), 0), now),
        )

    def _build_online_history_locked(
        self,
        connection: sqlite3.Connection,
        now: int,
    ) -> list[DiscordAuthOnlineHistoryPoint]:
        current_hour = now - (now % 3600)
        start_hour = current_hour - ((ONLINE_HISTORY_HOURS - 1) * 3600)
        rows = connection.execute(
            """
            SELECT bucket_start, online_players
            FROM metrics_snapshots
            WHERE bucket_start >= ?
            ORDER BY bucket_start ASC
            """,
            (start_hour - 3600,),
        ).fetchall()

        by_hour: dict[int, int] = {}
        for row in rows:
            hour_bucket = int(row["bucket_start"]) - (int(row["bucket_start"]) % 3600)
            by_hour[hour_bucket] = max(by_hour.get(hour_bucket, 0), int(row["online_players"]))

        points: list[DiscordAuthOnlineHistoryPoint] = []
        last_value = 0
        for index in range(ONLINE_HISTORY_HOURS):
            hour_bucket = start_hour + (index * 3600)
            if hour_bucket in by_hour:
                last_value = by_hour[hour_bucket]
            points.append(
                DiscordAuthOnlineHistoryPoint(
                    timestamp=hour_bucket,
                    online_players=last_value,
                )
            )
        return points

    def _build_activity_history_locked(
        self,
        connection: sqlite3.Connection,
        now: int,
    ) -> list[DiscordAuthActivityHistoryPoint]:
        current_day = now - (now % 86400)
        start_day = current_day - ((ACTIVITY_HISTORY_DAYS - 1) * 86400)
        rows = connection.execute(
            """
            SELECT event_type, created_at
            FROM auth_events
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (start_day,),
        ).fetchall()

        day_counts: dict[int, dict[str, int]] = {}
        for row in rows:
            event_type = str(row["event_type"]).strip().lower()
            if event_type not in {"login", "link"}:
                continue
            day_bucket = int(row["created_at"]) - (int(row["created_at"]) % 86400)
            stats = day_counts.setdefault(day_bucket, {"login": 0, "link": 0})
            stats[event_type] += 1

        points: list[DiscordAuthActivityHistoryPoint] = []
        for index in range(ACTIVITY_HISTORY_DAYS):
            day_bucket = start_day + (index * 86400)
            stats = day_counts.get(day_bucket, {"login": 0, "link": 0})
            points.append(
                DiscordAuthActivityHistoryPoint(
                    timestamp=day_bucket,
                    login_count=stats["login"],
                    link_count=stats["link"],
                )
            )
        return points

    def _build_sanction_history_locked(
        self,
        connection: sqlite3.Connection,
        now: int,
    ) -> list[DiscordAuthSanctionHistoryPoint]:
        current_day = now - (now % 86400)
        start_day = current_day - ((SANCTION_HISTORY_DAYS - 1) * 86400)
        rows = connection.execute(
            """
            SELECT event_type, created_at
            FROM auth_events
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (start_day,),
        ).fetchall()

        day_counts: dict[int, int] = {}
        for row in rows:
            event_type = str(row["event_type"]).strip().lower()
            if event_type not in {"ban", "tempban"}:
                continue
            day_bucket = int(row["created_at"]) - (int(row["created_at"]) % 86400)
            day_counts[day_bucket] = day_counts.get(day_bucket, 0) + 1

        points: list[DiscordAuthSanctionHistoryPoint] = []
        for index in range(SANCTION_HISTORY_DAYS):
            day_bucket = start_day + (index * 86400)
            points.append(
                DiscordAuthSanctionHistoryPoint(
                    timestamp=day_bucket,
                    moderation_count=day_counts.get(day_bucket, 0),
                )
            )
        return points
