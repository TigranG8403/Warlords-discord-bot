from __future__ import annotations

import json
import unittest

from tests import support  # noqa: F401
from modules.moderation.ai_server import _parse_model_json, _payload_from_request


class ModerationAiServerTests(unittest.TestCase):
    def test_parse_model_json_extracts_embedded_object(self) -> None:
        parsed = _parse_model_json(
            'Результат:\n```json\n{"decision":"review","confidence":0.7,"reason":"спорный контекст"}\n```'
        )

        self.assertEqual(parsed["decision"], "review")
        self.assertEqual(parsed["confidence"], 0.7)

    def test_payload_from_request_parses_recent_messages(self) -> None:
        payload = _payload_from_request(
            json.dumps(
                {
                    "guild_id": 1,
                    "guild_name": "Warlords",
                    "channel_id": 2,
                    "channel_name": "chat",
                    "message_id": 3,
                    "author_id": 4,
                    "author_name": "user",
                    "author_display_name": "User",
                    "content": "иди нахуй долбаеб",
                    "recent_messages": [
                        {
                            "author_id": 5,
                            "author_name": "Other",
                            "content": "что случилось",
                            "created_at": 10,
                            "is_target_author": False,
                        }
                    ],
                }
            ).encode("utf-8")
        )

        self.assertEqual(payload.guild_id, 1)
        self.assertEqual(len(payload.recent_messages), 1)
        self.assertEqual(payload.recent_messages[0].author_name, "Other")


if __name__ == "__main__":
    unittest.main()
