from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests import support  # noqa: F401
from modules.discordauth.module import _extract_link_code_from_message, _resolve_player_query
from modules.discordauth.service import DiscordAuthService


class DiscordAuthModuleTests(unittest.TestCase):
    def test_extract_link_code_accepts_plain_message_only(self) -> None:
        self.assertEqual(_extract_link_code_from_message("link abc123"), "abc123")
        self.assertEqual(_extract_link_code_from_message("link"), "")
        self.assertIsNone(_extract_link_code_from_message("/link abc123"))

    def test_resolve_player_query_finds_exact_name_and_uuid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = DiscordAuthService(Path(temp_dir) / "discordauth.sqlite3")
            service.touch_player_auth(player_uuid="uuid-steve", player_name="Steve", ip_address="127.0.0.1")

            by_name, name_error = _resolve_player_query(service, "Steve")
            by_uuid, uuid_error = _resolve_player_query(service, "uuid-steve")

            self.assertIsNotNone(by_name)
            self.assertIsNone(name_error)
            self.assertEqual(by_name.player_uuid, "uuid-steve")
            self.assertIsNotNone(by_uuid)
            self.assertIsNone(uuid_error)
            self.assertEqual(by_uuid.player_name, "Steve")

    def test_resolve_player_query_reports_ambiguous_partial_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = DiscordAuthService(Path(temp_dir) / "discordauth.sqlite3")
            service.touch_player_auth(player_uuid="uuid-1", player_name="SteveOne", ip_address="127.0.0.1")
            service.touch_player_auth(player_uuid="uuid-2", player_name="SteveTwo", ip_address="127.0.0.2")

            record, error = _resolve_player_query(service, "Steve")

            self.assertIsNone(record)
            self.assertIsNotNone(error)
            self.assertIn("SteveOne", error)
            self.assertIn("SteveTwo", error)
            self.assertIn("UUID", error)


if __name__ == "__main__":
    unittest.main()
