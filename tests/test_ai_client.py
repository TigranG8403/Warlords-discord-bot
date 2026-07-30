from __future__ import annotations

import asyncio
import json
import os
import unittest
from unittest.mock import patch

from tests import support  # noqa: F401

from integrations.ai import AiClientConfig, AiClientError, AiMessage, OpenAiCompatibleClient


class AiClientConfigTests(unittest.TestCase):
    def test_remote_http_endpoint_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            AiClientConfig(base_url="http://ai.example.com/v1", model="example")

    def test_loopback_http_endpoint_is_allowed(self) -> None:
        config = AiClientConfig(base_url="http://127.0.0.1:11434/v1/", model="local")

        self.assertEqual(config.base_url, "http://127.0.0.1:11434/v1")

    def test_partial_environment_configuration_is_rejected(self) -> None:
        with patch.dict(os.environ, {"AI_BASE_URL": "https://ai.example.com/v1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "configured together"):
                AiClientConfig.from_env()


class OpenAiCompatibleClientTests(unittest.TestCase):
    def test_complete_builds_authenticated_request(self) -> None:
        captured: dict[str, object] = {}

        def transport(request, timeout_seconds: float, max_response_bytes: int) -> bytes:
            captured["url"] = request.full_url
            captured["authorization"] = request.get_header("Authorization")
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout_seconds
            captured["limit"] = max_response_bytes
            return json.dumps(
                {"choices": [{"message": {"content": " Готово "}}]}
            ).encode("utf-8")

        client = OpenAiCompatibleClient(
            AiClientConfig(
                base_url="https://ai.example.com/v1",
                model="example-model",
                api_key="secret",
            ),
            transport=transport,
        )

        result = client.complete_sync(
            [AiMessage("user", "Проверь здание")],
            temperature=0.2,
            max_tokens=200,
        )

        self.assertEqual(result, "Готово")
        self.assertEqual(captured["url"], "https://ai.example.com/v1/chat/completions")
        self.assertEqual(captured["authorization"], "Bearer secret")
        self.assertEqual(captured["payload"]["model"], "example-model")
        self.assertEqual(captured["payload"]["temperature"], 0.2)
        self.assertEqual(captured["timeout"], 30.0)
        self.assertEqual(captured["limit"], 1_000_000)

    def test_complete_json_requires_an_object(self) -> None:
        def transport(_request, _timeout_seconds: float, _max_response_bytes: int) -> bytes:
            return json.dumps(
                {"choices": [{"message": {"content": "[]"}}]}
            ).encode("utf-8")

        client = OpenAiCompatibleClient(
            AiClientConfig(base_url="https://ai.example.com/v1", model="example"),
            transport=transport,
        )

        with self.assertRaisesRegex(AiClientError, "must be an object"):
            asyncio.run(client.complete_json([AiMessage("user", "Проверка")]))

    def test_invalid_provider_response_is_wrapped(self) -> None:
        client = OpenAiCompatibleClient(
            AiClientConfig(base_url="https://ai.example.com/v1", model="example"),
            transport=lambda *_args: b"{}",
        )

        with self.assertRaisesRegex(AiClientError, "invalid completion"):
            client.complete_sync([AiMessage("user", "Проверка")])


if __name__ == "__main__":
    unittest.main()
