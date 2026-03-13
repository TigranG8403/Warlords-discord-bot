from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Generic, Iterable, TypeVar


@dataclass(slots=True)
class PublishedPanelRecord:
    channel_id: int


RecordT = TypeVar("RecordT")


class SqliteMessageRepository(Generic[RecordT]):
    def __init__(
        self,
        database_path: Path,
        *,
        namespace: str,
        record_type: type[RecordT],
        legacy_path: Path | None = None,
    ) -> None:
        self.database_path = database_path
        self.namespace = namespace
        self.record_type = record_type
        self.legacy_path = legacy_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._migrate_legacy_records()

    def get(self, message_id: int) -> RecordT | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT record_json
                FROM panel_records
                WHERE namespace = ? AND message_id = ?
                """,
                (self.namespace, message_id),
            ).fetchone()
        if row is None:
            return None
        return self._deserialize(row["record_json"])

    def set(self, message_id: int, record: RecordT) -> None:
        payload = json.dumps(asdict(record), ensure_ascii=False)
        channel_id = int(getattr(record, "channel_id"))
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO panel_records (namespace, message_id, channel_id, record_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(namespace, message_id) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    record_json = excluded.record_json
                """,
                (self.namespace, message_id, channel_id, payload),
            )

    def delete(self, message_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                DELETE FROM panel_records
                WHERE namespace = ? AND message_id = ?
                """,
                (self.namespace, message_id),
            )

    def delete_many(self, message_ids: Iterable[int]) -> None:
        normalized_ids = sorted({int(message_id) for message_id in message_ids})
        if not normalized_ids:
            return

        placeholders = ", ".join("?" for _ in normalized_ids)
        with self._connection() as connection:
            connection.execute(
                f"""
                DELETE FROM panel_records
                WHERE namespace = ? AND message_id IN ({placeholders})
                """,
                (self.namespace, *normalized_ids),
            )

    def delete_by_channel(self, channel_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                DELETE FROM panel_records
                WHERE namespace = ? AND channel_id = ?
                """,
                (self.namespace, channel_id),
            )

    def items(self) -> list[tuple[int, RecordT]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT message_id, record_json
                FROM panel_records
                WHERE namespace = ?
                ORDER BY message_id
                """,
                (self.namespace,),
            ).fetchall()
        return [
            (int(row["message_id"]), self._deserialize(row["record_json"]))
            for row in rows
        ]

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS panel_records (
                    namespace TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY (namespace, message_id)
                );

                CREATE INDEX IF NOT EXISTS idx_panel_records_channel
                    ON panel_records(namespace, channel_id);
                """
            )

    def _migrate_legacy_records(self) -> None:
        if self.legacy_path is None or not self.legacy_path.exists():
            return

        try:
            raw_payload = json.loads(self.legacy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(raw_payload, dict):
            return

        with self._connection() as connection:
            for raw_message_id, raw_record in raw_payload.items():
                try:
                    message_id = int(raw_message_id)
                except (TypeError, ValueError):
                    continue
                if not isinstance(raw_record, dict):
                    continue

                try:
                    record = self.record_type(**raw_record)
                except TypeError:
                    continue

                connection.execute(
                    """
                    INSERT INTO panel_records (namespace, message_id, channel_id, record_json)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(namespace, message_id) DO UPDATE SET
                        channel_id = excluded.channel_id,
                        record_json = excluded.record_json
                    """,
                    (
                        self.namespace,
                        message_id,
                        int(getattr(record, "channel_id")),
                        json.dumps(asdict(record), ensure_ascii=False),
                    ),
                )

        try:
            self.legacy_path.unlink()
        except OSError:
            pass

    def _deserialize(self, raw_record: str) -> RecordT:
        return self.record_type(**json.loads(raw_record))

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


class PublishedPanelRepository(SqliteMessageRepository[PublishedPanelRecord]):
    def __init__(
        self,
        database_path: Path,
        *,
        namespace: str,
        legacy_path: Path | None = None,
    ) -> None:
        super().__init__(
            database_path,
            namespace=namespace,
            record_type=PublishedPanelRecord,
            legacy_path=legacy_path,
        )
