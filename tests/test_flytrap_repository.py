from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests import support  # noqa: F401

from modules.flytrap.models import FlytrapAction, FlytrapConfig
from modules.flytrap.repository import FlytrapRepository


class FlytrapRepositoryTests(unittest.TestCase):
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
