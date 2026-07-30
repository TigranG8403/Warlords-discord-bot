from __future__ import annotations

from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import sqlite3
import unittest

from tests import support  # noqa: F401

from modules import DEFAULT_MODULES
from deploy.migrate_legacy_state import (
    ENABLED_MODULES,
    build_production_env,
    collect_update_user_ids,
    migrate_databases,
    read_env_file,
    write_systemd_env,
)


class LegacyEnvironmentMigrationTests(unittest.TestCase):
    def test_production_module_allowlist_matches_supported_modules(self) -> None:
        self.assertEqual(tuple(ENABLED_MODULES.split(",")), DEFAULT_MODULES)

    def test_old_moderation_settings_are_mapped_without_old_behavior(self) -> None:
        values = build_production_env(
            {
                "DISCORD_TOKEN": "discord-secret",
                "APP_COMMAND_GUILD_ID": "100",
                "MODERATION_AI_BASE_URL": "https://ai.example.com/v1",
                "MODERATION_AI_API_KEY": "ai-secret",
                "MODERATION_AI_MODEL": "example-model",
            },
            {"PANEL_INITIAL_ALLOWED_DISCORD_IDS": "20,10"},
        )

        self.assertEqual(values["AI_BASE_URL"], "https://ai.example.com/v1")
        self.assertEqual(values["AI_API_KEY"], "ai-secret")
        self.assertEqual(values["BOT_UPDATE_ALLOWED_USER_IDS"], "10,20")
        self.assertNotIn("MODERATION_AI_BASE_URL", values)
        self.assertNotIn("DISCORDAUTH_BRIDGE_TOKEN", values)

    def test_panel_user_file_is_included_in_update_allowlist(self) -> None:
        with TemporaryDirectory() as temp_dir:
            allowed_users_path = Path(temp_dir) / "allowed.json"
            allowed_users_path.write_text(
                json.dumps({"users": [{"user_id": "30"}, {"user_id": "10"}]}),
                encoding="utf-8",
            )
            panel_env = {
                "PANEL_INITIAL_ALLOWED_DISCORD_IDS": "20",
                "PANEL_ALLOWED_USERS_FILE": str(allowed_users_path),
            }

            self.assertEqual(collect_update_user_ids(panel_env), ("10", "20", "30"))

    def test_environment_file_round_trip_preserves_special_characters(self) -> None:
        with TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / "bot.env"
            write_systemd_env(env_path, {"DISCORD_TOKEN": 'a\\b"c'})

            self.assertEqual(read_env_file(env_path)["DISCORD_TOKEN"], 'a\\b"c')
            if os.name == "posix":
                self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)


class LegacyDatabaseMigrationTests(unittest.TestCase):
    def test_only_active_databases_are_restored(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "legacy"
            backup = root / "backup"
            target = root / "target"
            legacy.mkdir()

            with closing(sqlite3.connect(legacy / "tickets.sqlite3")) as connection:
                connection.execute("CREATE TABLE sample (value TEXT)")
                connection.execute("INSERT INTO sample VALUES ('ticket')")
                connection.commit()
            with closing(sqlite3.connect(legacy / "moderation.sqlite3")) as connection:
                connection.execute("CREATE TABLE sample (value TEXT)")
                connection.commit()

            active_count, archived_count = migrate_databases(legacy, backup, target)

            self.assertEqual(active_count, 1)
            self.assertEqual(archived_count, 2)
            self.assertTrue((target / "tickets.sqlite3").is_file())
            self.assertFalse((target / "moderation.sqlite3").exists())
            self.assertTrue((backup / "moderation.sqlite3").is_file())


if __name__ == "__main__":
    unittest.main()
