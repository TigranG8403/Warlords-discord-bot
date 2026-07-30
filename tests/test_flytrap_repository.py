from __future__ import annotations

from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from tests import support  # noqa: F401

from modules.flytrap.models import FlytrapAction, FlytrapConfig
from modules.flytrap.repository import FlytrapRepository


class FlytrapRepositoryTests(unittest.TestCase):
    def test_adds_counter_to_existing_database(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "flytrap.sqlite3"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE flytrap_configs (
                        guild_id INTEGER PRIMARY KEY,
                        channel_id INTEGER NOT NULL UNIQUE,
                        log_channel_id INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        warning_message_id INTEGER NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO flytrap_configs (
                        guild_id,
                        channel_id,
                        log_channel_id,
                        action,
                        warning_message_id
                    )
                    VALUES (1, 2, 3, 'softban', 4)
                    """
                )
                connection.commit()

            repository = FlytrapRepository(database_path)

            config = repository.get_config(1)
            self.assertIsNotNone(config)
            self.assertEqual(config.moderated_count, 0)

    def test_config_lifecycle(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = FlytrapRepository(Path(temp_dir) / "flytrap.sqlite3")
            config = FlytrapConfig(
                guild_id=1,
                channel_id=2,
                log_channel_id=3,
                action=FlytrapAction.SOFTBAN,
                warning_message_id=4,
            )

            repository.set_config(config)

            self.assertEqual(repository.get_config(1), config)
            self.assertEqual(repository.get_config_by_channel(2), config)
            self.assertEqual(repository.list_configs(), [config])

            repository.delete_config(1)
            self.assertIsNone(repository.get_config(1))

    def test_moderated_count_is_incremented_and_preserved_on_reconfiguration(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = FlytrapRepository(Path(temp_dir) / "flytrap.sqlite3")
            repository.set_config(
                FlytrapConfig(
                    guild_id=1,
                    channel_id=2,
                    log_channel_id=3,
                    action=FlytrapAction.SOFTBAN,
                    warning_message_id=4,
                )
            )

            repository.claim_incident(
                message_id=10,
                guild_id=1,
                channel_id=2,
                user_id=3,
                action=FlytrapAction.SOFTBAN,
            )
            self.assertEqual(
                repository.finish_handled_incident(message_id=10, guild_id=1),
                1,
            )

            repository.set_config(
                FlytrapConfig(
                    guild_id=1,
                    channel_id=5,
                    log_channel_id=6,
                    action=FlytrapAction.BAN,
                    warning_message_id=7,
                )
            )

            config = repository.get_config(1)
            self.assertIsNotNone(config)
            self.assertEqual(config.moderated_count, 1)

    def test_incident_can_only_be_claimed_once(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = FlytrapRepository(Path(temp_dir) / "flytrap.sqlite3")

            first_claim = repository.claim_incident(
                message_id=10,
                guild_id=1,
                channel_id=2,
                user_id=3,
                action=FlytrapAction.BAN,
            )
            second_claim = repository.claim_incident(
                message_id=10,
                guild_id=1,
                channel_id=2,
                user_id=3,
                action=FlytrapAction.BAN,
            )
            repository.finish_incident(10, status="handled")

            self.assertTrue(first_claim)
            self.assertFalse(second_claim)
            self.assertEqual(repository.get_incident_status(10), "handled")


if __name__ == "__main__":
    unittest.main()
