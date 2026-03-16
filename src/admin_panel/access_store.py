from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AllowedUserRecord:
    user_id: str
    display_name: str = ""
    username: str = ""
    avatar_url: str | None = None
    added_by: str = ""


class AllowedUserStore:
    def __init__(self, path: Path, *, protected_ids: set[str] | None = None) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._protected_ids = set(protected_ids or set())
        self._lock = threading.Lock()
        self._ensure_file()
        if self._protected_ids:
            self.ensure_ids(self._protected_ids)

    def list_users(self) -> tuple[AllowedUserRecord, ...]:
        with self._lock:
            data = self._read_locked()
        return tuple(sorted(data.values(), key=lambda item: (item.display_name or item.username or item.user_id).lower()))

    def is_allowed(self, user_id: str) -> bool:
        with self._lock:
            return user_id in self._read_locked()

    def is_protected(self, user_id: str) -> bool:
        return user_id in self._protected_ids

    def ensure_ids(self, user_ids: set[str]) -> None:
        normalized = {value.strip() for value in user_ids if value.strip()}
        if not normalized:
            return
        with self._lock:
            data = self._read_locked()
            changed = False
            for user_id in normalized:
                if user_id not in data:
                    data[user_id] = AllowedUserRecord(user_id=user_id)
                    changed = True
            if changed:
                self._write_locked(data)

    def add_user(self, user_id: str, *, added_by: str, display_name: str = "", username: str = "", avatar_url: str | None = None) -> AllowedUserRecord:
        normalized = user_id.strip()
        if not normalized.isdigit():
            raise ValueError("Discord user ID must contain only digits.")
        with self._lock:
            data = self._read_locked()
            existing = data.get(normalized)
            record = AllowedUserRecord(
                user_id=normalized,
                display_name=display_name or (existing.display_name if existing else ""),
                username=username or (existing.username if existing else ""),
                avatar_url=avatar_url if avatar_url is not None else (existing.avatar_url if existing else None),
                added_by=added_by or (existing.added_by if existing else ""),
            )
            data[normalized] = record
            self._write_locked(data)
            return record

    def touch_user(self, user_id: str, *, display_name: str, username: str, avatar_url: str | None) -> None:
        normalized = user_id.strip()
        with self._lock:
            data = self._read_locked()
            existing = data.get(normalized)
            if existing is None:
                return
            data[normalized] = AllowedUserRecord(
                user_id=normalized,
                display_name=display_name or existing.display_name,
                username=username or existing.username,
                avatar_url=avatar_url,
                added_by=existing.added_by,
            )
            self._write_locked(data)

    def remove_user(self, user_id: str) -> bool:
        normalized = user_id.strip()
        if normalized in self._protected_ids:
            raise ValueError("This user has protected access and cannot be removed from the panel.")
        with self._lock:
            data = self._read_locked()
            removed = data.pop(normalized, None)
            if removed is not None:
                self._write_locked(data)
            return removed is not None

    def _ensure_file(self) -> None:
        if self._path.exists():
            return
        self._path.write_text("{\"users\": []}\n", encoding="utf-8")

    def _read_locked(self) -> dict[str, AllowedUserRecord]:
        raw = self._path.read_text(encoding="utf-8")
        payload = json.loads(raw)
        users = payload.get("users", [])
        data: dict[str, AllowedUserRecord] = {}
        if not isinstance(users, list):
            return data
        for item in users:
            if not isinstance(item, dict):
                continue
            user_id = item.get("user_id")
            if not isinstance(user_id, str) or not user_id.strip():
                continue
            data[user_id] = AllowedUserRecord(
                user_id=user_id,
                display_name=item.get("display_name", "") if isinstance(item.get("display_name"), str) else "",
                username=item.get("username", "") if isinstance(item.get("username"), str) else "",
                avatar_url=item.get("avatar_url") if isinstance(item.get("avatar_url"), str) else None,
                added_by=item.get("added_by", "") if isinstance(item.get("added_by"), str) else "",
            )
        return data

    def _write_locked(self, data: dict[str, AllowedUserRecord]) -> None:
        payload = {
            "users": [
                {
                    "user_id": record.user_id,
                    "display_name": record.display_name,
                    "username": record.username,
                    "avatar_url": record.avatar_url,
                    "added_by": record.added_by,
                }
                for record in sorted(data.values(), key=lambda item: item.user_id)
            ]
        }
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
