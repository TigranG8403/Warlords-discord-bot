from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from tests import support  # noqa: F401

from modules.kompromat.repository import KompromatRepository
from modules.kompromat.service import KompromatService


class KompromatServiceTests(unittest.TestCase):
    def test_search_by_member_returns_manual_entries_newest_first(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = KompromatRepository(Path(temp_dir) / "kompromat.sqlite3")
            repository.create_entry(
                guild_id=1,
                category_key="toxicity",
                title="Старая запись",
                summary="Ручной компромат",
                author_id=100,
                tags_text="<@500>",
                tagged_user_ids=[500],
                channel_id=300,
                message_id=400,
                thread_id=401,
                has_evidence=False,
                created_at="2026-01-01T12:00:00+00:00",
            )
            repository.create_entry(
                guild_id=1,
                category_key="rule_violation",
                title="Новая запись",
                summary="Более новый ручной компромат",
                author_id=101,
                tags_text="<@500>",
                tagged_user_ids=[500],
                channel_id=301,
                message_id=402,
                thread_id=None,
                has_evidence=True,
                created_at="2026-02-01T12:00:00+00:00",
            )

            service = KompromatService(repository)
            member = SimpleNamespace(id=500, display_name="Nikeron4ik")

            entries = service.search_by_member(guild_id=1, member=member, limit=10)

            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].title, "Новая запись")
            self.assertEqual(entries[1].title, "Старая запись")

    def test_search_embed_renders_records(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = KompromatService(
                KompromatRepository(Path(temp_dir) / "kompromat.sqlite3"),
            )
            member = SimpleNamespace(display_name="Messire")

            embed = service.build_search_embed(
                member=member,
                entries=[
                    SimpleNamespace(
                        sort_timestamp=1_800_000_000,
                        emoji="⛔",
                        label="Нарушение правил",
                        title="Нарушение на рынке",
                        summary="Ручная запись с доказательствами",
                        jump_url="https://discord.com/channels/1/900/901",
                        thread_id=None,
                    )
                ],
            )

            self.assertIn("Нарушение правил", embed.description)
            self.assertIn("Нарушение на рынке", embed.description)


if __name__ == "__main__":
    unittest.main()
