from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Iterable

from discord.ext import commands


@dataclass(slots=True)
class BotModule:
    name: str
    register: Callable[[commands.Bot], None]
    on_ready: Callable[[commands.Bot], Awaitable[None]] | None = None
    persistent_views: Callable[[], Iterable] | None = None
    description: str = field(default="")
