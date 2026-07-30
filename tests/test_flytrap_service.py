from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock

import discord

from tests import support  # noqa: F401

from modules.flytrap.models import FlytrapAction, FlytrapConfig
from modules.flytrap.repository import FlytrapRepository
from modules.flytrap.service import FlytrapService


def _member(*, guild: MagicMock, administrator: bool = False) -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.id = 30
    member.bot = False
    member.mention = "<@30>"
    member.guild = guild
    member.guild_permissions = SimpleNamespace(administrator=administrator)
    member.timeout = AsyncMock()
    return member


def _message(*, guild: MagicMock, member: MagicMock) -> MagicMock:
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 20

    message = MagicMock(spec=discord.Message)
    message.id = 40
    message.guild = guild
    message.channel = channel
    message.author = member
    message.content = "spam.example"
    message.attachments = []
    message.created_at = datetime.now(UTC)
    message.delete = AsyncMock()
    return message


class FlytrapServiceTests(unittest.TestCase):
    def test_softban_is_idempotent_and_logged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = FlytrapRepository(Path(temp_dir) / "flytrap.sqlite3")
            repository.set_config(
                FlytrapConfig(
                    guild_id=10,
                    channel_id=20,
                    log_channel_id=21,
                    action=FlytrapAction.SOFTBAN,
                    warning_message_id=1,
                )
            )
            service = FlytrapService(repository)

            guild = MagicMock(spec=discord.Guild)
            guild.id = 10
            guild.owner_id = 99
            guild.ban = AsyncMock()
            guild.unban = AsyncMock()
            log_channel = MagicMock(spec=discord.TextChannel)
            log_channel.send = AsyncMock()
            guild.get_channel.return_value = log_channel

            member = _member(guild=guild)
            message = _message(guild=guild, member=member)

            asyncio.run(service.handle_message(message))
            asyncio.run(service.handle_message(message))

            guild.ban.assert_awaited_once()
            guild.unban.assert_awaited_once()
            log_channel.send.assert_awaited_once()
            self.assertEqual(repository.get_incident_status(message.id), "handled")

    def test_administrator_is_not_punished(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = FlytrapRepository(Path(temp_dir) / "flytrap.sqlite3")
            repository.set_config(
                FlytrapConfig(
                    guild_id=10,
                    channel_id=20,
                    log_channel_id=21,
                    action=FlytrapAction.BAN,
                    warning_message_id=1,
                )
            )
            service = FlytrapService(repository)

            guild = MagicMock(spec=discord.Guild)
            guild.id = 10
            guild.owner_id = 99
            guild.ban = AsyncMock()
            log_channel = MagicMock(spec=discord.TextChannel)
            log_channel.send = AsyncMock()
            guild.get_channel.return_value = log_channel

            member = _member(guild=guild, administrator=True)
            message = _message(guild=guild, member=member)

            asyncio.run(service.handle_message(message))

            guild.ban.assert_not_awaited()
            message.delete.assert_awaited_once()
            self.assertEqual(repository.get_incident_status(message.id), "protected")

    def test_timeout_recovers_member_from_message_history(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = FlytrapRepository(Path(temp_dir) / "flytrap.sqlite3")
            repository.set_config(
                FlytrapConfig(
                    guild_id=10,
                    channel_id=20,
                    log_channel_id=21,
                    action=FlytrapAction.TIMEOUT,
                    warning_message_id=1,
                )
            )
            service = FlytrapService(repository)

            guild = MagicMock(spec=discord.Guild)
            guild.id = 10
            guild.owner_id = 99
            guild.get_member.return_value = None
            log_channel = MagicMock(spec=discord.TextChannel)
            log_channel.send = AsyncMock()
            guild.get_channel.return_value = log_channel

            member = _member(guild=guild)
            guild.fetch_member = AsyncMock(return_value=member)
            user = MagicMock(spec=discord.User)
            user.id = member.id
            user.bot = False
            user.mention = member.mention
            message = _message(guild=guild, member=user)

            asyncio.run(service.handle_message(message))

            guild.fetch_member.assert_awaited_once_with(user.id)
            member.timeout.assert_awaited_once()
            message.delete.assert_awaited_once()
            self.assertEqual(repository.get_incident_status(message.id), "handled")


if __name__ == "__main__":
    unittest.main()
