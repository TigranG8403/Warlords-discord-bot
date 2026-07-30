from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests import support  # noqa: F401

from modules.greetings.models import GreetingsConfig
from modules.greetings.repository import GreetingsRepository


class GreetingsRepositoryTests(unittest.TestCase):
    def test_config_can_be_replaced_and_deleted(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = GreetingsRepository(Path(temp_dir) / "greetings.sqlite3")
            repository.set_config(GreetingsConfig(guild_id=1, channel_id=10))
            repository.set_config(GreetingsConfig(guild_id=1, channel_id=20))

            self.assertEqual(
                repository.get_config(1),
                GreetingsConfig(guild_id=1, channel_id=20),
            )

            repository.delete_config(1)
            self.assertIsNone(repository.get_config(1))
