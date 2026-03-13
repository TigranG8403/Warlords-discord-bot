from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import TicketGuildSettings


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _deserialize_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


@dataclass(slots=True)
class TicketRecord:
    id: int
    guild_id: int
    channel_id: int
    message_id: int
    creator_id: int
    ticket_type: str
    panel_type: str
    subject: str
    details: dict[str, str]
    status: str
    assigned_to: int | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    closed_by: int | None
    close_reason: str | None
    last_staff_call_at: datetime | None


class TicketRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL UNIQUE,
                    message_id INTEGER NOT NULL DEFAULT 0,
                    creator_id INTEGER NOT NULL,
                    ticket_type TEXT NOT NULL,
                    panel_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    assigned_to INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    closed_at TEXT,
                    closed_by INTEGER,
                    close_reason TEXT,
                    last_staff_call_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_tickets_active_creator
                    ON tickets(guild_id, creator_id, ticket_type, closed_at);

                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    ticket_category_id INTEGER NOT NULL,
                    fraction_category_id INTEGER NOT NULL,
                    rp_category_id INTEGER NOT NULL,
                    log_channel_id INTEGER NOT NULL,
                    support_role_id INTEGER NOT NULL,
                    staff_call_cooldown_minutes INTEGER NOT NULL DEFAULT 5
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(guild_settings)").fetchall()
            }
            if "staff_call_cooldown_minutes" not in columns:
                connection.execute(
                    "ALTER TABLE guild_settings ADD COLUMN staff_call_cooldown_minutes INTEGER NOT NULL DEFAULT 5"
                )

    def create_ticket(
        self,
        *,
        guild_id: int,
        channel_id: int,
        creator_id: int,
        ticket_type: str,
        panel_type: str,
        subject: str,
        details: dict[str, str],
        status: str,
        created_at: datetime,
    ) -> TicketRecord:
        serialized_now = _serialize_datetime(created_at)
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tickets (
                    guild_id, channel_id, creator_id, ticket_type, panel_type,
                    subject, details_json, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    channel_id,
                    creator_id,
                    ticket_type,
                    panel_type,
                    subject,
                    json.dumps(details, ensure_ascii=False),
                    status,
                    serialized_now,
                    serialized_now,
                ),
            )
            ticket_id = int(cursor.lastrowid)

        record = self.get_by_id(ticket_id)
        if record is None:
            raise RuntimeError("Не удалось сохранить тикет в базе данных.")
        return record

    def get_by_id(self, ticket_id: int) -> TicketRecord | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return self._row_to_record(row)

    def get_by_channel_id(self, channel_id: int) -> TicketRecord | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)).fetchone()
        return self._row_to_record(row)

    def get_active_by_creator_and_type(self, guild_id: int, creator_id: int, ticket_type: str) -> TicketRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM tickets
                WHERE guild_id = ? AND creator_id = ? AND ticket_type = ? AND closed_at IS NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (guild_id, creator_id, ticket_type),
            ).fetchone()
        return self._row_to_record(row)

    def set_message_id(self, channel_id: int, message_id: int, updated_at: datetime) -> TicketRecord | None:
        return self._update_and_fetch(
            channel_id,
            "message_id = ?, updated_at = ?",
            (message_id, _serialize_datetime(updated_at)),
        )

    def assign_ticket(self, channel_id: int, staff_member_id: int, status: str, updated_at: datetime) -> TicketRecord | None:
        return self._update_and_fetch(
            channel_id,
            "assigned_to = ?, status = ?, updated_at = ?",
            (staff_member_id, status, _serialize_datetime(updated_at)),
        )

    def update_status(self, channel_id: int, status: str, updated_at: datetime) -> TicketRecord | None:
        return self._update_and_fetch(
            channel_id,
            "status = ?, updated_at = ?",
            (status, _serialize_datetime(updated_at)),
        )

    def set_last_staff_call_at(self, channel_id: int, called_at: datetime) -> TicketRecord | None:
        return self._update_and_fetch(
            channel_id,
            "last_staff_call_at = ?, updated_at = ?",
            (_serialize_datetime(called_at), _serialize_datetime(called_at)),
        )

    def mark_closed(
        self,
        channel_id: int,
        *,
        closed_by: int,
        close_reason: str,
        closed_at: datetime,
    ) -> TicketRecord | None:
        return self._update_and_fetch(
            channel_id,
            "status = ?, closed_by = ?, close_reason = ?, closed_at = ?, updated_at = ?",
            (
                "closed",
                closed_by,
                close_reason,
                _serialize_datetime(closed_at),
                _serialize_datetime(closed_at),
            ),
        )

    def delete_by_channel_id(self, channel_id: int) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM tickets WHERE channel_id = ?", (channel_id,))

    def set_guild_settings(self, settings: TicketGuildSettings) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO guild_settings (
                    guild_id,
                    ticket_category_id,
                    fraction_category_id,
                    rp_category_id,
                    log_channel_id,
                    support_role_id,
                    staff_call_cooldown_minutes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    ticket_category_id = excluded.ticket_category_id,
                    fraction_category_id = excluded.fraction_category_id,
                    rp_category_id = excluded.rp_category_id,
                    log_channel_id = excluded.log_channel_id,
                    support_role_id = excluded.support_role_id,
                    staff_call_cooldown_minutes = excluded.staff_call_cooldown_minutes
                """,
                (
                    settings.guild_id,
                    settings.ticket_category_id,
                    settings.fraction_category_id,
                    settings.rp_category_id,
                    settings.log_channel_id,
                    settings.support_role_id,
                    settings.staff_call_cooldown_minutes,
                ),
            )

    def get_guild_settings(self, guild_id: int) -> TicketGuildSettings | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    guild_id,
                    ticket_category_id,
                    fraction_category_id,
                    rp_category_id,
                    log_channel_id,
                    support_role_id,
                    staff_call_cooldown_minutes
                FROM guild_settings
                WHERE guild_id = ?
                """,
                (guild_id,),
            ).fetchone()
        if row is None:
            return None
        return TicketGuildSettings(
            guild_id=row["guild_id"],
            ticket_category_id=row["ticket_category_id"],
            fraction_category_id=row["fraction_category_id"],
            rp_category_id=row["rp_category_id"],
            log_channel_id=row["log_channel_id"],
            support_role_id=row["support_role_id"],
            staff_call_cooldown_minutes=row["staff_call_cooldown_minutes"],
        )

    def delete_guild_settings(self, guild_id: int) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,))

    def _update_and_fetch(self, channel_id: int, set_clause: str, values: tuple[object, ...]) -> TicketRecord | None:
        with self._connection() as connection:
            connection.execute(f"UPDATE tickets SET {set_clause} WHERE channel_id = ?", (*values, channel_id))
            row = connection.execute("SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)).fetchone()
        return self._row_to_record(row)

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_record(self, row: sqlite3.Row | None) -> TicketRecord | None:
        if row is None:
            return None

        return TicketRecord(
            id=row["id"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            message_id=row["message_id"],
            creator_id=row["creator_id"],
            ticket_type=row["ticket_type"],
            panel_type=row["panel_type"],
            subject=row["subject"],
            details=json.loads(row["details_json"]),
            status=row["status"],
            assigned_to=row["assigned_to"],
            created_at=_deserialize_datetime(row["created_at"]) or datetime.min,
            updated_at=_deserialize_datetime(row["updated_at"]) or datetime.min,
            closed_at=_deserialize_datetime(row["closed_at"]),
            closed_by=row["closed_by"],
            close_reason=row["close_reason"],
            last_staff_call_at=_deserialize_datetime(row["last_staff_call_at"]),
        )
