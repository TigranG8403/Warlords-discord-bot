from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, Iterable, Protocol, TypeVar

import discord
from discord.ext import commands, tasks


class ChannelBoundRecord(Protocol):
    channel_id: int


RecordT = TypeVar("RecordT", bound=ChannelBoundRecord)


class PanelRepository(Protocol[RecordT]):
    def set(self, message_id: int, record: RecordT) -> None: ...

    def delete(self, message_id: int) -> None: ...

    def delete_many(self, message_ids: Iterable[int]) -> None: ...

    def delete_by_channel(self, channel_id: int) -> None: ...

    def items(self) -> list[tuple[int, RecordT]]: ...


@dataclass(slots=True)
class PanelRenderResult:
    embed: discord.Embed | None = None
    content: str | None = None
    view: discord.ui.View | None = None
    files: tuple[discord.File, ...] = ()
    allowed_mentions: discord.AllowedMentions | None = None

    def as_send_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.content is not None:
            kwargs["content"] = self.content
        if self.embed is not None:
            kwargs["embed"] = self.embed
        if self.view is not None:
            kwargs["view"] = self.view
        if self.allowed_mentions is not None:
            kwargs["allowed_mentions"] = self.allowed_mentions
        if len(self.files) == 1:
            kwargs["file"] = self.files[0]
        elif self.files:
            kwargs["files"] = list(self.files)
        return kwargs

    def as_edit_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.content is not None:
            kwargs["content"] = self.content
        if self.embed is not None:
            kwargs["embed"] = self.embed
        if self.view is not None:
            kwargs["view"] = self.view
        if self.allowed_mentions is not None:
            kwargs["allowed_mentions"] = self.allowed_mentions
        kwargs["attachments"] = list(self.files)
        return kwargs


RenderResult = PanelRenderResult | None
PanelRenderer = Callable[[RecordT, discord.TextChannel], RenderResult | Awaitable[RenderResult]]


class PanelRuntime(Generic[RecordT]):
    def __init__(
        self,
        *,
        name: str,
        repository: PanelRepository[RecordT],
        render_panel: PanelRenderer[RecordT],
        period_getter: Callable[[], str],
        logger: logging.Logger | None = None,
    ) -> None:
        self.name = name
        self.repository = repository
        self.render_panel = render_panel
        self.period_getter = period_getter
        self.logger = logger or logging.getLogger(__name__)
        self.bot: commands.Bot | None = None
        self._last_period: str | None = None
        self._listeners_bound = False

    def bind(self, bot: commands.Bot) -> None:
        self.bot = bot
        if self._listeners_bound:
            return

        bot.add_listener(self._on_raw_message_delete, "on_raw_message_delete")
        bot.add_listener(self._on_raw_bulk_message_delete, "on_raw_bulk_message_delete")
        bot.add_listener(self._on_guild_channel_delete, "on_guild_channel_delete")
        self._listeners_bound = True

    async def publish(self, channel: discord.TextChannel, record: RecordT) -> discord.Message:
        render_result = await self._render(record, channel)
        if render_result is None:
            raise RuntimeError(f"Не удалось собрать панель {self.name}.")

        message = await channel.send(**render_result.as_send_kwargs())
        self.repository.set(message.id, record)
        return message

    async def resolve_channel(self, channel_id: int) -> discord.TextChannel | None:
        if self.bot is None:
            return None

        channel = self.bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel

        try:
            fetched_channel = await self.bot.fetch_channel(channel_id)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            return None

        if isinstance(fetched_channel, discord.TextChannel):
            return fetched_channel
        return None

    async def refresh_registered_message(self, message_id: int, record: RecordT) -> None:
        channel = await self.resolve_channel(record.channel_id)
        if channel is None:
            self.repository.delete(message_id)
            return

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            self.repository.delete(message_id)
            return
        except (discord.Forbidden, discord.HTTPException):
            return

        try:
            render_result = await self._render(record, channel)
        except Exception:
            self.logger.exception("Не удалось собрать %s-панель %s.", self.name, message_id)
            return

        if render_result is None:
            return

        try:
            await message.edit(**render_result.as_edit_kwargs())
        except discord.NotFound:
            self.repository.delete(message_id)
        except (discord.Forbidden, discord.HTTPException) as error:
            self.logger.warning("Не удалось обновить %s-панель %s: %s", self.name, message_id, error)

    async def refresh_registered_messages(self) -> None:
        for message_id, record in self.repository.items():
            await self.refresh_registered_message(message_id, record)

    async def on_ready(self, bot: commands.Bot) -> None:
        self.bind(bot)
        await self.refresh_registered_messages()
        self._last_period = self.period_getter()
        if not self.refresh_loop.is_running():
            self.refresh_loop.start()

    async def _on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        self.repository.delete(payload.message_id)

    async def _on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent) -> None:
        self.repository.delete_many(payload.message_ids)

    async def _on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        self.repository.delete_by_channel(channel.id)

    async def _render(self, record: RecordT, channel: discord.TextChannel) -> RenderResult:
        render_result = self.render_panel(record, channel)
        if inspect.isawaitable(render_result):
            return await render_result
        return render_result

    @tasks.loop(minutes=1)
    async def refresh_loop(self) -> None:
        current_period = self.period_getter()
        if current_period == self._last_period:
            return

        self._last_period = current_period
        await self.refresh_registered_messages()

    @refresh_loop.before_loop
    async def before_refresh_loop(self) -> None:
        if self.bot is not None:
            await self.bot.wait_until_ready()
