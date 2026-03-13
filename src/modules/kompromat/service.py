from __future__ import annotations

import re
from dataclasses import dataclass
import discord

from modules.tickets.config import convert_to_msk, get_utc_time

from .repository import KompromatEntry, KompromatRepository

MENTION_RE = re.compile(r"<@!?(\d+)>")


@dataclass(frozen=True, slots=True)
class KompromatCategory:
    key: str
    label: str
    emoji: str
    color: int
    description: str


CATEGORIES = (
    KompromatCategory(
        key="rule_violation",
        label="Нарушение правил",
        emoji="⛔",
        color=0x6D1A1A,
        description="Любые нарушения правил сервера, обход ограничений и спорные действия.",
    ),
    KompromatCategory(
        key="toxicity",
        label="Оскорбления / токсичность",
        emoji="🤬",
        color=0x8A2323,
        description="Оскорбления, травля, провокации, токсичное поведение и агрессия.",
    ),
    KompromatCategory(
        key="spam",
        label="Спам / флуд",
        emoji="📨",
        color=0x8A5A23,
        description="Повторяющиеся сообщения, флуд, мусорные упоминания, реклама и засорение чатов.",
    ),
    KompromatCategory(
        key="scam",
        label="Скам",
        emoji="🎣",
        color=0x5C2751,
        description="Попытки обмана, фишинг, подозрительные ссылки, выманивание данных и схемы.",
    ),
    KompromatCategory(
        key="other",
        label="Другое",
        emoji="🗃️",
        color=0x4A5568,
        description="Все, что не подходит под основные категории, но стоит зафиксировать.",
    ),
)

CATEGORY_MAP = {category.key: category for category in CATEGORIES}


class KompromatService:
    def __init__(self, repository: KompromatRepository) -> None:
        self.repository = repository

    def categories(self) -> tuple[KompromatCategory, ...]:
        return CATEGORIES

    def category(self, key: str) -> KompromatCategory:
        return CATEGORY_MAP[key]

    async def create_entry(
        self,
        *,
        interaction: discord.Interaction,
        category_key: str,
        title: str,
        summary: str,
        tagged_user_ids: list[int],
    ) -> tuple[discord.Message, discord.Thread | None]:
        if interaction.guild is None:
            raise RuntimeError("Команда доступна только на сервере.")

        archive_channel_id = self.repository.get_archive_channel(interaction.guild.id)
        if archive_channel_id is None:
            raise RuntimeError("Архивный канал компроматов не настроен. Переопубликуйте панель и укажите archive channel.")

        channel = interaction.guild.get_channel(archive_channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise RuntimeError("Архивный канал компроматов не найден или не является текстовым.")

        category = self.category(category_key)
        tags_text = " ".join(f"<@{user_id}>" for user_id in tagged_user_ids) or None
        embed = self._build_entry_embed(
            category=category,
            title=title,
            summary=summary,
            author=interaction.user,
            tags_text=tags_text,
            tagged_user_ids=tagged_user_ids,
        )

        message = await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )

        thread = await self._create_evidence_thread(message, interaction.user)
        if thread is not None and message.embeds:
            updated_embed = discord.Embed.from_dict(message.embeds[0].to_dict())
            field_index = next(
                (index for index, field in enumerate(updated_embed.fields) if field.name == "Доказательства"),
                None,
            )
            if field_index is None:
                updated_embed.add_field(name="Доказательства", value=f"Ожидаются • <#{thread.id}>", inline=True)
            else:
                updated_embed.set_field_at(
                    field_index,
                    name="Доказательства",
                    value=f"Ожидаются • <#{thread.id}>",
                    inline=True,
                )
            await message.edit(embed=updated_embed)

        self.repository.create_entry(
            guild_id=interaction.guild.id,
            category_key=category.key,
            title=title,
            summary=summary,
            author_id=interaction.user.id,
            tags_text=tags_text,
            tagged_user_ids=tagged_user_ids,
            channel_id=message.channel.id,
            message_id=message.id,
            thread_id=thread.id if thread is not None else None,
            has_evidence=False,
            created_at=get_utc_time().isoformat(),
        )
        return message, thread

    def search_by_member(self, *, guild_id: int, member: discord.Member) -> list[KompromatEntry]:
        return self.repository.search_by_member(guild_id=guild_id, member_id=member.id)

    def build_search_embed(self, *, member: discord.Member, entries: list[KompromatEntry]) -> discord.Embed:
        if not entries:
            return discord.Embed(
                title=f"Компроматы по {member.display_name}",
                description="Записей с таким тегом пока не найдено.",
                color=0x6D1A1A,
            )

        lines: list[str] = []
        for entry in entries:
            category = self.category(entry.category_key)
            created_at = convert_to_msk(discord.utils.parse_time(entry.created_at)).strftime("%d.%m.%Y %H:%M")
            jump_url = f"https://discord.com/channels/{entry.guild_id}/{entry.channel_id}/{entry.message_id}"
            thread_part = f" • <#{entry.thread_id}>" if entry.thread_id else ""
            lines.append(
                f"{category.emoji} **{category.label}** - [{entry.title}]({jump_url})\n"
                f"`{created_at}`{thread_part}\n"
                f"{discord.utils.escape_markdown(self._shorten(entry.summary, 160))}"
            )

        return discord.Embed(
            title=f"Компроматы по {member.display_name}",
            description="\n\n".join(lines),
            color=0x6D1A1A,
        )

    async def _create_evidence_thread(
        self,
        message: discord.Message,
        author: discord.abc.User,
    ) -> discord.Thread | None:
        try:
            thread = await message.create_thread(
                name=f"Доказательства • {self._sanitize_thread_name(message.embeds[0].title or 'Компромат')}",
                auto_archive_duration=10080,
            )
        except (discord.Forbidden, discord.HTTPException):
            return None

        await thread.send(
            f"{author.mention}, сюда можно прикрепить скриншоты, файлы и другие доказательства.",
            allowed_mentions=discord.AllowedMentions(users=[author]),
        )
        return thread

    def _build_entry_embed(
        self,
        *,
        category: KompromatCategory,
        title: str,
        summary: str,
        author: discord.abc.User,
        tags_text: str | None,
        tagged_user_ids: list[int],
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"{category.emoji} {title}",
            description=summary,
            color=category.color,
            timestamp=get_utc_time(),
        )
        embed.add_field(name="Категория", value=category.label, inline=True)
        embed.add_field(name="Автор", value=author.mention, inline=True)
        embed.add_field(name="Доказательства", value="Ожидаются", inline=True)

        if tagged_user_ids:
            mentions = " ".join(f"<@{user_id}>" for user_id in tagged_user_ids)
            embed.add_field(name="Теги участников", value=mentions, inline=False)
        elif tags_text:
            embed.add_field(name="Теги участников", value=tags_text, inline=False)

        embed.set_footer(text="Доказательства можно найти в треде под этой записью")
        return embed

    def _extract_tagged_user_ids(self, tags_text: str | None) -> list[int]:
        if not tags_text:
            return []
        seen: set[int] = set()
        result: list[int] = []
        for raw_user_id in MENTION_RE.findall(tags_text):
            user_id = int(raw_user_id)
            if user_id in seen:
                continue
            seen.add(user_id)
            result.append(user_id)
        return result

    def _shorten(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    def _sanitize_thread_name(self, text: str) -> str:
        compact = " ".join(text.split())
        return compact[:70]
