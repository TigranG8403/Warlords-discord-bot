from __future__ import annotations

import json
import os
from dataclasses import dataclass
from http import HTTPStatus

import discord

from core.discord_interactions import safe_followup_send, safe_response_edit_message


class BridgeRequestError(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def parse_bridge_json_body(raw_body: str) -> dict[str, object]:
    payload = raw_body.strip()
    if not payload:
        return {}

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as error:
        raise BridgeRequestError(HTTPStatus.BAD_REQUEST, f"Invalid JSON body: {error.msg}.") from error

    if not isinstance(parsed, dict):
        raise BridgeRequestError(HTTPStatus.BAD_REQUEST, "JSON body must be an object.")
    return parsed


def build_login_request_content(player_name: str, ip_address: str) -> str:
    return (
        f"Игрок **{player_name}** пытается войти на сервер.\n"
        f"IP: `{ip_address or '-'}`\n\n"
        "Подтвердить вход?"
    )


def describe_inactive_login_request(status: str | None) -> str:
    normalized = (status or "").strip().upper()
    if normalized == "APPROVED":
        return "Вход уже подтверждён."
    if normalized == "DENIED":
        return "Вход уже отклонён."
    if normalized == "CANCELLED":
        return "Запрос уже недействителен: игрок вышел с сервера."
    if normalized == "TIMEOUT":
        return "Запрос уже истёк."
    if normalized == "DM_FAILED":
        return "Запрос завершён: сообщение в Discord не было доставлено."
    return "Запрос уже завершён или истёк."


async def finalize_login_interaction(
    interaction: discord.Interaction,
    *,
    content: str,
    interaction_active: bool,
) -> None:
    if interaction_active:
        try:
            if interaction.message is not None:
                await interaction.message.edit(content=content, view=None)
                return
        except discord.HTTPException:
            pass

        try:
            await interaction.edit_original_response(content=content, view=None)
            return
        except discord.HTTPException:
            pass
    else:
        if await safe_response_edit_message(interaction, content=content, view=None):
            return

    await safe_followup_send(interaction, content, ephemeral=True)


@dataclass(slots=True, frozen=True)
class DiscordAuthBridgeConfig:
    host: str
    port: int
    token: str


def load_bridge_config() -> DiscordAuthBridgeConfig | None:
    token = os.getenv("DISCORDAUTH_BRIDGE_TOKEN", "").strip()
    if not token:
        return None
    host = os.getenv("DISCORDAUTH_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("DISCORDAUTH_BRIDGE_PORT", "8790"))
    return DiscordAuthBridgeConfig(host=host, port=port, token=token)
