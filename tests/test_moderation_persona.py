from __future__ import annotations

import unittest

from tests import support  # noqa: F401
from modules.moderation.persona import PERSONA_FACTS, PERSONA_STYLE


class ModerationPersonaTests(unittest.TestCase):
    def test_persona_facts_keep_known_server_answers(self) -> None:
        joined = " ".join(PERSONA_FACTS).lower()

        self.assertIn("300", joined)
        self.assertIn("500", joined)
        self.assertIn("jamb1", joined)
        self.assertIn("messire", joined)

    def test_persona_style_is_short_lively_and_not_lecturing(self) -> None:
        lowered = PERSONA_STYLE.lower()

        self.assertIn("лёгкой усмешкой", lowered)
        self.assertIn("без клоунады", lowered)
        self.assertIn("не делай ответы холодными", lowered)
        self.assertIn("не читай лекции", lowered)
        self.assertIn("молчание — редкий случай", lowered)
        self.assertIn("не искажай известные факты", lowered)


if __name__ == "__main__":
    unittest.main()
