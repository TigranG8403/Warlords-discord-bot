from __future__ import annotations

import hmac
import os
import secrets
import subprocess
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

try:
    from .git_ops import GitRepository, GitSnapshot, format_tracking_status
    from .render import DashboardPageData, FlashMessage, LoginPageData, render_dashboard_page, render_login_page
except ImportError:
    from admin_panel.git_ops import GitRepository, GitSnapshot, format_tracking_status
    from admin_panel.render import DashboardPageData, FlashMessage, LoginPageData, render_dashboard_page, render_login_page


SESSION_COOKIE_NAME = "warlords_panel_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
DEFAULT_LOG_LINES = 40
DEFAULT_PANEL_HOST = "127.0.0.1"
DEFAULT_PANEL_PORT = 8788
DEFAULT_GIT_REMOTE = "origin"
OUTPUT_LIMIT = 24_000


@dataclass(frozen=True)
class PanelConfig:
    host: str
    port: int
    password: str
    service_name: str
    app_dir: str
    git_remote: str
    app_user: str
    log_lines: int


@dataclass
class SessionData:
    csrf_token: str
    expires_at: float
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

    def create(self) -> tuple[str, SessionData]:
        session_id = secrets.token_urlsafe(32)
        session = SessionData(
            csrf_token=secrets.token_urlsafe(24),
            expires_at=self._time_func() + self._ttl_seconds,
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


def load_config() -> PanelConfig:
    password = os.getenv("PANEL_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("PANEL_PASSWORD is required for the admin panel.")

    return PanelConfig(
        host=os.getenv("PANEL_HOST", DEFAULT_PANEL_HOST).strip() or DEFAULT_PANEL_HOST,
        port=parse_int_env("PANEL_PORT", DEFAULT_PANEL_PORT),
        password=password,
        service_name=os.getenv("BOT_SERVICE_NAME", "warlords-bot").strip() or "warlords-bot",
        app_dir=os.getenv("BOT_APP_DIR", "/opt/warlords-bot").strip() or "/opt/warlords-bot",
        git_remote=os.getenv("BOT_GIT_REMOTE", DEFAULT_GIT_REMOTE).strip() or DEFAULT_GIT_REMOTE,
        app_user=os.getenv("BOT_APP_USER", "warlords").strip() or "warlords",
        log_lines=parse_int_env("BOT_LOG_LINES", DEFAULT_LOG_LINES),
    )


def parse_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    return int(raw_value)


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


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], request_handler_class, config: PanelConfig) -> None:
        super().__init__(server_address, request_handler_class)
        self.config = config
        self.sessions = SessionStore()
        self.repo = GitRepository(
            self.run,
            app_dir=self.config.app_dir,
            app_user=self.config.app_user,
            remote_name=self.config.git_remote,
        )

    def run(self, args: list[str], *, timeout: int = 30) -> CommandResult:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part).strip()
        return CommandResult(returncode=completed.returncode, output=trim_output(output))

    def sudo_systemctl(self, *args: str, timeout: int = 30) -> CommandResult:
        return self.run(["sudo", "-n", "systemctl", *args], timeout=timeout)

    def service_snapshot(self) -> dict[str, str]:
        result = self.sudo_systemctl(
            "show",
            self.config.service_name,
            "--property=Id,Description,LoadState,ActiveState,SubState,MainPID,ExecMainPID,ExecMainStatus,ActiveEnterTimestamp,FragmentPath",
        )
        if result.returncode != 0:
            raise RuntimeError(result.output or "Failed to query service status.")
        data = parse_key_value_output(result.output)
        data["status_text"] = build_status_text(data.get("ActiveState", ""), data.get("SubState", ""))
        return data

    def git_snapshot(self) -> GitSnapshot:
        return self.repo.snapshot()

    def logs_snapshot(self) -> str:
        result = self.run(
            [
                "sudo",
                "-n",
                "journalctl",
                "-u",
                self.config.service_name,
                "-n",
                str(self.config.log_lines),
                "--no-pager",
            ],
            timeout=30,
        )
        return result.output or "No logs yet."

    def perform_action(self, action: str, *, branch: str = "") -> tuple[str, str, str]:
        actions = {
            "fetch": self._fetch_remote,
            "start": self._start_service,
            "stop": self._stop_service,
            "restart": self._restart_service,
            "update": self._update_service,
            "switch_branch": lambda: self._switch_branch(branch),
        }
        handler = actions.get(action)
        if handler is None:
            return ("error", "Unknown action", f"Unsupported action: {action}")
        return handler()

    def _fetch_remote(self) -> tuple[str, str, str]:
        result = self.repo.fetch_remote()
        if result.returncode != 0:
            return ("error", "Fetch failed", result.output or "git fetch failed")
        return ("success", "Git refs updated", result.output or f"Fetched {self.config.git_remote}.")

    def _start_service(self) -> tuple[str, str, str]:
        result = self.sudo_systemctl("start", self.config.service_name)
        if result.returncode != 0:
            return ("error", "Start failed", result.output or "systemctl start failed")
        status = self.sudo_systemctl("is-active", self.config.service_name)
        return ("success", "Bot started", status.output or "Service started.")

    def _stop_service(self) -> tuple[str, str, str]:
        result = self.sudo_systemctl("stop", self.config.service_name)
        if result.returncode != 0:
            return ("error", "Stop failed", result.output or "systemctl stop failed")
        status = self.sudo_systemctl("is-active", self.config.service_name)
        return ("success", "Bot stopped", status.output or "Service stopped.")

    def _restart_service(self) -> tuple[str, str, str]:
        result = self.sudo_systemctl("restart", self.config.service_name, timeout=60)
        if result.returncode != 0:
            return ("error", "Restart failed", result.output or "systemctl restart failed")
        status = self.sudo_systemctl("status", "--no-pager", self.config.service_name, timeout=60)
        return ("success", "Bot restarted", status.output or "Service restarted.")

    def _update_service(self) -> tuple[str, str, str]:
        results = self.repo.update_current_branch()
        restart_result = self.sudo_systemctl("restart", self.config.service_name, timeout=60)
        return combine_action_results(
            success_title="Bot updated",
            failure_title="Update failed",
            final_failure_title="Restart after update failed",
            results=results,
            final_result=restart_result,
            fallback_output="Update completed.",
        )

    def _switch_branch(self, branch: str) -> tuple[str, str, str]:
        results = self.repo.switch_branch(branch)
        restart_result = self.sudo_systemctl("restart", self.config.service_name, timeout=60)
        return combine_action_results(
            success_title=f"Switched to {branch}",
            failure_title=f"Switch to {branch} failed",
            final_failure_title="Restart after branch switch failed",
            results=results,
            final_result=restart_result,
            fallback_output="Branch switched.",
        )


