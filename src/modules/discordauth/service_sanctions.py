from __future__ import annotations

from .config import DiscordAuthEventRecord, DiscordAuthPlayerRecord


class DiscordAuthSanctionsMixin:
    def set_access_state(self, player_uuid: str, access_state: str) -> DiscordAuthPlayerRecord | None:
        normalized = access_state.strip().upper()
        if normalized not in {"AUTO", "ALLOWED", "BLOCKED"}:
            raise ValueError("Недопустимое состояние доступа.")
        return self._update_player_fields(player_uuid, access_state=normalized)

    def set_admin_meta(self, player_uuid: str, *, admin_status: str, admin_note: str) -> DiscordAuthPlayerRecord | None:
        return self._update_player_fields(
            player_uuid,
            admin_status=admin_status.strip(),
            admin_note=admin_note.strip(),
        )

    def set_temp_ban(self, player_uuid: str, *, minutes: int, reason: str) -> DiscordAuthPlayerRecord | None:
        if minutes <= 0:
            raise ValueError("Длительность бана должна быть больше 0 минут.")
        expires_at = self._now() + (minutes * 60)
        return self._update_player_fields(
            player_uuid,
            temp_ban_until=expires_at,
            temp_ban_reason=reason.strip(),
        )

    def clear_temp_ban(self, player_uuid: str) -> DiscordAuthPlayerRecord | None:
        return self._update_player_fields(
            player_uuid,
            temp_ban_until=0,
            temp_ban_reason="",
        )

    def ban_player(self, player_uuid: str, *, reason: str) -> DiscordAuthPlayerRecord | None:
        normalized_reason = reason.strip()
        record = self._update_player_fields(
            player_uuid,
            access_state="BLOCKED",
            admin_note=normalized_reason,
        )
        if record is None:
            return None

        with self._connection() as connection:
            self._record_event_locked(
                connection,
                "ban",
                record.player_uuid,
                record.player_name,
                self._now(),
                reason=normalized_reason,
            )
        return record

    def lift_player_ban(self, player_uuid: str, *, access_state: str = "AUTO") -> DiscordAuthPlayerRecord | None:
        normalized = access_state.strip().upper()
        if normalized not in {"AUTO", "ALLOWED"}:
            raise ValueError("Недопустимый режим снятия бана.")

        record = self._update_player_fields(
            player_uuid,
            access_state=normalized,
            admin_note="",
        )
        if record is None:
            return None

        with self._connection() as connection:
            self._record_event_locked(
                connection,
                "unban",
                record.player_uuid,
                record.player_name,
                self._now(),
            )
        return record

    def apply_temp_ban(self, player_uuid: str, *, minutes: int, reason: str) -> DiscordAuthPlayerRecord | None:
        record = self.set_temp_ban(player_uuid, minutes=minutes, reason=reason)
        if record is None:
            return None

        with self._connection() as connection:
            self._record_event_locked(
                connection,
                "tempban",
                record.player_uuid,
                record.player_name,
                self._now(),
                reason=record.temp_ban_reason,
                expires_at=record.temp_ban_until,
            )
        return record

    def remove_temp_ban(self, player_uuid: str) -> DiscordAuthPlayerRecord | None:
        record = self.clear_temp_ban(player_uuid)
        if record is None:
            return None

        with self._connection() as connection:
            self._record_event_locked(
                connection,
                "tempunban",
                record.player_uuid,
                record.player_name,
                self._now(),
            )
        return record

    def list_recent_events(
        self,
        *,
        limit: int = 12,
        player_uuid: str | None = None,
        event_types: set[str] | None = None,
    ) -> list[DiscordAuthEventRecord]:
        normalized_limit = max(1, min(limit, 100))
        normalized_types = {item.strip().lower() for item in (event_types or set()) if item.strip()}

        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            query = """
                SELECT event_type, player_uuid, player_name, reason, expires_at, created_at
                FROM auth_events
            """
            clauses: list[str] = []
            params: list[object] = []

            if player_uuid is not None and player_uuid.strip():
                clauses.append("player_uuid = ?")
                params.append(player_uuid.strip())

            if normalized_types:
                placeholders = ", ".join("?" for _ in normalized_types)
                clauses.append(f"event_type IN ({placeholders})")
                params.extend(sorted(normalized_types))

            if clauses:
                query += " WHERE " + " AND ".join(clauses)

            query += " ORDER BY created_at DESC, event_id DESC LIMIT ?"
            params.append(normalized_limit)
            rows = connection.execute(query, tuple(params)).fetchall()

        return [
            DiscordAuthEventRecord(
                event_type=str(row["event_type"]),
                player_uuid=str(row["player_uuid"]),
                player_name=str(row["player_name"]),
                reason=str(row["reason"]),
                expires_at=int(row["expires_at"]),
                created_at=int(row["created_at"]),
            )
            for row in rows
        ]

    def list_recent_restrictions(self, *, limit: int = 12, player_uuid: str | None = None) -> list[DiscordAuthEventRecord]:
        return self.list_recent_events(
            limit=limit,
            player_uuid=player_uuid,
            event_types={"ban", "unban", "tempban", "tempunban"},
        )
