from __future__ import annotations

from pathlib import Path

from .config import DEFAULT_DATABASE_PATH
from .service_dashboard import DiscordAuthDashboardMixin
from .service_guilds import DiscordAuthGuildSettingsMixin
from .service_players import DiscordAuthPlayersMixin
from .service_sanctions import DiscordAuthSanctionsMixin
from .service_sessions import DiscordAuthSessionsMixin
from .service_storage import DiscordAuthStorageMixin


class DiscordAuthService(
    DiscordAuthGuildSettingsMixin,
    DiscordAuthPlayersMixin,
    DiscordAuthSanctionsMixin,
    DiscordAuthSessionsMixin,
    DiscordAuthDashboardMixin,
    DiscordAuthStorageMixin,
):
    def __init__(self, database_path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
