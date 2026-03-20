from __future__ import annotations

import unittest

from tests import support  # noqa: F401
from modules.moderation.knowledge import (
    DEFAULT_SERVER_FACTS,
    EXTRA_KNOWN_PROFILES,
    EXTRA_SERVER_FACTS,
    SEEDED_KNOWN_PROFILES,
)


class ModerationKnowledgeTests(unittest.TestCase):
    def test_server_facts_include_related_projects_and_mods(self) -> None:
        facts = "\n".join(DEFAULT_SERVER_FACTS + EXTRA_SERVER_FACTS)

        self.assertIn("Варферия", facts)
        self.assertIn("Minecraft Warfare", facts)
        self.assertIn("Рекруты", facts)
        self.assertIn("Laurel of Ages", facts)
        self.assertIn("сервер завтра в 3", facts)

    def test_known_profiles_include_related_people_and_aliases(self) -> None:
        profiles = {profile.discord_id: profile for profile in SEEDED_KNOWN_PROFILES + EXTRA_KNOWN_PROFILES}

        self.assertIn(451031568895705109, profiles)
        self.assertIn(761296747715624960, profiles)
        self.assertIn(745608321435959318, profiles)
        self.assertIn(238399235744071680, profiles)
        self.assertIn(389098582604775436, profiles)
        self.assertIn("Фемыч", profiles[745608321435959318].aliases)
        self.assertIn("Ярс", profiles[389098582604775436].aliases)


if __name__ == "__main__":
    unittest.main()
