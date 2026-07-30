from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests import support  # noqa: F401

from modules.maintenance.access import parse_allowed_user_ids
from modules.maintenance.deployment import DeploymentController, DeploymentError


class MaintenanceAccessTests(unittest.TestCase):
    def test_allowed_user_ids_are_deduplicated(self) -> None:
        self.assertEqual(
            parse_allowed_user_ids(" 10,20,10 "),
            frozenset({10, 20}),
        )

    def test_invalid_allowed_user_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Discord user IDs"):
            parse_allowed_user_ids("10,not-an-id")


class DeploymentControllerTests(unittest.TestCase):
    def test_trigger_creates_a_fixed_request_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            request_path = Path(temp_dir) / "deploy.request"
            controller = DeploymentController(request_path)

            asyncio.run(controller.trigger_update())

            self.assertTrue(request_path.is_file())
            self.assertRegex(request_path.read_text(encoding="utf-8"), r"^\d{4}-\d{2}-\d{2}T")

    def test_existing_request_prevents_duplicate_deployment(self) -> None:
        with TemporaryDirectory() as temp_dir:
            request_path = Path(temp_dir) / "deploy.request"
            request_path.write_text("already queued\n", encoding="utf-8")
            controller = DeploymentController(request_path)

            with self.assertRaisesRegex(DeploymentError, "уже выполняется"):
                asyncio.run(controller.trigger_update())


if __name__ == "__main__":
    unittest.main()
