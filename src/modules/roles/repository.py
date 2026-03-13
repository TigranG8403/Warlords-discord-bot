from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.panel_registry import SqliteMessageRepository


@dataclass(slots=True)
class RolePanelRecord:
    guild_id: int
    channel_id: int
    news_role_id: int
    gamer_role_id: int


class RolePanelRepository(SqliteMessageRepository[RolePanelRecord]):
    def __init__(self, database_path: Path, *, legacy_path: Path | None = None) -> None:
        super().__init__(
            database_path,
            namespace="roles",
            record_type=RolePanelRecord,
            legacy_path=legacy_path,
        )
