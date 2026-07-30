from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FlytrapAction(str, Enum):
    TIMEOUT = "timeout"
    SOFTBAN = "softban"
    BAN = "ban"

    @property
    def display_name(self) -> str:
        return {
            FlytrapAction.TIMEOUT: "тайм-аут на один час",
            FlytrapAction.SOFTBAN: "исключение с удалением недавних сообщений",
            FlytrapAction.BAN: "постоянный бан",
        }[self]


@dataclass(frozen=True, slots=True)
class FlytrapConfig:
    guild_id: int
    channel_id: int
    log_channel_id: int
    action: FlytrapAction
    warning_message_id: int
    moderated_count: int = 0
