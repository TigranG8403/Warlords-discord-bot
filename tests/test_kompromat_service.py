from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from tests import support  # noqa: F401

from modules.kompromat.repository import KompromatRepository
from modules.kompromat.service import KompromatService
from modules.moderation.config import ModerationEventRecord
from modules.moderation.repository import ModerationRepository


class KompromatServiceTests(unittest.TestCase):
    def test_search_by_member_includes_moderation_events(self) -> None:
        with TemporaryDirectory() as temp_dir:
            kompromat_repository = KompromatRepository(Path(temp_dir) / "kompromat.sqlite3")
            moderation_repository = ModerationRepository(Path(temp_dir) / "moderation.sqlite3")
            moderation_repository.save_guild_settings(1, archive_channel_id=900)

            kompromat_repository.create_entry(
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
            moderation_repository.add_event(
                ModerationEventRecord(
                    guild_id=1,
                    channel_id=310,
                    message_id=410,
                    author_id=500,
                    author_name="displetto",
                    message_content="если сорвешь, и завтра сервера не будет, то ты мне должен 1000 рублей",
                    decision="review",
                    reason="Шутка про запуск, но событие заархивировано для истории.",
                    labels=("server_launch",),
                    timeout_minutes=0,
                    source="deepseek:deepseek-chat",
                    confidence=0.88,
                    archive_message_id=901,
                    created_at=1_800_000_000,
                )
            )

            service = KompromatService(kompromat_repository, moderation_repository)
            member = SimpleNamespace(id=500, display_name="Nikeron4ik")

            entries = service.search_by_member(guild_id=1, member=member, limit=10)

            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].label, "Автомодерация • Ручная проверка")
            self.assertEqual(entries[0].jump_url, "https://discord.com/channels/1/900/901")
            self.assertEqual(entries[1].title, "Старая запись")

    def test_search_embed_renders_moderation_records(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = KompromatService(
                KompromatRepository(Path(temp_dir) / "kompromat.sqlite3"),
                ModerationRepository(Path(temp_dir) / "moderation.sqlite3"),
            )
            member = SimpleNamespace(display_name="Messire")

            embed = service.build_search_embed(
                member=member,
                entries=[
                    SimpleNamespace(
                        sort_timestamp=1_800_000_000,
                        emoji="🤖",
                        label="Автомодерация • Автомут",
                        title="ты просто конченый долбоеб",
                        summary="Явное оскорбление",
                        jump_url="https://discord.com/channels/1/900/901",
                        thread_id=None,
                    )
                ],
            )

            self.assertIn("Автомодерация", embed.description)
            self.assertIn("ты просто конченый долбоеб", embed.description)


if __name__ == "__main__":
    unittest.main()
