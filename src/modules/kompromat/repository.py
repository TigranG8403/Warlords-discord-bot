from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class KompromatEntry:
    entry_id: int
    guild_id: int
    category_key: str
    title: str
    summary: str
    author_id: int
    tags_text: str | None
    channel_id: int
    message_id: int
    thread_id: int | None
    has_evidence: int
    created_at: str


class KompromatRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def set_archive_channel(self, guild_id: int, channel_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO guild_settings (guild_id, archive_channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET archive_channel_id = excluded.archive_channel_id
                """,
                (guild_id, channel_id),
            )

    def get_archive_channel(self, guild_id: int) -> int | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT archive_channel_id FROM guild_settings WHERE guild_id = ?",
                (guild_id,),
            ).fetchone()
        return row[0] if row else None

    def create_entry(
        self,
        *,
        guild_id: int,
        category_key: str,
        title: str,
        summary: str,
        author_id: int,
        tags_text: str | None,
        tagged_user_ids: list[int],
        channel_id: int,
        message_id: int,
        thread_id: int | None,
        has_evidence: bool,
        created_at: str,
    ) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO entries (
                    guild_id,
                    category_key,
                    title,
                    summary,
                    author_id,
                    tags_text,
                    channel_id,
                    message_id,
                    thread_id,
                    has_evidence,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    category_key,
                    title,
                    summary,
                    author_id,
                    tags_text,
                    channel_id,
                    message_id,
                    thread_id,
                    int(has_evidence),
                    created_at,
                ),
            )
            entry_id = int(cursor.lastrowid)
            for user_id in tagged_user_ids:
                connection.execute(
                    "INSERT INTO entry_tags (entry_id, user_id) VALUES (?, ?)",
                    (entry_id, user_id),
                )
        return entry_id

    def search_by_member(self, *, guild_id: int, member_id: int, limit: int = 10) -> list[KompromatEntry]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    e.entry_id,
                    e.guild_id,
                    e.category_key,
                    e.title,
                    e.summary,
                    e.author_id,
                    e.tags_text,
                    e.channel_id,
                    e.message_id,
                    e.thread_id,
                    e.has_evidence,
                    e.created_at
                FROM entries e
                INNER JOIN entry_tags t ON t.entry_id = e.entry_id
                WHERE e.guild_id = ? AND t.user_id = ?
                ORDER BY e.entry_id DESC
                LIMIT ?
                """,
                (guild_id, member_id, limit),
            ).fetchall()
        return [KompromatEntry(*row) for row in rows]

    def get_by_thread_id(self, thread_id: int) -> KompromatEntry | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    entry_id,
                    guild_id,
                    category_key,
                    title,
                    summary,
                    author_id,
                    tags_text,
                    channel_id,
                    message_id,
                    thread_id,
                    has_evidence,
                    created_at
                FROM entries
                WHERE thread_id = ?
                """,
                (thread_id,),
            ).fetchone()
        return KompromatEntry(*row) if row else None

    def mark_has_evidence(self, entry_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE entries SET has_evidence = 1 WHERE entry_id = ?",
                (entry_id,),
            )

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    archive_channel_id INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    category_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    author_id INTEGER NOT NULL,
                    tags_text TEXT,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    thread_id INTEGER,
                    has_evidence INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entry_tags (
                    entry_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    PRIMARY KEY (entry_id, user_id)
                );
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(entries)").fetchall()
            }
            if "has_evidence" not in columns:
                connection.execute(
                    "ALTER TABLE entries ADD COLUMN has_evidence INTEGER NOT NULL DEFAULT 0"
                )

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
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
