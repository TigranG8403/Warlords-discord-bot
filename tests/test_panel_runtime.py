from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
import unittest

from tests import support  # noqa: F401

from core.panel_runtime import PanelRuntime


@dataclass(slots=True)
class DummyRecord:
    channel_id: int


class DummyRepository:
    def __init__(self) -> None:
        self.deleted_message_ids: list[int] = []
        self.deleted_many: list[int] = []
        self.deleted_channel_ids: list[int] = []

    def set(self, message_id: int, record: DummyRecord) -> None:
        raise NotImplementedError

    def delete(self, message_id: int) -> None:
        self.deleted_message_ids.append(message_id)

    def delete_many(self, message_ids) -> None:
        self.deleted_many.extend(sorted(message_ids))

    def delete_by_channel(self, channel_id: int) -> None:
        self.deleted_channel_ids.append(channel_id)

    def items(self):
        return []


class PanelRuntimeDeletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_cleans_registry_on_message_and_channel_delete(self) -> None:
        repository = DummyRepository()
        runtime = PanelRuntime(
            name="dummy",
            repository=repository,
            render_panel=lambda record, channel: None,
            period_getter=lambda: "day",
        )

        await runtime._on_raw_message_delete(SimpleNamespace(message_id=101))
        await runtime._on_raw_bulk_message_delete(SimpleNamespace(message_ids={201, 202}))
        await runtime._on_guild_channel_delete(SimpleNamespace(id=301))

        self.assertEqual(repository.deleted_message_ids, [101])
        self.assertEqual(repository.deleted_many, [201, 202])
        self.assertEqual(repository.deleted_channel_ids, [301])


if __name__ == "__main__":
    unittest.main()
