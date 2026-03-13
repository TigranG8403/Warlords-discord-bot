from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests import support  # noqa: F401

from modules.tickets.config import TicketGuildSettings
from modules.tickets.repository import TicketRepository


class TicketRepositoryTests(unittest.TestCase):
    def test_create_update_and_close_ticket(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = TicketRepository(Path(temp_dir) / "tickets.sqlite3")
            repository.initialize()
            created_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

            record = repository.create_ticket(
                guild_id=1,
                channel_id=10,
                creator_id=100,
                ticket_type="other",
                panel_type="support",
                subject="Тестовый тикет",
                details={"subject": "Тестовый тикет"},
                status="open",
                created_at=created_at,
            )

            self.assertEqual(record.subject, "Тестовый тикет")
            self.assertEqual(repository.get_active_by_creator_and_type(1, 100, "other").id, record.id)

            updated = repository.set_message_id(10, 55, created_at)
            self.assertIsNotNone(updated)
            self.assertEqual(updated.message_id, 55)

            assigned = repository.assign_ticket(10, 900, "in_progress", created_at)
            self.assertIsNotNone(assigned)
            self.assertEqual(assigned.assigned_to, 900)
            self.assertEqual(assigned.status, "in_progress")

            closed = repository.mark_closed(
                10,
                closed_by=900,
                close_reason="Решено",
                closed_at=created_at,
            )
            self.assertIsNotNone(closed)
            self.assertEqual(closed.close_reason, "Решено")
            self.assertIsNone(repository.get_active_by_creator_and_type(1, 100, "other"))

    def test_set_get_and_delete_guild_settings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = TicketRepository(Path(temp_dir) / "tickets.sqlite3")
            repository.initialize()
            settings = TicketGuildSettings(
                guild_id=1,
                ticket_category_id=10,
                fraction_category_id=11,
                rp_category_id=12,
                log_channel_id=13,
                support_role_id=14,
                staff_call_cooldown_minutes=5,
            )

            repository.set_guild_settings(settings)
            self.assertEqual(repository.get_guild_settings(1), settings)

            updated = TicketGuildSettings(
                guild_id=1,
                ticket_category_id=20,
                fraction_category_id=21,
                rp_category_id=22,
                log_channel_id=23,
                support_role_id=24,
                staff_call_cooldown_minutes=15,
            )
            repository.set_guild_settings(updated)
            self.assertEqual(repository.get_guild_settings(1), updated)

            repository.delete_guild_settings(1)
            self.assertIsNone(repository.get_guild_settings(1))


if __name__ == "__main__":
    unittest.main()
