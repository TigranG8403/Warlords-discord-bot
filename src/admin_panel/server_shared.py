from __future__ import annotations

import hmac
import os
import pkgutil
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .discord_auth import DiscordOAuthConfig
from .render import BotModuleCardView


SESSION_COOKIE_NAME = "warlords_panel_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
OAUTH_STATE_TTL_SECONDS = 10 * 60
DEFAULT_LOG_LINES = 40
DEFAULT_PANEL_HOST = "127.0.0.1"
DEFAULT_PANEL_PORT = 8788
DEFAULT_GIT_REMOTE = "origin"
OUTPUT_LIMIT = 24_000
MODULE_DESCRIPTIONS = {
    "discordauth": ("привязка Minecraft-аккаунтов и подтверждение входа", "link / login / access"),
    "tickets": ("тикет-система и панели обращений", "tickets / settings / runtime"),
    "roles": ("панель выбора ролей", "roles / panel"),
    "rules": ("публикация правил сервера", "rules / panel"),
    "welcome": ("welcome-панель и онбординг", "welcome / panel"),
    "presence": ("статус и активность бота", "presence"),
    "kompromat": ("модуль компроматов", "kompromat / panel / search"),
}


@dataclass(frozen=True)
class PanelConfig:
    host: str
    port: int
    password: str | None
    secure_cookie: bool
    service_name: str
    app_dir: str
    git_remote: str
    app_user: str
    log_lines: int
    allowed_users_file: str
    protected_discord_ids: tuple[str, ...]
    discord_oauth: DiscordOAuthConfig | None


@dataclass
class SessionData:
    csrf_token: str
    expires_at: float
    user_id: str | None = None
    display_name: str = ""
    username: str = ""
    avatar_url: str | None = None
    flash_level: str | None = None
    flash_title: str | None = None
    flash_output: str | None = None


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str


