from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests import support  # noqa: F401

from core.panel_registry import PublishedPanelRecord, PublishedPanelRepository


class PublishedPanelRepositoryTests(unittest.TestCase):
    def test_set_get_delete_many_and_delete_by_channel(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "panel_registry.sqlite3"
            repository = PublishedPanelRepository(database_path, namespace="welcome")

            record_a = PublishedPanelRecord(channel_id=10)
            record_b = PublishedPanelRecord(channel_id=20)
            repository.set(1, record_a)
            repository.set(2, record_b)

            self.assertEqual(repository.get(1), record_a)
            self.assertEqual(repository.items(), [(1, record_a), (2, record_b)])

            repository.delete_many([1, 999])
            self.assertIsNone(repository.get(1))
            self.assertEqual(repository.items(), [(2, record_b)])

            repository.delete_by_channel(20)
            self.assertEqual(repository.items(), [])

    def test_migrates_legacy_json_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "panel_registry.sqlite3"
            legacy_path = Path(temp_dir) / "welcome_panels.json"
            legacy_payload = {
                "123": {"channel_id": 456},
            }
            legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

            repository = PublishedPanelRepository(
                database_path,
                namespace="welcome",
                legacy_path=legacy_path,
            )

            self.assertEqual(repository.get(123), PublishedPanelRecord(channel_id=456))
            self.assertFalse(legacy_path.exists())


if __name__ == "__main__":
    unittest.main()
