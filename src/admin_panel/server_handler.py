from __future__ import annotations

from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from .discord_auth import build_authorize_url, exchange_code, fetch_identity
from .discordauth_dashboard import (
    _format_unix_timestamp,
    _normalize_discordauth_filter,
    build_dashboard_location,
    build_discordauth_dashboard,
)
from .git_ops import GitSnapshot, format_tracking_status
from .render import (
    AllowedUserView,
    CurrentUserView,
    DashboardPageData,
    FlashMessage,
    LoginPageData,
    render_discordauth_panel,
    render_dashboard_page,
    render_login_page,
)
from .server_runtime import PanelServer
from .server_shared import (
    SESSION_COOKIE_NAME,
    SessionData,
    build_bot_module_cards,
    build_session_cookie,
    constant_time_equal,
    expire_session_cookie,
)


class PanelHandler(BaseHTTPRequestHandler):
    server: PanelServer

    def do_GET(self) -> None:
        path, query = self._request_parts()

        if path == "/healthz":
            self._send_text("ok\n")
            return

        if path == "/auth/discord/login":
            self._handle_discord_login()
            return

        if path == "/auth/discord/callback":
            self._handle_discord_callback(query)
            return

        session_id, session = self._get_session()
        if path == "/login":
            if session is not None:
                self._redirect("/")
                return
            self._render_login()
            return

        if path != "/":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if session is None:
            self._redirect("/login")
            return

        partial = query.get("partial", [""])[0].strip().lower()
        if partial == "discordauth":
            self._render_discordauth_partial(session, query)
            return

        self._render_dashboard(session_id, session, query)

    def do_POST(self) -> None:
        path, _ = self._request_parts()
        fields = self._parse_form()
        if path == "/login":
            self._handle_password_login(fields)
            return
        if path == "/logout":
            self._handle_logout()
            return
        if path == "/action":
            self._handle_action(fields)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args) -> None:
        return

    def _handle_password_login(self, fields: dict[str, list[str]]) -> None:
        if self.server.config.password is None:
            self._render_login(error="Password sign-in is disabled for this panel.")
            return

        password = fields.get("password", [""])[0]
        if not constant_time_equal(password, self.server.config.password):
            self._render_login(error="Invalid panel password.")
            return

        session_id, _ = self.server.sessions.create()
        self.send_response(HTTPStatus.SEE_OTHER)
        self._set_security_headers()
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", build_session_cookie(session_id, secure=self.server.config.secure_cookie))
        self.end_headers()

    def _handle_discord_login(self) -> None:
        config = self.server.config.discord_oauth
        if config is None:
            self._redirect("/login")
            return
        state = self.server.oauth_states.create()
        self._redirect(build_authorize_url(config, state))

    def _handle_discord_callback(self, query: dict[str, list[str]]) -> None:
        config = self.server.config.discord_oauth
        if config is None:
            self._redirect("/login")
            return

        oauth_error = query.get("error", [""])[0]
        if oauth_error:
            self._render_login(error="Discord sign-in was cancelled or failed.")
            return

        state = query.get("state", [""])[0]
        code = query.get("code", [""])[0]
        if not self.server.oauth_states.consume(state):
            self._render_login(error="The Discord sign-in session expired. Try again.")
            return
        if not code:
            self._render_login(error="Discord did not return an authorization code.")
            return

        try:
            access_token = exchange_code(config, code)
            identity = fetch_identity(access_token)
        except Exception as error:
            self._render_login(error=f"Discord sign-in failed: {error}")
            return

        if not self.server.allowed_users.is_allowed(identity.user_id):
            self._render_login(error="This Discord account does not have access to the panel.")
            return

        self.server.allowed_users.touch_user(
            identity.user_id,
            display_name=identity.display_name,
            username=identity.username,
            avatar_url=identity.avatar_url,
        )
        session_id, _ = self.server.sessions.create(
            user_id=identity.user_id,
            display_name=identity.display_name,
            username=identity.username,
            avatar_url=identity.avatar_url,
        )
        self.send_response(HTTPStatus.SEE_OTHER)
        self._set_security_headers()
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", build_session_cookie(session_id, secure=self.server.config.secure_cookie))
        self.end_headers()

    def _handle_logout(self) -> None:
        session_id, _ = self._get_session()
        self.server.sessions.delete(session_id)
        self.send_response(HTTPStatus.SEE_OTHER)
        self._set_security_headers()
        self.send_header("Location", "/login")
        self.send_header("Set-Cookie", expire_session_cookie(secure=self.server.config.secure_cookie))
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
            self._redirect(self._dashboard_location_from_fields(fields))
            return

        action = fields.get("action", [""])[0]
        if action == "allow_user":
            self._handle_allow_user_action(session_id, session, fields)
            return
        if action == "remove_allowed_user":
            self._handle_remove_user_action(session_id, session, fields)
            return
        if self._handle_discordauth_action(session_id, fields):
            return

        branch = fields.get("branch", [""])[0]
        level, title, output = self.server.perform_action(action, branch=branch)
        self.server.sessions.set_flash(session_id, level=level, title=title, output=output)
        self._redirect("/")

    def _dashboard_location_from_fields(self, fields: dict[str, list[str]]) -> str:
        return build_dashboard_location(
            tab=fields.get("tab", ["server"])[0],
            player_uuid=fields.get("player_uuid", [""])[0].strip(),
            search=fields.get("discordauth_search", [""])[0].strip(),
            filter_value=fields.get("discordauth_filter", ["all"])[0],
        )

    def _handle_discordauth_action(self, session_id: str, fields: dict[str, list[str]]) -> bool:
        action = fields.get("action", [""])[0]
        if action not in {
            "discordauth_set_access",
            "discordauth_ban_player",
            "discordauth_set_temp_ban",
            "discordauth_clear_temp_ban",
            "discordauth_unlink_player",
            "discordauth_cancel_session",
        }:
            return False

        redirect_location = self._dashboard_location_from_fields(fields)
        try:
            from modules.discordauth.service import DiscordAuthService
        except ImportError:
            self.server.sessions.set_flash(
                session_id,
                level="error",
                title="DiscordAuth недоступен",
                output="Модуль DiscordAuth не удалось загрузить на стороне панели.",
            )
            self._redirect(redirect_location)
            return True

        service = DiscordAuthService()
        player_uuid = fields.get("player_uuid", [""])[0].strip()

        try:
            if action == "discordauth_set_access":
                access_state = fields.get("access_state", [""])[0].strip().upper()
                if not player_uuid:
                    raise ValueError("Не выбран игрок для изменения допуска.")
                if access_state == "BLOCKED":
                    raise ValueError("Для перманентного бана используй отдельную форму с причиной.")
                record = service.lift_player_ban(player_uuid, access_state=access_state)
                if record is None:
                    raise ValueError("Игрок не найден в DiscordAuth.")
                titles = {
                    "AUTO": "Включён авто-допуск",
                    "ALLOWED": "Доступ разрешён",
                    "BLOCKED": "Доступ запрещён",
                }
                outputs = {
                    "AUTO": f"Игрок {record.player_name} снова проверяется по Discord-роли.",
                    "ALLOWED": f"Игрок {record.player_name} вручную допущен к серверу.",
                    "BLOCKED": f"Игроку {record.player_name} вручную запрещён вход.",
                }
                title = titles.get(access_state, "Режим допуска обновлён")
                output = outputs.get(access_state, f"Режим доступа игрока {record.player_name} обновлён.")
            elif action == "discordauth_ban_player":
                if not player_uuid:
                    raise ValueError("Не выбран игрок для выдачи перманентного бана.")
                reason = fields.get("reason", [""])[0].strip()
                record = service.ban_player(player_uuid, reason=reason)
                if record is None:
                    raise ValueError("Игрок не найден в DiscordAuth.")
                title = "Перманентный бан выдан"
                output = f"Игроку {record.player_name} запрещен вход на сервер."
            elif action == "discordauth_set_temp_ban":
                if not player_uuid:
                    raise ValueError("Не выбран игрок для выдачи бана.")
                minutes_raw = fields.get("minutes", ["0"])[0].strip()
                minutes = int(minutes_raw or "0")
                reason = fields.get("reason", [""])[0].strip()
                record = service.apply_temp_ban(player_uuid, minutes=minutes, reason=reason)
                if record is None:
                    raise ValueError("Игрок не найден в DiscordAuth.")
                title = "Временный бан выдан"
                output = (
                    f"Игрок {record.player_name} заблокирован до {_format_unix_timestamp(record.temp_ban_until)}."
                )
            elif action == "discordauth_clear_temp_ban":
                if not player_uuid:
                    raise ValueError("Не выбран игрок для снятия бана.")
                record = service.remove_temp_ban(player_uuid)
                if record is None:
                    raise ValueError("Игрок не найден в DiscordAuth.")
                title = "Бан снят"
                output = f"Временный бан игрока {record.player_name} очищен."
            elif action == "discordauth_unlink_player":
                if not player_uuid:
                    raise ValueError("Не выбран игрок для сброса привязки.")
                record = service.unlink_player(player_uuid)
                if record is None:
                    raise ValueError("Игрок не найден в DiscordAuth.")
                title = "Привязка сброшена"
                output = f"Discord-привязка игрока {record.player_name} удалена."
            else:
                session_value = fields.get("session_id", [""])[0].strip()
                if not session_value:
                    raise ValueError("Не найдена активная сессия для сброса.")
                record = service.cancel_login_session(session_value)
                if record is None:
                    raise ValueError("Активная сессия входа не найдена.")
                title = "Запрос на вход сброшен"
                output = f"Сессия игрока {record.player_name} переведена в состояние {record.status.lower()}."
        except ValueError as error:
            self.server.sessions.set_flash(session_id, level="error", title="Ошибка DiscordAuth", output=str(error))
            self._redirect(redirect_location)
            return True
        except Exception as error:
            self.server.sessions.set_flash(
                session_id,
                level="error",
                title="Сбой DiscordAuth",
                output=str(error),
            )
            self._redirect(redirect_location)
            return True

        self.server.sessions.set_flash(session_id, level="success", title=title, output=output)
        self._redirect(redirect_location)
        return True

    def _handle_allow_user_action(self, session_id: str, session: SessionData, fields: dict[str, list[str]]) -> None:
        if self.server.config.discord_oauth is None or session.user_id is None:
            self.server.sessions.set_flash(
                session_id,
                level="error",
                title="Discord required",
                output="Sign in with Discord to manage panel access.",
            )
            self._redirect("/")
            return

        target_user_id = fields.get("discord_user_id", [""])[0].strip()
        try:
            self.server.allowed_users.add_user(target_user_id, added_by=session.user_id)
        except ValueError as error:
            self.server.sessions.set_flash(session_id, level="error", title="Invalid user ID", output=str(error))
            self._redirect("/")
            return

        self.server.sessions.set_flash(
            session_id,
            level="success",
            title="Access granted",
            output=f"Discord user {target_user_id} can now sign in to the panel.",
        )
        self._redirect("/")

    def _handle_remove_user_action(self, session_id: str, session: SessionData, fields: dict[str, list[str]]) -> None:
        if self.server.config.discord_oauth is None or session.user_id is None:
            self.server.sessions.set_flash(
                session_id,
                level="error",
                title="Discord required",
                output="Sign in with Discord to manage panel access.",
            )
            self._redirect("/")
            return

        target_user_id = fields.get("target_user_id", [""])[0].strip()
        try:
            removed = self.server.allowed_users.remove_user(target_user_id)
        except ValueError as error:
            self.server.sessions.set_flash(session_id, level="error", title="Access protected", output=str(error))
            self._redirect("/")
            return

        if removed:
            self.server.sessions.set_flash(
                session_id,
                level="success",
                title="Access removed",
                output=f"Discord user {target_user_id} no longer has panel access.",
            )
        else:
            self.server.sessions.set_flash(
                session_id,
                level="error",
                title="User not found",
                output=f"Discord user {target_user_id} is not in the access list.",
            )
        self._redirect("/")

    def _render_login(self, *, error: str | None = None) -> None:
        self._send_html(
            render_login_page(
                LoginPageData(
                    title="Warlords Bot Panel",
                    error=error,
                    discord_login_url="/auth/discord/login" if self.server.config.discord_oauth is not None else None,
                    password_enabled=self.server.config.password is not None,
                )
            )
        )

    def _build_dashboard_page_data(
        self,
        *,
        session_id: str | None,
        session: SessionData,
        query: dict[str, list[str]],
        consume_flash: bool,
        include_server_sections: bool,
    ) -> DashboardPageData:
        flash = self.server.sessions.pop_flash(session_id) if consume_flash and session_id is not None else None
        flash_message = None
        if flash is not None:
            flash_message = FlashMessage(level=flash[0], title=flash[1], output=flash[2])

        current_user = None
        if session.user_id is not None:
            current_user = CurrentUserView(
                user_id=session.user_id,
                display_name=session.display_name or session.username or session.user_id,
                username=session.username,
                avatar_url=session.avatar_url,
            )

        allowed_users: tuple[AllowedUserView, ...] = ()
        if include_server_sections:
            allowed_users = tuple(
                AllowedUserView(
                    user_id=record.user_id,
                    display_name=record.display_name,
                    username=record.username,
                    avatar_url=record.avatar_url,
                    removable=not self.server.allowed_users.is_protected(record.user_id),
                )
                for record in self.server.allowed_users.list_users()
            )
        service_data: dict[str, str] = {}
        git_data = GitSnapshot(
            remote_name="",
            remote_url="",
            current_branch="",
            commit="",
            subject="",
            upstream="",
            ahead=0,
            behind=0,
            worktree_status="",
            branches=(),
        )
        tracking_status = ""
        logs = ""
        if include_server_sections:
            service_data = self.server.service_snapshot()
            git_data = self.server.git_snapshot()
            tracking_status = format_tracking_status(git_data.ahead, git_data.behind)
            logs = self.server.logs_snapshot()
        requested_tab = query.get("tab", ["server"])[0]
        active_tab = "panel" if requested_tab in {"panel", "bot"} else "server"
        discordauth_search = query.get("discordauth_search", [""])[0].strip()
        discordauth_filter = _normalize_discordauth_filter(query.get("discordauth_filter", ["all"])[0])
        selected_player_uuid = query.get("player_uuid", [""])[0].strip() or None
        (
            discordauth_summary,
            discordauth_metrics,
            discordauth_players,
            discordauth_selected_player,
            discordauth_recent_restrictions,
            discordauth_selected_restrictions,
        ) = build_discordauth_dashboard(
            search=discordauth_search,
            filter_value=discordauth_filter,
            selected_player_uuid=selected_player_uuid,
        )
        return DashboardPageData(
            csrf_token=session.csrf_token,
            service_name=self.server.config.service_name,
            service_data=service_data,
            git_data=git_data,
            tracking_status=tracking_status,
            logs=logs,
            flash=flash_message,
            current_user=current_user,
            allowed_users=allowed_users,
            discord_auth_enabled=self.server.config.discord_oauth is not None,
            bot_modules=build_bot_module_cards(),
            active_tab=active_tab,
            discordauth_summary=discordauth_summary,
            discordauth_metrics=discordauth_metrics,
            discordauth_players=discordauth_players,
            discordauth_selected_player=discordauth_selected_player,
            discordauth_recent_restrictions=discordauth_recent_restrictions,
            discordauth_selected_restrictions=discordauth_selected_restrictions,
            discordauth_search=discordauth_search,
            discordauth_filter=discordauth_filter,
        )

    def _render_dashboard(self, session_id: str, session: SessionData, query: dict[str, list[str]]) -> None:
        page = self._build_dashboard_page_data(
            session_id=session_id,
            session=session,
            query=query,
            consume_flash=True,
            include_server_sections=True,
        )
        self._send_html(render_dashboard_page(page))

    def _render_discordauth_partial(self, session: SessionData, query: dict[str, list[str]]) -> None:
        page = self._build_dashboard_page_data(
            session_id=None,
            session=session,
            query=query,
            consume_flash=False,
            include_server_sections=False,
        )
        self._send_html(render_discordauth_panel(page))

    def _request_parts(self) -> tuple[str, dict[str, list[str]]]:
        parsed = urlsplit(self.path)
        return parsed.path, parse_qs(parsed.query, keep_blank_values=True)

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
            "default-src 'self'; img-src 'self' https://cdn.discordapp.com data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