class SessionStore:
    def __init__(self, *, ttl_seconds: int = SESSION_TTL_SECONDS, time_func=time.time) -> None:
        self._ttl_seconds = ttl_seconds
        self._time_func = time_func
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionData] = {}

    def create(
        self,
        *,
        user_id: str | None = None,
        display_name: str = "",
        username: str = "",
        avatar_url: str | None = None,
    ) -> tuple[str, SessionData]:
        session_id = secrets.token_urlsafe(32)
        session = SessionData(
            csrf_token=secrets.token_urlsafe(24),
            expires_at=self._time_func() + self._ttl_seconds,
            user_id=user_id,
            display_name=display_name,
            username=username,
            avatar_url=avatar_url,
        )
        with self._lock:
            self._purge_locked()
            self._sessions[session_id] = session
        return session_id, session

    def get(self, session_id: str | None) -> SessionData | None:
        if not session_id:
            return None
        with self._lock:
            self._purge_locked()
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.expires_at = self._time_func() + self._ttl_seconds
            return session

    def delete(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)

    def set_flash(self, session_id: str, *, level: str, title: str, output: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return
            session.flash_level = level
            session.flash_title = title
            session.flash_output = output

    def pop_flash(self, session_id: str | None) -> tuple[str, str, str] | None:
        if not session_id:
            return None
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.flash_level is None:
                return None
            flash = (session.flash_level, session.flash_title or "", session.flash_output or "")
            session.flash_level = None
            session.flash_title = None
            session.flash_output = None
            return flash

    def _purge_locked(self) -> None:
        now = self._time_func()
        expired = [session_id for session_id, session in self._sessions.items() if session.expires_at <= now]
        for session_id in expired:
            self._sessions.pop(session_id, None)


class ExpiringTokenStore:
    def __init__(self, *, ttl_seconds: int, time_func=time.time) -> None:
        self._ttl_seconds = ttl_seconds
        self._time_func = time_func
        self._lock = threading.Lock()
        self._tokens: dict[str, float] = {}

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._purge_locked()
            self._tokens[token] = self._time_func() + self._ttl_seconds
        return token

    def consume(self, token: str) -> bool:
        if not token:
            return False
        with self._lock:
            self._purge_locked()
            expires_at = self._tokens.pop(token, None)
            return expires_at is not None and expires_at > self._time_func()

    def _purge_locked(self) -> None:
        now = self._time_func()
        expired = [token for token, expires_at in self._tokens.items() if expires_at <= now]
        for token in expired:
            self._tokens.pop(token, None)


def load_config() -> PanelConfig:
    app_dir = os.getenv("BOT_APP_DIR", "/opt/warlords-bot").strip() or "/opt/warlords-bot"
    password = os.getenv("PANEL_PASSWORD", "").strip() or None
    discord_client_id = os.getenv("PANEL_DISCORD_CLIENT_ID", "").strip()
    discord_client_secret = os.getenv("PANEL_DISCORD_CLIENT_SECRET", "").strip()
    discord_redirect_uri = os.getenv("PANEL_DISCORD_REDIRECT_URI", "").strip()

    discord_values = [discord_client_id, discord_client_secret, discord_redirect_uri]
    if any(discord_values) and not all(discord_values):
        raise RuntimeError("PANEL_DISCORD_CLIENT_ID, PANEL_DISCORD_CLIENT_SECRET, and PANEL_DISCORD_REDIRECT_URI must be configured together.")

    discord_oauth = None
    if all(discord_values):
        discord_oauth = DiscordOAuthConfig(
            client_id=discord_client_id,
            client_secret=discord_client_secret,
            redirect_uri=discord_redirect_uri,
        )

    if password is None and discord_oauth is None:
        raise RuntimeError("Configure PANEL_PASSWORD, Discord OAuth, or both for the admin panel.")

    protected_ids = tuple(parse_csv_env("PANEL_INITIAL_ALLOWED_DISCORD_IDS"))

    return PanelConfig(
        host=os.getenv("PANEL_HOST", DEFAULT_PANEL_HOST).strip() or DEFAULT_PANEL_HOST,
        port=parse_int_env("PANEL_PORT", DEFAULT_PANEL_PORT),
        password=password,
        secure_cookie=parse_bool_env("PANEL_SECURE_COOKIE", False),
        service_name=os.getenv("BOT_SERVICE_NAME", "warlords-bot").strip() or "warlords-bot",
        app_dir=app_dir,
        git_remote=os.getenv("BOT_GIT_REMOTE", DEFAULT_GIT_REMOTE).strip() or DEFAULT_GIT_REMOTE,
        app_user=os.getenv("BOT_APP_USER", "warlords").strip() or "warlords",
        log_lines=parse_int_env("BOT_LOG_LINES", DEFAULT_LOG_LINES),
        allowed_users_file=os.getenv("PANEL_ALLOWED_USERS_FILE", f"{app_dir}/data/panel_allowed_users.json").strip()
        or f"{app_dir}/data/panel_allowed_users.json",
        protected_discord_ids=protected_ids,
        discord_oauth=discord_oauth,
    )


def parse_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    return int(raw_value)


def parse_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def parse_csv_env(name: str) -> list[str]:
    raw_value = os.getenv(name, "")
    return [value.strip() for value in raw_value.split(",") if value.strip()]


def trim_output(output: str, limit: int = OUTPUT_LIMIT) -> str:
    normalized = output.strip()
    if len(normalized) <= limit:
        return normalized
    suffix = normalized[-limit:]
    return "[output truncated]\n" + suffix


def parse_key_value_output(output: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in output.splitlines():
        if not raw_line or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        data[key] = value
    return data


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def build_bot_module_cards() -> tuple[BotModuleCardView, ...]:
    enabled_raw = os.getenv("ENABLED_MODULES", "")
    enabled = {value.strip() for value in enabled_raw.split(",") if value.strip()}

    try:
        import modules
    except ImportError:
        return ()

    names = sorted(
        module.name
        for module in pkgutil.iter_modules(modules.__path__)
        if module.ispkg and not module.name.startswith("_")
    )
    cards: list[BotModuleCardView] = []
    for name in names:
        description, meta = MODULE_DESCRIPTIONS.get(name, ("внутренний модуль бота", f"module: {name}"))
        if enabled:
            state = "активен" if name in enabled else "отключён"
        else:
            state = "активен"
        cards.append(
            BotModuleCardView(
                name=name,
                description=description,
                state=state,
                meta=meta,
            )
        )
    return tuple(cards)


def build_status_text(active_state: str, sub_state: str) -> str:
    if not active_state:
        return "Unknown"
    if not sub_state:
        return active_state.capitalize()
    return f"{active_state.capitalize()} / {sub_state}"


def build_session_cookie(session_id: str, *, secure: bool) -> str:
    secure_attr = " Secure;" if secure else ""
    return (
        f"{SESSION_COOKIE_NAME}={session_id}; "
        f"HttpOnly; Path=/; SameSite=Lax; Max-Age=28800;{secure_attr}"
    )


def expire_session_cookie(*, secure: bool) -> str:
    secure_attr = " Secure;" if secure else ""
    return (
        f"{SESSION_COOKIE_NAME}=deleted; "
        f"HttpOnly; Path=/; SameSite=Lax; Max-Age=0;{secure_attr}"
    )


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
