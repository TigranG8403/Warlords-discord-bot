from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "WarlordsBotPanel/1.0 (+https://botpanel.warlords.su)",
}


@dataclass(frozen=True)
class DiscordOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str = "identify"


@dataclass(frozen=True)
class DiscordIdentity:
    user_id: str
    username: str
    global_name: str
    avatar_url: str | None

    @property
    def display_name(self) -> str:
        return self.global_name or self.username


def build_authorize_url(config: DiscordOAuthConfig, state: str) -> str:
    return f"{DISCORD_AUTHORIZE_URL}?{urlencode({
        'client_id': config.client_id,
        'redirect_uri': config.redirect_uri,
        'response_type': 'code',
        'scope': config.scope,
        'state': state,
        'prompt': 'consent',
    })}"


def exchange_code(config: DiscordOAuthConfig, code: str) -> str:
    payload = urlencode(
        {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
        }
    ).encode("utf-8")
    request = Request(
        f"{DISCORD_API_BASE}/oauth2/token",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            **REQUEST_HEADERS,
        },
    )
    response_data = _request_json(request)
    access_token = response_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("Discord did not return an access token.")
    return access_token


def fetch_identity(access_token: str) -> DiscordIdentity:
    request = Request(
        f"{DISCORD_API_BASE}/users/@me",
        headers={
            "Authorization": f"Bearer {access_token}",
            **REQUEST_HEADERS,
        },
    )
    data = _request_json(request)
    user_id = _require_str(data, "id")
    username = _require_str(data, "username")
    global_name = data.get("global_name") if isinstance(data.get("global_name"), str) else ""
    avatar_hash = data.get("avatar") if isinstance(data.get("avatar"), str) else ""
    avatar_url = build_avatar_url(user_id, avatar_hash)
    return DiscordIdentity(
        user_id=user_id,
        username=username,
        global_name=global_name,
        avatar_url=avatar_url,
    )


def build_avatar_url(user_id: str, avatar_hash: str) -> str | None:
    if avatar_hash:
        extension = "gif" if avatar_hash.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{extension}?size=128"
    if not user_id.isdigit():
        return None
    default_index = (int(user_id) >> 22) % 6
    return f"https://cdn.discordapp.com/embed/avatars/{default_index}.png"


def _request_json(request: Request) -> dict[str, Any]:
    with urlopen(request, timeout=15) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected Discord API response.")
    return data


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Discord response is missing '{key}'.")
    return value
