from __future__ import annotations

import asyncio
import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import discord

from .bridge_shared import (
    BridgeRequestError,
    DiscordAuthBridgeConfig,
    build_login_request_content,
    load_bridge_config,
    parse_bridge_json_body,
)
from .bridge_views import ManagedLoginApprovalView
from .config import DiscordAuthPresenceRecord
from .service import DiscordAuthService


logger = logging.getLogger(__name__)


class DiscordAuthBridgeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class,
        *,
        config: DiscordAuthBridgeConfig,
        service: DiscordAuthService,
        bot: discord.Client,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self.config = config
        self.service = service
        self.bot = bot
        self.loop = loop

    def run_async(self, coro, *, timeout: int = 15):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout=timeout)

    async def verify_role(self, discord_user_id: int) -> dict[str, object]:
        settings = self.service.get_primary_guild_settings()
        if settings is None:
            return {"configured": False, "hasRole": False}

        guild = self.bot.get_guild(settings.guild_id)
        if guild is None:
            guild = await self.bot.fetch_guild(settings.guild_id)

        member = guild.get_member(discord_user_id)
        if member is None:
            try:
                member = await guild.fetch_member(discord_user_id)
            except discord.HTTPException:
                member = None

        has_role = member is not None and any(role.id == settings.verify_role_id for role in member.roles)
        return {
            "configured": True,
            "guildId": settings.guild_id,
            "verifyRoleId": settings.verify_role_id,
            "hasRole": has_role,
        }

    async def dispatch_login_request(self, session_id: str) -> dict[str, object]:
        session = self.service.get_login_session(session_id)
        if session is None:
            return {"sent": False, "reason": "missing"}

        try:
            user = self.bot.get_user(session.discord_user_id) or await self.bot.fetch_user(session.discord_user_id)
            channel = await user.create_dm()
            view = ManagedLoginApprovalView(self.service, session_id)
            content = build_login_request_content(session.player_name, session.ip_address)
            message = await channel.send(content, view=view)
            self.service.set_login_message_id(session_id, message.id)
            return {"sent": True, "messageId": message.id}
        except discord.HTTPException as error:
            logger.warning("Не удалось отправить DiscordAuth DM для сессии %s: %s", session_id, error)
            self.service.resolve_login_session(session_id, "DM_FAILED")
            return {"sent": False, "reason": "dm_failed"}


