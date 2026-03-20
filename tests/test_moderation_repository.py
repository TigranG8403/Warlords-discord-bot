from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from tests import support  # noqa: F401
from modules.moderation.config import ModerationEventRecord, ModerationKnownProfile
from modules.moderation.repository import ModerationRepository


class ModerationRepositoryTests(unittest.TestCase):
    def test_save_and_load_guild_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ModerationRepository(Path(temp_dir) / "moderation.sqlite3")

            repository.save_guild_settings(
                42,
                archive_channel_id=1001,
                admin_alert_role_id=2002,
                admin_alert_user_id=3003,
            )

            settings = repository.get_guild_settings(42)
            self.assertIsNotNone(settings)
            assert settings is not None
            self.assertEqual(settings.archive_channel_id, 1001)
            self.assertEqual(settings.admin_alert_role_id, 2002)
            self.assertEqual(settings.admin_alert_user_id, 3003)

    def test_add_and_list_recent_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ModerationRepository(Path(temp_dir) / "moderation.sqlite3")
            repository.add_event(
                ModerationEventRecord(
                    guild_id=7,
                    channel_id=8,
                    message_id=9,
                    author_id=10,
                    author_name="messire",
                    message_content="иди нахуй долбоеб",
                    decision="light_violation",
                    reason="Явное оскорбление",
                    labels=("insult", "aggression"),
                    timeout_minutes=1440,
                    source="rules",
                    confidence=0.9,
                    reply_text="reply",
                    attachment_urls=("https://cdn.test/file.png",),
                    context_lines=("user1: привет", "user2: ага"),
                )
            )

            records = repository.list_recent_events(guild_id=7, limit=5)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].labels, ("insult", "aggression"))
            self.assertEqual(records[0].attachment_urls, ("https://cdn.test/file.png",))
            self.assertEqual(records[0].context_lines, ("user1: привет", "user2: ага"))

    def test_seed_known_profiles_and_character_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ModerationRepository(Path(temp_dir) / "moderation.sqlite3")
            repository.seed_known_profiles(
                (
                    ModerationKnownProfile(
                        discord_id=1,
                        primary_name="messire",
                        aliases=("mss1r", "мессир"),
                        summary="создатель и разработчик бота",
                    ),
                )
            )

            profile = repository.get_known_profile(1)
            self.assertIsNotNone(profile)
            assert profile is not None
            self.assertEqual(profile.primary_name, "messire")
            self.assertIn("мессир", profile.aliases)
            self.assertTrue(repository.list_known_profile_summaries())

            repository.record_user_observation(
                guild_id=7,
                user_id=1,
                author_name="messire",
                role_names=("Admin", "Dev"),
                content="ну привет",
                decision="allow",
                addressed_to_bot=True,
                labels=(),
            )
            repository.record_user_observation(
                guild_id=7,
                user_id=1,
                author_name="messire",
                role_names=("Admin", "Dev"),
                content="что по открытию",
                decision="allow",
                addressed_to_bot=True,
                labels=(),
            )

            self.assertTrue(repository.should_refresh_user_character(guild_id=7, user_id=1))
            self.assertEqual(len(repository.get_recent_user_samples(guild_id=7, user_id=1)), 2)

            repository.save_user_character_summary(
                guild_id=7,
                user_id=1,
                summary="Обычно пишет коротко и по делу, часто обращается к боту напрямую.",
            )

            self.assertIn("коротко", repository.describe_user_character(guild_id=7, user_id=1))

    def test_get_user_history_snapshot_summarizes_recent_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ModerationRepository(Path(temp_dir) / "moderation.sqlite3")
            now = int(time.time())
            with repository._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO moderation_events (
                        guild_id,
                        channel_id,
                        message_id,
                        author_id,
                        author_name,
                        message_content,
                        decision,
                        reason,
                        labels,
                        timeout_minutes,
                        source,
                        confidence,
                        archive_message_id,
                        created_at,
                        reply_text,
                        attachment_urls,
                        context_lines
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        7,
                        8,
                        10,
                        77,
                        "user",
                        "первый перегиб",
                        "warning",
                        "резковато",
                        "bait",
                        0,
                        "deepseek:deepseek-chat",
                        0.81,
                        None,
                        now - 30 * 60,
                        "полегче",
                        "",
                        "",
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO moderation_events (
                        guild_id,
                        channel_id,
                        message_id,
                        author_id,
                        author_name,
                        message_content,
                        decision,
                        reason,
                        labels,
                        timeout_minutes,
                        source,
                        confidence,
                        archive_message_id,
                        created_at,
                        reply_text,
                        attachment_urls,
                        context_lines
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        7,
                        8,
                        11,
                        77,
                        "user",
                        "повторный перегиб",
                        "light_violation",
                        "повтор после предупреждения",
                        "bait,warning_escalation",
                        90,
                        "deepseek:deepseek-chat",
                        0.88,
                        None,
                        now - 6 * 60 * 60,
                        "вот теперь пауза",
                        "",
                        "",
                    ),
                )

            snapshot = repository.get_user_history_snapshot(guild_id=7, user_id=77)

            self.assertEqual(snapshot.warning_count_24h, 1)
            self.assertEqual(snapshot.light_violation_count_72h, 1)
            self.assertEqual(snapshot.last_decision, "light_violation")
            self.assertIn("warning", snapshot.recent_events[1])
            self.assertGreaterEqual(snapshot.last_sanction_age_minutes, 0)


if __name__ == "__main__":
    unittest.main()
