from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from .config import (
    ModerationEventRecord,
    ModerationGuildSettings,
    ModerationHistorySnapshot,
    ModerationKnownProfile,
    ModerationUserObservationSnapshot,
)


class ModerationRepository:
    _OBSERVATION_SAMPLE_LIMIT = 18
    _RECENT_HISTORY_EVENT_LIMIT = 8

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_guild_settings(
        self,
        guild_id: int,
        *,
        archive_channel_id: int,
        admin_alert_role_id: int | None = None,
        admin_alert_user_id: int | None = None,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO guild_settings (guild_id, archive_channel_id, admin_alert_role_id, admin_alert_user_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    archive_channel_id = excluded.archive_channel_id,
                    admin_alert_role_id = excluded.admin_alert_role_id,
                    admin_alert_user_id = excluded.admin_alert_user_id
                """,
                (guild_id, archive_channel_id, admin_alert_role_id, admin_alert_user_id),
            )

    def get_guild_settings(self, guild_id: int) -> ModerationGuildSettings | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT guild_id, archive_channel_id, admin_alert_role_id, admin_alert_user_id
                FROM guild_settings
                WHERE guild_id = ?
                """,
                (guild_id,),
            ).fetchone()

        if row is None:
            return None
        return ModerationGuildSettings(
            guild_id=int(row["guild_id"]),
            archive_channel_id=int(row["archive_channel_id"]),
            admin_alert_role_id=_optional_int(row["admin_alert_role_id"]),
            admin_alert_user_id=_optional_int(row["admin_alert_user_id"]),
        )

    def seed_known_profiles(self, profiles: Iterable[ModerationKnownProfile]) -> None:
        with self._connection() as connection:
            for profile in profiles:
                connection.execute(
                    """
                    INSERT INTO known_profiles (discord_id, primary_name, aliases, summary)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(discord_id) DO UPDATE SET
                        primary_name = excluded.primary_name,
                        aliases = excluded.aliases,
                        summary = excluded.summary
                    """,
                    (
                        profile.discord_id,
                        profile.primary_name,
                        ",".join(profile.aliases),
                        profile.summary,
                    ),
                )

    def get_known_profile(self, discord_id: int) -> ModerationKnownProfile | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT discord_id, primary_name, aliases, summary
                FROM known_profiles
                WHERE discord_id = ?
                """,
                (discord_id,),
            ).fetchone()

        if row is None:
            return None
        aliases = tuple(item for item in str(row["aliases"]).split(",") if item)
        return ModerationKnownProfile(
            discord_id=int(row["discord_id"]),
            primary_name=str(row["primary_name"]),
            aliases=aliases,
            summary=str(row["summary"]),
        )

    def list_known_profile_summaries(self, *, limit: int = 20) -> tuple[str, ...]:
        normalized_limit = max(1, min(limit, 50))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT discord_id, primary_name, aliases, summary
                FROM known_profiles
                ORDER BY primary_name COLLATE NOCASE ASC
                LIMIT ?
                """,
                (normalized_limit,),
            ).fetchall()

        summaries: list[str] = []
        for row in rows:
            aliases = [item for item in str(row["aliases"]).split(",") if item]
            alias_text = f" ({', '.join(aliases)})" if aliases else ""
            summaries.append(f"{row['primary_name']}{alias_text} — {row['summary']}")
        return tuple(summaries)

    def list_known_profiles(self, *, limit: int = 20) -> tuple[ModerationKnownProfile, ...]:
        normalized_limit = max(1, min(limit, 50))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT discord_id, primary_name, aliases, summary
                FROM known_profiles
                ORDER BY primary_name COLLATE NOCASE ASC
                LIMIT ?
                """,
                (normalized_limit,),
            ).fetchall()

        profiles: list[ModerationKnownProfile] = []
        for row in rows:
            aliases = tuple(item for item in str(row["aliases"]).split(",") if item)
            profiles.append(
                ModerationKnownProfile(
                    discord_id=int(row["discord_id"]),
                    primary_name=str(row["primary_name"]),
                    aliases=aliases,
                    summary=str(row["summary"]),
                )
            )
        return tuple(profiles)

    def record_user_observation(
        self,
        *,
        guild_id: int,
        user_id: int,
        author_name: str,
        role_names: tuple[str, ...],
        content: str,
        decision: str,
        addressed_to_bot: bool,
        labels: tuple[str, ...],
    ) -> None:
        normalized_content = " ".join(content.split())[:180]
        sample_parts = [normalized_content or "<пусто>"]
        if role_names:
            sample_parts.append(f"роли: {', '.join(role_names[:6])}")
        if decision != "allow":
            sample_parts.append(f"decision: {decision}")
        if labels:
            sample_parts.append(f"labels: {', '.join(labels[:6])}")
        if addressed_to_bot:
            sample_parts.append("адресовано боту")
        sample_line = " | ".join(sample_parts)

        with self._connection() as connection:
            existing = connection.execute(
                """
                SELECT total_messages, recent_samples
                FROM user_observations
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            ).fetchone()

            if existing is None:
                total_messages = 1
                samples = [sample_line]
                connection.execute(
                    """
                    INSERT INTO user_observations (
                        guild_id,
                        user_id,
                        last_seen_name,
                        role_names,
                        total_messages,
                        recent_samples,
                        ai_summary,
                        ai_summary_updated_at,
                        summary_message_count,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, '', 0, 0, ?)
                    """,
                    (
                        guild_id,
                        user_id,
                        author_name,
                        ", ".join(role_names[:8]),
                        total_messages,
                        "\n".join(samples),
                        int(time.time()),
                    ),
                )
                return

            total_messages = int(existing["total_messages"]) + 1
            samples = [item for item in str(existing["recent_samples"]).splitlines() if item]
            samples.append(sample_line)
            samples = samples[-self._OBSERVATION_SAMPLE_LIMIT :]
            connection.execute(
                """
                UPDATE user_observations
                SET last_seen_name = ?,
                    role_names = ?,
                    total_messages = ?,
                    recent_samples = ?,
                    updated_at = ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (
                    author_name,
                    ", ".join(role_names[:8]),
                    total_messages,
                    "\n".join(samples),
                    int(time.time()),
                    guild_id,
                    user_id,
                ),
            )

    def get_recent_user_samples(self, *, guild_id: int, user_id: int) -> tuple[str, ...]:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT recent_samples
                FROM user_observations
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            ).fetchone()

        if row is None:
            return ()
        return tuple(item for item in str(row["recent_samples"]).splitlines() if item)

    def describe_user_character(self, *, guild_id: int, user_id: int) -> str:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT ai_summary
                FROM user_observations
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            ).fetchone()

        if row is None:
            return ""
        return str(row["ai_summary"]).strip()

    def should_refresh_user_character(self, *, guild_id: int, user_id: int) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT total_messages, ai_summary, ai_summary_updated_at, summary_message_count
                FROM user_observations
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            ).fetchone()

        if row is None:
            return False

        total_messages = int(row["total_messages"])
        summary_message_count = int(row["summary_message_count"])
        ai_summary = str(row["ai_summary"]).strip()
        updated_at = int(row["ai_summary_updated_at"])
        now = int(time.time())

        if total_messages < 2:
            return False
        if not ai_summary:
            return True
        if total_messages - summary_message_count >= 2:
            return True
        return updated_at <= 0 or now - updated_at >= 6 * 60 * 60

    def save_user_character_summary(self, *, guild_id: int, user_id: int, summary: str) -> None:
        normalized = " ".join(summary.split()).strip()[:220]
        if not normalized:
            return
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE user_observations
                SET ai_summary = ?,
                    ai_summary_updated_at = ?,
                    summary_message_count = total_messages
                WHERE guild_id = ? AND user_id = ?
                """,
                (normalized, int(time.time()), guild_id, user_id),
            )

    def clear_user_observations(self, *, guild_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                DELETE FROM user_observations
                WHERE guild_id = ?
                """,
                (guild_id,),
            )

    def get_user_history_snapshot(self, *, guild_id: int, user_id: int) -> ModerationHistorySnapshot:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT decision, reason, labels, timeout_minutes, created_at
                FROM moderation_events
                WHERE guild_id = ? AND author_id = ?
                ORDER BY event_id DESC
                LIMIT ?
                """,
                (guild_id, user_id, self._RECENT_HISTORY_EVENT_LIMIT),
            ).fetchall()

        if not rows:
            return ModerationHistorySnapshot()

        now = int(time.time())
        warning_count_24h = 0
        warning_count_72h = 0
        light_violation_count_72h = 0
        ban_violation_count_30d = 0
        last_warning_age_minutes = -1
        last_sanction_age_minutes = -1
        recent_events: list[str] = []

        first_row = rows[0]
        last_created_at = int(first_row["created_at"])
        last_event_age_minutes = max(0, int((now - last_created_at) / 60))
        last_labels = tuple(item for item in str(first_row["labels"]).split(",") if item)

        for row in rows:
            decision = str(row["decision"]).strip()
            reason = str(row["reason"]).strip()
            labels = tuple(item for item in str(row["labels"]).split(",") if item)
            created_at = int(row["created_at"])
            age_seconds = max(0, now - created_at)
            age_minutes = max(0, int(age_seconds / 60))

            if age_seconds <= 24 * 60 * 60 and decision == "warning":
                warning_count_24h += 1
            if age_seconds <= 72 * 60 * 60:
                if decision == "warning":
                    warning_count_72h += 1
                if decision == "light_violation":
                    light_violation_count_72h += 1
            if age_seconds <= 30 * 24 * 60 * 60 and decision == "ban_violation":
                ban_violation_count_30d += 1

            if decision == "warning" and last_warning_age_minutes < 0:
                last_warning_age_minutes = age_minutes
            if decision in {"light_violation", "ban_violation"} and last_sanction_age_minutes < 0:
                last_sanction_age_minutes = age_minutes

            label_text = f" [{', '.join(labels[:3])}]" if labels else ""
            if age_minutes < 60:
                age_text = f"{age_minutes}м назад"
            elif age_minutes < 24 * 60:
                age_text = f"{max(1, age_minutes // 60)}ч назад"
            else:
                age_text = f"{max(1, age_minutes // (24 * 60))}д назад"
            recent_events.append(f"{age_text}: {decision}{label_text} — {reason[:96]}")

        return ModerationHistorySnapshot(
            warning_count_24h=warning_count_24h,
            warning_count_72h=warning_count_72h,
            light_violation_count_72h=light_violation_count_72h,
            ban_violation_count_30d=ban_violation_count_30d,
            last_decision=str(first_row["decision"]).strip(),
            last_reason=str(first_row["reason"]).strip(),
            last_labels=last_labels,
            last_timeout_minutes=int(first_row["timeout_minutes"]),
            last_event_age_minutes=last_event_age_minutes,
            last_warning_age_minutes=last_warning_age_minutes,
            last_sanction_age_minutes=last_sanction_age_minutes,
            recent_events=tuple(recent_events),
        )

    def list_user_observation_snapshots(
        self,
        *,
        guild_id: int,
        minimum_messages: int = 2,
        limit: int = 0,
    ) -> tuple[ModerationUserObservationSnapshot, ...]:
        query = """
            SELECT guild_id, user_id, last_seen_name, role_names, recent_samples, total_messages
            FROM user_observations
            WHERE guild_id = ? AND total_messages >= ?
            ORDER BY total_messages DESC, updated_at DESC
        """
        params: list[int] = [guild_id, max(1, minimum_messages)]
        if limit > 0:
            query += "\nLIMIT ?"
            params.append(limit)

        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()

        snapshots: list[ModerationUserObservationSnapshot] = []
        for row in rows:
            role_names = tuple(item.strip() for item in str(row["role_names"]).split(",") if item.strip())
            recent_samples = tuple(item for item in str(row["recent_samples"]).splitlines() if item)
            snapshots.append(
                ModerationUserObservationSnapshot(
                    guild_id=int(row["guild_id"]),
                    user_id=int(row["user_id"]),
                    display_name=str(row["last_seen_name"]),
                    role_names=role_names,
                    recent_samples=recent_samples,
                    total_messages=int(row["total_messages"]),
                )
            )
        return tuple(snapshots)

    def add_event(self, record: ModerationEventRecord) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO moderation_events (
                    guild_id,
                    channel_id,
                    message_id,
                    author_id,
                    author_name,
                    message_content,
                    decision,
                    reason,
                    labels,
                    timeout_minutes,
                    source,
                    confidence,
                    archive_message_id,
                    created_at,
                    reply_text,
                    attachment_urls,
                    context_lines
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.guild_id,
                    record.channel_id,
                    record.message_id,
                    record.author_id,
                    record.author_name,
                    record.message_content,
                    record.decision,
                    record.reason,
                    ",".join(record.labels),
                    record.timeout_minutes,
                    record.source,
                    record.confidence,
                    record.archive_message_id,
                    record.created_at or int(time.time()),
                    record.reply_text,
                    "\n".join(record.attachment_urls),
                    "\n".join(record.context_lines),
                ),
            )

    def list_recent_events(self, *, guild_id: int, limit: int = 20) -> list[ModerationEventRecord]:
        normalized_limit = max(1, min(limit, 100))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    guild_id,
                    channel_id,
                    message_id,
                    author_id,
                    author_name,
                    message_content,
                    decision,
                    reason,
                    labels,
                    timeout_minutes,
                    source,
                    confidence,
                    archive_message_id,
                    created_at,
                    reply_text,
                    attachment_urls,
                    context_lines
                FROM moderation_events
                WHERE guild_id = ?
                ORDER BY event_id DESC
                LIMIT ?
                """,
                (guild_id, normalized_limit),
            ).fetchall()

        return [self._record_from_row(row) for row in rows]

    def list_events_by_member(
        self,
        *,
        guild_id: int,
        member_id: int,
        limit: int = 20,
    ) -> list[ModerationEventRecord]:
        normalized_limit = max(1, min(limit, 100))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    guild_id,
                    channel_id,
                    message_id,
                    author_id,
                    author_name,
                    message_content,
                    decision,
                    reason,
                    labels,
                    timeout_minutes,
                    source,
                    confidence,
                    archive_message_id,
                    created_at,
                    reply_text,
                    attachment_urls,
                    context_lines
                FROM moderation_events
                WHERE guild_id = ? AND author_id = ?
                ORDER BY event_id DESC
                LIMIT ?
                """,
                (guild_id, member_id, normalized_limit),
            ).fetchall()

        return [self._record_from_row(row) for row in rows]

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    archive_channel_id INTEGER NOT NULL,
                    admin_alert_role_id INTEGER,
                    admin_alert_user_id INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS moderation_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    author_name TEXT NOT NULL,
                    message_content TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    labels TEXT NOT NULL DEFAULT '',
                    timeout_minutes INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0,
                    archive_message_id INTEGER,
                    created_at INTEGER NOT NULL,
                    reply_text TEXT NOT NULL DEFAULT '',
                    attachment_urls TEXT NOT NULL DEFAULT '',
                    context_lines TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS known_profiles (
                    discord_id INTEGER PRIMARY KEY,
                    primary_name TEXT NOT NULL,
                    aliases TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_observations (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    last_seen_name TEXT NOT NULL DEFAULT '',
                    role_names TEXT NOT NULL DEFAULT '',
                    total_messages INTEGER NOT NULL DEFAULT 0,
                    recent_samples TEXT NOT NULL DEFAULT '',
                    ai_summary TEXT NOT NULL DEFAULT '',
                    ai_summary_updated_at INTEGER NOT NULL DEFAULT 0,
                    summary_message_count INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
                """
            )
            self._ensure_column(connection, "user_observations", "recent_samples", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "user_observations", "ai_summary", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "user_observations", "ai_summary_updated_at", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "user_observations", "summary_message_count", "INTEGER NOT NULL DEFAULT 0")

    def _ensure_column(self, connection: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
        existing_columns = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing_columns:
            return
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _record_from_row(self, row: sqlite3.Row) -> ModerationEventRecord:
        labels = tuple(item for item in str(row["labels"]).split(",") if item)
        attachment_urls = tuple(item for item in str(row["attachment_urls"]).splitlines() if item)
        context_lines = tuple(item for item in str(row["context_lines"]).splitlines() if item)
        return ModerationEventRecord(
            guild_id=int(row["guild_id"]),
            channel_id=int(row["channel_id"]),
            message_id=int(row["message_id"]),
            author_id=int(row["author_id"]),
            author_name=str(row["author_name"]),
            message_content=str(row["message_content"]),
            decision=str(row["decision"]),
            reason=str(row["reason"]),
            labels=labels,
            timeout_minutes=int(row["timeout_minutes"]),
            source=str(row["source"]),
            confidence=float(row["confidence"]),
            archive_message_id=_optional_int(row["archive_message_id"]),
            created_at=int(row["created_at"]),
            reply_text=str(row["reply_text"]),
            attachment_urls=attachment_urls,
            context_lines=context_lines,
        )

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)
