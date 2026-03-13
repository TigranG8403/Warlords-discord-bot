from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests import support  # noqa: F401

from modules.kompromat.repository import KompromatRepository


class KompromatRepositoryTests(unittest.TestCase):
    def test_archive_settings_and_entry_lookup(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = KompromatRepository(Path(temp_dir) / "kompromat.sqlite3")
            repository.set_archive_channel(1, 200)

            entry_id = repository.create_entry(
                guild_id=1,
                category_key="other",
                title="Подозрительная история",
                summary="Краткое описание",
                author_id=100,
                tags_text="<@500>",
                tagged_user_ids=[500],
                channel_id=300,
                message_id=400,
                thread_id=401,
                has_evidence=False,
                created_at="2026-01-01T12:00:00+00:00",
            )

            self.assertEqual(repository.get_archive_channel(1), 200)

            entries = repository.search_by_member(guild_id=1, member_id=500)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].entry_id, entry_id)

            repository.mark_has_evidence(entry_id)
            entry = repository.get_by_thread_id(401)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.has_evidence, 1)


if __name__ == "__main__":
    unittest.main()
