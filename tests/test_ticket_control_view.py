from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from tests import support  # noqa: F401

from modules.tickets.views import inside


class DummyTextChannel:
    def __init__(self, channel_id: int) -> None:
        self.id = channel_id


class DummyMember:
    def __init__(self, member_id: int) -> None:
        self.id = member_id


class DummyRepository:
    def __init__(self, record) -> None:
        self.record = record

    def get_by_channel_id(self, channel_id: int):
        if self.record.channel_id == channel_id:
            return self.record
        return None


class DummyService:
    def __init__(self, record, guild_settings) -> None:
        self.repository = DummyRepository(record)
        self.guild_settings = guild_settings
        self.last_can_close_args = None
        self.requested_guild_id = None

    def get_guild_settings(self, guild_id: int):
        self.requested_guild_id = guild_id
        return self.guild_settings

    def _can_close_ticket(self, member, record, guild_settings) -> bool:
        self.last_can_close_args = (member, record, guild_settings)
        return True


class TicketControlViewTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_button_checks_permissions_with_guild_settings(self) -> None:
        record = SimpleNamespace(channel_id=777, creator_id=15)
        guild_settings = SimpleNamespace(support_role_id=42)
        service = DummyService(record, guild_settings)
        view = inside.TicketControlView(service)
        interaction = SimpleNamespace(
            channel=DummyTextChannel(777),
            user=DummyMember(15),
            guild=SimpleNamespace(id=123456),
        )

        with (
            patch.object(inside.discord, "TextChannel", DummyTextChannel),
            patch.object(inside.discord, "Member", DummyMember),
            patch.object(inside, "_safe_send_modal", AsyncMock(return_value=True)) as safe_send_modal,
        ):
            await view._open_close_modal(interaction)

        self.assertEqual(service.requested_guild_id, 123456)
        self.assertEqual(service.last_can_close_args, (interaction.user, record, guild_settings))
        safe_send_modal.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
