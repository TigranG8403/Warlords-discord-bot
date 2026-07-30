from __future__ import annotations

import unittest

from tests import support  # noqa: F401

from modules.welcome.content import EMBED_DESCRIPTION


class WelcomeContentTests(unittest.TestCase):
    def test_description_is_valid_for_discord_embed(self) -> None:
        self.assertLessEqual(len(EMBED_DESCRIPTION), 4096)
        self.assertIn("<#1352161207657693249>", EMBED_DESCRIPTION)


if __name__ == "__main__":
    unittest.main()
