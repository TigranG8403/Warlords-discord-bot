from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path


def mark_ready_from_env() -> None:
    raw_path = os.getenv("BOT_READY_FILE", "").strip()
    if not raw_path:
        return

    ready_path = Path(raw_path)
    ready_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = ready_path.with_name(f".{ready_path.name}.tmp")
    temporary_path.write_text(
        f"{datetime.now(timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )
    temporary_path.replace(ready_path)
