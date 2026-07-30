from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import FlytrapAction, FlytrapConfig


class FlytrapRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def set_config(self, config: FlytrapConfig) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO flytrap_configs (
                    guild_id,
                    channel_id,
                    log_channel_id,
                    action,
                    warning_message_id,
                    moderated_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    log_channel_id = excluded.log_channel_id,
                    action = excluded.action,
                    warning_message_id = excluded.warning_message_id
                """,
                (
                    config.guild_id,
                    config.channel_id,
                    config.log_channel_id,
                    config.action.value,
                    config.warning_message_id,
                    config.moderated_count,
                ),
            )

    def get_config(self, guild_id: int) -> FlytrapConfig | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    guild_id,
                    channel_id,
                    log_channel_id,
                    action,
                    warning_message_id,
                    moderated_count
                FROM flytrap_configs
                WHERE guild_id = ?
                """,
                (guild_id,),
            ).fetchone()
        return self._config_from_row(row) if row is not None else None

    def get_config_by_channel(self, channel_id: int) -> FlytrapConfig | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    guild_id,
                    channel_id,
                    log_channel_id,
                    action,
                    warning_message_id,
                    moderated_count
                FROM flytrap_configs
                WHERE channel_id = ?
                """,
                (channel_id,),
            ).fetchone()
        return self._config_from_row(row) if row is not None else None

    def list_configs(self) -> list[FlytrapConfig]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    guild_id,
                    channel_id,
                    log_channel_id,
                    action,
                    warning_message_id,
                    moderated_count
                FROM flytrap_configs
                ORDER BY guild_id
                """
            ).fetchall()
        return [self._config_from_row(row) for row in rows]

    def delete_config(self, guild_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM flytrap_configs WHERE guild_id = ?",
                (guild_id,),
            )

    def finish_handled_incident(self, *, message_id: int, guild_id: int) -> int:
        with self._connection() as connection:
            incident_cursor = connection.execute(
                """
                UPDATE flytrap_incidents
                SET status = 'handled', finished_at = ?
                WHERE message_id = ? AND status = 'processing'
                """,
                (datetime.now(UTC).isoformat(), message_id),
            )
            if incident_cursor.rowcount != 1:
                raise LookupError(f"Активный инцидент {message_id} не найден.")

            config_cursor = connection.execute(
                """
                UPDATE flytrap_configs
                SET moderated_count = moderated_count + 1
                WHERE guild_id = ?
                """,
                (guild_id,),
            )
            if config_cursor.rowcount != 1:
                raise LookupError(f"Конфигурация Мухоловки для сервера {guild_id} не найдена.")

            row = connection.execute(
                "SELECT moderated_count FROM flytrap_configs WHERE guild_id = ?",
                (guild_id,),
            ).fetchone()
        if row is None:  # pragma: no cover - guarded by the update above
            raise LookupError(f"Счётчик Мухоловки для сервера {guild_id} не найден.")
        return int(row["moderated_count"])

    def claim_incident(
        self,
        *,
        message_id: int,
        guild_id: int,
        channel_id: int,
        user_id: int,
        action: FlytrapAction,
    ) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO flytrap_incidents (
                    message_id,
                    guild_id,
                    channel_id,
                    user_id,
                    action,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 'processing', ?)
                """,
                (
                    message_id,
                    guild_id,
                    channel_id,
                    user_id,
                    action.value,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return cursor.rowcount == 1

    def finish_incident(self, message_id: int, *, status: str, detail: str | None = None) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE flytrap_incidents
                SET status = ?, detail = ?, finished_at = ?
                WHERE message_id = ?
                """,
                (status, detail, datetime.now(UTC).isoformat(), message_id),
            )

    def get_incident_status(self, message_id: int) -> str | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT status FROM flytrap_incidents WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        return str(row["status"]) if row is not None else None

    def purge_old_incidents(self, *, max_age: timedelta = timedelta(days=30)) -> int:
        cutoff = (datetime.now(UTC) - max_age).isoformat()
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM flytrap_incidents WHERE created_at < ?",
                (cutoff,),
            )
        return cursor.rowcount

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS flytrap_configs (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL UNIQUE,
                    log_channel_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    warning_message_id INTEGER NOT NULL,
                    moderated_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS flytrap_incidents (
                    message_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL,
                    finished_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_flytrap_incidents_created_at
                    ON flytrap_incidents(created_at);
                """
            )
            config_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(flytrap_configs)").fetchall()
            }
            if "moderated_count" not in config_columns:
                connection.execute(
                    """
                    ALTER TABLE flytrap_configs
                    ADD COLUMN moderated_count INTEGER NOT NULL DEFAULT 0
                    """
                )

    @staticmethod
    def _config_from_row(row: sqlite3.Row) -> FlytrapConfig:
        return FlytrapConfig(
            guild_id=int(row["guild_id"]),
            channel_id=int(row["channel_id"]),
            log_channel_id=int(row["log_channel_id"]),
            action=FlytrapAction(row["action"]),
            warning_message_id=int(row["warning_message_id"]),
            moderated_count=int(row["moderated_count"]),
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
