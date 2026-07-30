from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests import support  # noqa: F401

from core.readiness import mark_ready_from_env


class ReadinessTests(unittest.TestCase):
    def test_marker_is_written_atomically_when_configured(self) -> None:
        with TemporaryDirectory() as temp_dir:
            ready_path = Path(temp_dir) / "runtime" / "ready"
            with patch.dict(os.environ, {"BOT_READY_FILE": str(ready_path)}, clear=True):
                mark_ready_from_env()

            self.assertTrue(ready_path.is_file())
            self.assertRegex(ready_path.read_text(encoding="utf-8"), r"^\d{4}-\d{2}-\d{2}T")
            self.assertFalse((ready_path.parent / ".ready.tmp").exists())

    def test_marker_is_optional_for_local_development(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            mark_ready_from_env()