class PanelHandler(BaseHTTPRequestHandler):
    server: PanelServer

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_text("ok\n")
            return

        session_id, session = self._get_session()
        if self.path == "/login":
            if session is not None:
                self._redirect("/")
                return
            self._render_login()
            return

        if self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if session is None:
            self._redirect("/login")
            return

        self._render_dashboard(session_id, session)

    def do_POST(self) -> None:
        fields = self._parse_form()
        if self.path == "/login":
            self._handle_login(fields)
            return
        if self.path == "/logout":
            self._handle_logout()
            return
        if self.path == "/action":
            self._handle_action(fields)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args) -> None:
        return

    def _handle_login(self, fields: dict[str, list[str]]) -> None:
        password = fields.get("password", [""])[0]
        if not constant_time_equal(password, self.server.config.password):
            self._render_login(error="Invalid panel password.")
            return

        session_id, _ = self.server.sessions.create()
        self.send_response(HTTPStatus.SEE_OTHER)
        self._set_security_headers()
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", build_session_cookie(session_id))
        self.end_headers()

    def _handle_logout(self) -> None:
        session_id, _ = self._get_session()
        self.server.sessions.delete(session_id)
        self.send_response(HTTPStatus.SEE_OTHER)
        self._set_security_headers()
        self.send_header("Location", "/login")
        self.send_header("Set-Cookie", expire_session_cookie())
        self.end_headers()

    def _handle_action(self, fields: dict[str, list[str]]) -> None:
        session_id, session = self._get_session()
        if session_id is None or session is None:
            self._redirect("/login")
            return

        csrf_token = fields.get("csrf_token", [""])[0]
        if not constant_time_equal(csrf_token, session.csrf_token):
            self.server.sessions.set_flash(
                session_id,
                level="error",
                title="Invalid token",
                output="The session expired or the request did not come from the panel. Refresh the page and try again.",
            )
            self._redirect("/")
            return

        action = fields.get("action", [""])[0]
        branch = fields.get("branch", [""])[0]
        level, title, output = self.server.perform_action(action, branch=branch)
        self.server.sessions.set_flash(session_id, level=level, title=title, output=output)
        self._redirect("/")

    def _render_login(self, *, error: str | None = None) -> None:
        self._send_html(render_login_page(LoginPageData(title="Warlords Bot Panel", error=error)))

    def _render_dashboard(self, session_id: str, session: SessionData) -> None:
        flash = self.server.sessions.pop_flash(session_id)
        flash_message = None
        if flash is not None:
            flash_message = FlashMessage(level=flash[0], title=flash[1], output=flash[2])

        service_data = self.server.service_snapshot()
        git_data = self.server.git_snapshot()
        page = DashboardPageData(
            csrf_token=session.csrf_token,
            service_name=self.server.config.service_name,
            service_data=service_data,
            git_data=git_data,
            tracking_status=format_tracking_status(git_data.ahead, git_data.behind),
            logs=self.server.logs_snapshot(),
            flash=flash_message,
        )
        self._send_html(render_dashboard_page(page))

    def _parse_form(self) -> dict[str, list[str]]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8", "replace")
        return parse_qs(raw_body, keep_blank_values=True)

    def _get_session(self) -> tuple[str | None, SessionData | None]:
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None, None
        cookies = SimpleCookie()
        cookies.load(cookie_header)
        morsel = cookies.get(SESSION_COOKIE_NAME)
        session_id = morsel.value if morsel is not None else None
        return session_id, self.server.sessions.get(session_id)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self._set_security_headers()
        self.send_header("Location", location)
        self.end_headers()

    def _send_html(self, body: str) -> None:
        content = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self._set_security_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_text(self, body: str) -> None:
        content = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self._set_security_headers()
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _set_security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        )


