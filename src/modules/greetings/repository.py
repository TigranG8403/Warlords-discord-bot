from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import GreetingsConfig


class GreetingsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def set_config(self, config: GreetingsConfig) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO greetings_configs (guild_id, channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    channel_id = excluded.channel_id
                """,
                (config.guild_id, config.channel_id),
            )

    def get_config(self, guild_id: int) -> GreetingsConfig | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT guild_id, channel_id
                FROM greetings_configs
                WHERE guild_id = ?
                """,
                (guild_id,),
            ).fetchone()
        if row is None:
            return None
        return GreetingsConfig(guild_id=int(row["guild_id"]), channel_id=int(row["channel_id"]))

    def delete_config(self, guild_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM greetings_configs WHERE guild_id = ?",
                (guild_id,),
            )

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS greetings_configs (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL
                )
                """
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
