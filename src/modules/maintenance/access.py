from __future__ import annotations

import os


def parse_allowed_user_ids(raw_value: str | None) -> frozenset[int]:
    if not raw_value:
        return frozenset()

    user_ids: set[int] = set()
    for raw_id in raw_value.split(","):
        value = raw_id.strip()
        if not value:
            continue
        try:
            user_id = int(value)
        except ValueError as error:
            raise RuntimeError(
                "BOT_UPDATE_ALLOWED_USER_IDS must contain comma-separated Discord user IDs."
            ) from error
        if user_id <= 0:
            raise RuntimeError("Discord user IDs in BOT_UPDATE_ALLOWED_USER_IDS must be positive.")
        user_ids.add(user_id)
    return frozenset(user_ids)


def load_allowed_user_ids() -> frozenset[int]:
    return parse_allowed_user_ids(os.getenv("BOT_UPDATE_ALLOWED_USER_IDS"))
