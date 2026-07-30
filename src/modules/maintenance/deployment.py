from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path


DEPLOY_REQUEST_PATH = Path("/var/lib/warlords-bot/deploy.request")


class DeploymentError(RuntimeError):
    """Raised when a production deployment cannot be queued."""


class DeploymentController:
    def __init__(self, request_path: Path = DEPLOY_REQUEST_PATH) -> None:
        self._request_path = request_path
        self._lock = asyncio.Lock()

    async def trigger_update(self) -> None:
        async with self._lock:
            try:
                await asyncio.to_thread(self._create_request)
            except FileExistsError as error:
                raise DeploymentError("Обновление уже выполняется.") from error
            except OSError as error:
                raise DeploymentError(
                    "Не удалось создать безопасную заявку на обновление."
                ) from error

    def _create_request(self) -> None:
        requested_at = datetime.now(timezone.utc).isoformat()
        with self._request_path.open("x", encoding="utf-8") as request_file:
            request_file.write(f"{requested_at}\n")