def combine_action_results(
    *,
    success_title: str,
    failure_title: str,
    final_failure_title: str,
    results: list[CommandResult],
    final_result: CommandResult,
    fallback_output: str,
) -> tuple[str, str, str]:
    parts = [part for part in [*(result.output for result in results), final_result.output] if part]
    output = "\n\n".join(parts).strip() or fallback_output
    for result in results:
        if result.returncode != 0:
            return ("error", failure_title, output)
    if final_result.returncode != 0:
        return ("error", final_failure_title, output)
    return ("success", success_title, output)


def build_status_text(active_state: str, sub_state: str) -> str:
    if not active_state:
        return "Unknown"
    if not sub_state:
        return active_state.capitalize()
    return f"{active_state.capitalize()} / {sub_state}"


def build_session_cookie(session_id: str) -> str:
    return (
        f"{SESSION_COOKIE_NAME}={session_id}; "
        "HttpOnly; Path=/; SameSite=Strict; Max-Age=28800"
    )


def expire_session_cookie() -> str:
    return (
        f"{SESSION_COOKIE_NAME}=deleted; "
        "HttpOnly; Path=/; SameSite=Strict; Max-Age=0"
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


def main() -> None:
    env_path = os.getenv("PANEL_ENV_FILE")
    if env_path:
        load_dotenv_file(Path(env_path))

    config = load_config()
    server = PanelServer((config.host, config.port), PanelHandler, config)
    print(f"Warlords admin panel listening on http://{config.host}:{config.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
