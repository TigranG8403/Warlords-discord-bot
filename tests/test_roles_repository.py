from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests import support  # noqa: F401

from modules.roles.repository import RolePanelRecord, RolePanelRepository


class RolePanelRepositoryTests(unittest.TestCase):
    def test_set_get_items_and_delete(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = RolePanelRepository(Path(temp_dir) / "panel_registry.sqlite3")
            record = RolePanelRecord(
                guild_id=1,
                channel_id=2,
                news_role_id=3,
                gamer_role_id=4,
            )

            repository.set(42, record)

            self.assertEqual(repository.get(42), record)
            self.assertEqual(repository.items(), [(42, record)])

            repository.delete(42)
            self.assertIsNone(repository.get(42))
            self.assertEqual(repository.items(), [])


if __name__ == "__main__":
    unittest.main()
