from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager

from .config import LoginSessionRecord


class DiscordAuthStorageMixin:
    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    verify_role_id INTEGER NOT NULL,
                    start_message_channel_id INTEGER NOT NULL,
                    admin_command_channel_id INTEGER NOT NULL,
                    admin_command_role_id INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS player_records (
                    player_uuid TEXT PRIMARY KEY,
                    player_name TEXT NOT NULL,
                    discord_user_id INTEGER NOT NULL DEFAULT 0,
                    discord_username TEXT NOT NULL DEFAULT '',
                    discord_display_name TEXT NOT NULL DEFAULT '',
                    access_state TEXT NOT NULL DEFAULT 'AUTO',
                    admin_status TEXT NOT NULL DEFAULT '',
                    temp_ban_until INTEGER NOT NULL DEFAULT 0,
                    temp_ban_reason TEXT NOT NULL DEFAULT '',
                    admin_note TEXT NOT NULL DEFAULT '',
                    last_ip TEXT NOT NULL DEFAULT '',
                    last_authenticated_at INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_player_records_discord_user_id
                    ON player_records(discord_user_id);

                CREATE TABLE IF NOT EXISTS link_codes (
                    code TEXT PRIMARY KEY,
                    player_uuid TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS login_sessions (
                    session_id TEXT PRIMARY KEY,
                    player_uuid TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    discord_user_id INTEGER NOT NULL,
                    address TEXT NOT NULL DEFAULT '',
                    ip_address TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    message_id INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_login_sessions_status
                    ON login_sessions(status);

                CREATE TABLE IF NOT EXISTS metrics_snapshots (
                    bucket_start INTEGER PRIMARY KEY,
                    total_players INTEGER NOT NULL,
                    linked_players INTEGER NOT NULL,
                    pending_codes INTEGER NOT NULL,
                    active_sessions INTEGER NOT NULL,
                    online_players INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    player_uuid TEXT NOT NULL DEFAULT '',
                    player_name TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    expires_at INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_auth_events_type_created_at
                    ON auth_events(event_type, created_at);
                """
            )
            self._ensure_column(connection, "player_records", "is_online", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "player_records", "online_since", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "player_records", "last_seen_at", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "auth_events", "reason", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "auth_events", "expires_at", "INTEGER NOT NULL DEFAULT 0")

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {str(row["name"]) for row in rows}
        if column_name in existing:
            return
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _cleanup_expired_locked(self, connection: sqlite3.Connection) -> None:
        now = self._now()
        connection.execute("DELETE FROM link_codes WHERE expires_at <= ?", (now,))
        connection.execute(
            """
            UPDATE login_sessions
            SET status = 'TIMEOUT'
            WHERE status = 'PENDING' AND expires_at <= ?
            """,
            (now,),
        )

    def _row_to_session(self, row: sqlite3.Row) -> LoginSessionRecord:
        return LoginSessionRecord(
            session_id=row["session_id"],
            player_uuid=row["player_uuid"],
            player_name=row["player_name"],
            discord_user_id=int(row["discord_user_id"]),
            address=row["address"],
            ip_address=row["ip_address"],
            status=row["status"],
            created_at=int(row["created_at"]),
            expires_at=int(row["expires_at"]),
            message_id=int(row["message_id"]),
        )

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _now() -> int:
        return int(time.time())
