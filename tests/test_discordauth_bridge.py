from __future__ import annotations

import unittest
from http import HTTPStatus

from tests import support  # noqa: F401
from modules.discordauth.bridge import (
    BridgeRequestError,
    build_login_request_content,
    describe_inactive_login_request,
    parse_bridge_json_body,
)


class DiscordAuthBridgeTests(unittest.TestCase):
    def test_parse_bridge_json_body_rejects_invalid_json(self) -> None:
        with self.assertRaises(BridgeRequestError) as context:
            parse_bridge_json_body('{"players":\\}')

        self.assertEqual(context.exception.status, HTTPStatus.BAD_REQUEST)
        self.assertIn("Invalid JSON body", context.exception.message)

    def test_parse_bridge_json_body_rejects_non_object_payload(self) -> None:
        with self.assertRaises(BridgeRequestError) as context:
            parse_bridge_json_body("[]")

        self.assertEqual(context.exception.status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(context.exception.message, "JSON body must be an object.")

    def test_parse_bridge_json_body_accepts_empty_payload(self) -> None:
        self.assertEqual(parse_bridge_json_body("   "), {})

    def test_build_login_request_content_keeps_only_ip(self) -> None:
        content = build_login_request_content("messire", "213.208.174.146")

        self.assertIn("Игрок **messire** пытается войти на сервер.", content)
        self.assertIn("IP: `213.208.174.146`", content)
        self.assertNotIn("Адрес:", content)

    def test_describe_inactive_login_request_handles_cancelled_sessions(self) -> None:
        self.assertEqual(
            describe_inactive_login_request("CANCELLED"),
            "Запрос уже недействителен: игрок вышел с сервера.",
        )


if __name__ == "__main__":
    unittest.main()