class DiscordAuthBridgeHandler(BaseHTTPRequestHandler):
    server: DiscordAuthBridgeServer

    def do_GET(self) -> None:
        self._dispatch_request(self._do_get)

    def do_POST(self) -> None:
        self._dispatch_request(self._do_post)

    def _dispatch_request(self, handler) -> None:
        try:
            handler()
        except BridgeRequestError as error:
            self._send_json({"message": error.message}, status=error.status)
        except BrokenPipeError:
            logger.debug("DiscordAuth bridge client disconnected during %s %s.", self.command, self.path)
        except ConnectionError:
            logger.debug("DiscordAuth bridge connection error during %s %s.", self.command, self.path)
        except Exception:
            client_host = self.client_address[0] if self.client_address else "-"
            logger.exception(
                "DiscordAuth bridge failed for %s %s from %s.",
                self.command,
                self.path,
                client_host,
            )
            self._send_json({"message": "Internal server error."}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _do_get(self) -> None:
        path, query = self._request_parts()
        if path == "/healthz":
            self._send_json({"status": "ok"})
            return
        if not self._authorized():
            return
        if path == "/api/discordauth/settings/primary":
            self._handle_primary_settings()
            return
        if path == "/api/discordauth/verify-role":
            self._handle_verify_role(query)
            return
        if path.startswith("/api/discordauth/players/"):
            self._handle_get_player(path)
            return
        if path.startswith("/api/discordauth/login-sessions/"):
            self._handle_get_session(path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _do_post(self) -> None:
        path, _ = self._request_parts()
        if not self._authorized():
            return
        if path == "/api/discordauth/link-codes/register":
            self._handle_register_link_code()
            return
        if path == "/api/discordauth/login-sessions/start":
            self._handle_start_session()
            return
        if path == "/api/discordauth/presence/snapshot":
            self._handle_presence_snapshot()
            return
        if path.startswith("/api/discordauth/login-sessions/") and path.endswith("/cancel"):
            self._handle_cancel_session(path)
            return
        if path.startswith("/api/discordauth/players/") and path.endswith("/session-refresh"):
            self._handle_session_refresh(path)
            return
        if path.startswith("/api/discordauth/players/") and path.endswith("/unlink"):
            self._handle_unlink(path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args) -> None:
        return

    def _handle_primary_settings(self) -> None:
        settings = self.server.service.get_primary_guild_settings()
        if settings is None:
            self._send_json({"configured": False})
            return
        self._send_json(
            {
                "configured": True,
                "guildId": settings.guild_id,
                "verifyRoleId": settings.verify_role_id,
                "startMessageChannel": settings.start_message_channel_id,
                "adminCommandChannelId": settings.admin_command_channel_id,
                "adminCommandRoleId": settings.admin_command_role_id,
            }
        )

    def _handle_verify_role(self, query: dict[str, list[str]]) -> None:
        raw_user_id = query.get("discord_user_id", [""])[0].strip()
        if not raw_user_id.isdigit():
            self._send_json({"message": "discord_user_id is required."}, status=HTTPStatus.BAD_REQUEST)
            return
        result = self.server.run_async(self.server.verify_role(int(raw_user_id)))
        self._send_json(result)

    def _handle_get_player(self, path: str) -> None:
        player_uuid = path.removeprefix("/api/discordauth/players/").split("/", 1)[0]
        player = self.server.service.get_player(player_uuid)
        if player is None:
            self._send_json({"linked": False, "playerUuid": player_uuid}, status=HTTPStatus.NOT_FOUND)
            return
        self._send_json(
            {
                "playerUuid": player.player_uuid,
                "playerName": player.player_name,
                "discordUserId": player.discord_user_id,
                "discordUsername": player.discord_username,
                "discordDisplayName": player.discord_display_name,
                "linked": player.linked,
                "accessState": player.access_state,
                "adminStatus": player.admin_status,
                "tempBanUntil": player.temp_ban_until,
                "tempBanReason": player.temp_ban_reason,
                "adminNote": player.admin_note,
                "lastIp": player.last_ip,
                "lastAuthenticatedAt": player.last_authenticated_at,
                "isOnline": player.is_online,
                "onlineSince": player.online_since,
                "lastSeenAt": player.last_seen_at,
            }
        )

    def _handle_get_session(self, path: str) -> None:
        session_id = path.removeprefix("/api/discordauth/login-sessions/").split("/", 1)[0]
        session = self.server.service.get_login_session(session_id)
        if session is None:
            self._send_json({"message": "Session not found."}, status=HTTPStatus.NOT_FOUND)
            return
        self._send_json(
            {
                "sessionId": session.session_id,
                "playerUuid": session.player_uuid,
                "playerName": session.player_name,
                "discordUserId": session.discord_user_id,
                "status": session.status,
                "createdAt": session.created_at,
                "expiresAt": session.expires_at,
                "messageId": session.message_id,
            }
        )

    def _handle_register_link_code(self) -> None:
        body = self._read_json()
        try:
            record = self.server.service.register_link_code(
                code=str(body.get("code", "")),
                player_uuid=str(body.get("player_uuid", "")),
                player_name=str(body.get("player_name", "")),
            )
        except ValueError as error:
            self._send_json({"message": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json(
            {
                "message": "Код привязки зарегистрирован.",
                "code": record.code,
                "playerUuid": record.player_uuid,
                "expiresAt": record.expires_at,
            }
        )

    def _handle_start_session(self) -> None:
        body = self._read_json()
        try:
            session = self.server.service.create_login_session(
                player_uuid=str(body.get("player_uuid", "")),
                player_name=str(body.get("player_name", "")),
                address=str(body.get("address", "")),
                ip_address=str(body.get("ip_address", "")),
            )
        except ValueError as error:
            self._send_json({"message": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return
        dispatch_result = self.server.run_async(self.server.dispatch_login_request(session.session_id))
        current = self.server.service.get_login_session(session.session_id)
        self._send_json(
            {
                "message": "Сессия входа создана.",
                "sessionId": session.session_id,
                "status": current.status if current is not None else session.status,
                "dispatch": dispatch_result,
            }
        )

    def _handle_cancel_session(self, path: str) -> None:
        session_id = path.removeprefix("/api/discordauth/login-sessions/").removesuffix("/cancel")
        session = self.server.service.cancel_login_session(session_id)
        if session is None:
            self._send_json({"message": "Session not found."}, status=HTTPStatus.NOT_FOUND)
            return
        self._send_json({"message": "Сессия отменена.", "status": session.status})

    def _handle_session_refresh(self, path: str) -> None:
        player_uuid = path.removeprefix("/api/discordauth/players/").removesuffix("/session-refresh").rstrip("/")
        body = self._read_json()
        record = self.server.service.touch_player_auth(
            player_uuid=player_uuid,
            player_name=str(body.get("player_name", "")),
            ip_address=str(body.get("ip_address", "")),
        )
        self._send_json(
            {
                "message": "Сессия игрока обновлена.",
                "playerUuid": record.player_uuid,
                "lastAuthenticatedAt": record.last_authenticated_at,
            }
        )

    def _handle_presence_snapshot(self) -> None:
        body = self._read_json()
        raw_players = body.get("players", [])
        if not isinstance(raw_players, list):
            self._send_json({"message": "players must be an array."}, status=HTTPStatus.BAD_REQUEST)
            return

        players: list[DiscordAuthPresenceRecord] = []
        for item in raw_players:
            if not isinstance(item, dict):
                continue
            players.append(
                DiscordAuthPresenceRecord(
                    player_uuid=str(item.get("player_uuid", "")),
                    player_name=str(item.get("player_name", "")),
                    ip_address=str(item.get("ip_address", "")),
                )
            )

        online_count = self.server.service.sync_online_players(players)
        self._send_json(
            {
                "message": "Presence snapshot updated.",
                "onlinePlayers": online_count,
            }
        )

    def _handle_unlink(self, path: str) -> None:
        player_uuid = path.removeprefix("/api/discordauth/players/").removesuffix("/unlink").rstrip("/")
        record = self.server.service.unlink_player(player_uuid)
        if record is None:
            self._send_json({"message": "Игрок не найден."}, status=HTTPStatus.NOT_FOUND)
            return
        self._send_json({"message": "Привязка очищена.", "playerUuid": record.player_uuid})

    def _authorized(self) -> bool:
        if self.headers.get("X-Bridge-Token", "") == self.server.config.token:
            return True
        self._send_json({"message": "Unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
        return False

    def _request_parts(self) -> tuple[str, dict[str, list[str]]]:
        parsed = urlsplit(self.path)
        return parsed.path, parse_qs(parsed.query, keep_blank_values=True)

    def _read_json(self) -> dict[str, object]:
        raw_content_length = self.headers.get("Content-Length", "0").strip()
        try:
            content_length = int(raw_content_length or "0")
        except ValueError as error:
            raise BridgeRequestError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length header.") from error

        if content_length < 0:
            raise BridgeRequestError(HTTPStatus.BAD_REQUEST, "Content-Length must not be negative.")

        raw_body = self.rfile.read(content_length).decode("utf-8", "replace")
        return parse_bridge_json_body(raw_body)

    def _send_json(self, payload: dict[str, object], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class BridgeRuntime:
    def __init__(self, service: DiscordAuthService) -> None:
        self.service = service
        self._thread: threading.Thread | None = None
        self._server: DiscordAuthBridgeServer | None = None

    def start(self, *, bot: discord.Client) -> None:
        if self._server is not None:
            return
        config = load_bridge_config()
        if config is None:
            logger.info("DiscordAuth bridge disabled: DISCORDAUTH_BRIDGE_TOKEN is not configured.")
            return
        loop = asyncio.get_running_loop()
        server = DiscordAuthBridgeServer(
            (config.host, config.port),
            DiscordAuthBridgeHandler,
            config=config,
            service=self.service,
            bot=bot,
            loop=loop,
        )
        thread = threading.Thread(target=server.serve_forever, name="discordauth-bridge", daemon=True)
        thread.start()
        self._server = server
        self._thread = thread
        logger.info("DiscordAuth bridge listening on http://%s:%s", config.host, config.port)

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None
