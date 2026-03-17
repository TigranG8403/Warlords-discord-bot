from __future__ import annotations

import sqlite3

from .config import (
    LINK_CODE_TTL_SECONDS,
    DiscordAuthPlayerRecord,
    DiscordAuthPresenceRecord,
    LinkCodeRecord,
)


class DiscordAuthPlayersMixin:
    def register_link_code(
        self,
        *,
        code: str,
        player_uuid: str,
        player_name: str,
        ttl_seconds: int = LINK_CODE_TTL_SECONDS,
    ) -> LinkCodeRecord:
        normalized_code = code.strip().upper()
        if not normalized_code:
            raise ValueError("Код привязки не может быть пустым.")

        now = self._now()
        record = LinkCodeRecord(
            code=normalized_code,
            player_uuid=player_uuid.strip(),
            player_name=player_name.strip() or player_uuid.strip(),
            created_at=now,
            expires_at=now + max(ttl_seconds, 30),
        )
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            connection.execute(
                """
                INSERT INTO link_codes (code, player_uuid, player_name, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    player_uuid = excluded.player_uuid,
                    player_name = excluded.player_name,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (
                    record.code,
                    record.player_uuid,
                    record.player_name,
                    record.created_at,
                    record.expires_at,
                ),
            )
            self._record_metrics_snapshot_locked(connection, now)
        return record

    def consume_link_code(
        self,
        *,
        code: str,
        discord_user_id: int,
        discord_username: str,
        discord_display_name: str,
    ) -> DiscordAuthPlayerRecord | None:
        normalized_code = code.strip().upper()
        now = self._now()
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            row = connection.execute(
                """
                SELECT code, player_uuid, player_name, created_at, expires_at
                FROM link_codes
                WHERE code = ?
                """,
                (normalized_code,),
            ).fetchone()
            if row is None:
                return None

            record = LinkCodeRecord(
                code=row["code"],
                player_uuid=row["player_uuid"],
                player_name=row["player_name"],
                created_at=int(row["created_at"]),
                expires_at=int(row["expires_at"]),
            )
            connection.execute("DELETE FROM link_codes WHERE code = ?", (normalized_code,))
            current = self._get_player_locked(connection, record.player_uuid)
            next_name = current.player_name if current is not None and current.player_name else record.player_name
            connection.execute(
                """
                INSERT INTO player_records (
                    player_uuid,
                    player_name,
                    discord_user_id,
                    discord_username,
                    discord_display_name,
                    access_state,
                    admin_status,
                    temp_ban_until,
                    temp_ban_reason,
                    admin_note,
                    last_ip,
                    last_authenticated_at,
                    is_online,
                    online_since,
                    last_seen_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_uuid) DO UPDATE SET
                    player_name = excluded.player_name,
                    discord_user_id = excluded.discord_user_id,
                    discord_username = excluded.discord_username,
                    discord_display_name = excluded.discord_display_name,
                    updated_at = excluded.updated_at
                """,
                (
                    record.player_uuid,
                    next_name,
                    discord_user_id,
                    discord_username.strip(),
                    discord_display_name.strip(),
                    current.access_state if current is not None else "AUTO",
                    current.admin_status if current is not None else "",
                    current.temp_ban_until if current is not None else 0,
                    current.temp_ban_reason if current is not None else "",
                    current.admin_note if current is not None else "",
                    current.last_ip if current is not None else "",
                    current.last_authenticated_at if current is not None else 0,
                    0,
                    0,
                    current.last_seen_at if current is not None else 0,
                    now,
                ),
            )
            result = self._get_player_locked(connection, record.player_uuid)
            if result is None:
                return None
            self._prune_orphan_duplicates_locked(connection, result.player_uuid, result.player_name)
            self._record_event_locked(connection, "link", result.player_uuid, result.player_name, now)
            self._record_metrics_snapshot_locked(connection, now)
            return result

    def get_player(self, player_uuid: str) -> DiscordAuthPlayerRecord | None:
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            return self._get_player_locked(connection, player_uuid)

    def list_players(self) -> list[DiscordAuthPlayerRecord]:
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            rows = connection.execute(
                """
                SELECT *
                FROM player_records
                ORDER BY LOWER(player_name) ASC, player_uuid ASC
                """
            ).fetchall()
        return [self._row_to_player(row) for row in rows]

    def find_player_by_discord_user_id(self, discord_user_id: int) -> DiscordAuthPlayerRecord | None:
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            row = connection.execute(
                """
                SELECT *
                FROM player_records
                WHERE discord_user_id = ?
                LIMIT 1
                """,
                (discord_user_id,),
            ).fetchone()
        return self._row_to_player(row) if row is not None else None

    def unlink_player(self, player_uuid: str) -> DiscordAuthPlayerRecord | None:
        with self._connection() as connection:
            current = self._get_player_locked(connection, player_uuid)
            if current is None:
                return None
            now = self._now()
            connection.execute(
                """
                UPDATE player_records
                SET
                    discord_user_id = 0,
                    discord_username = '',
                    discord_display_name = '',
                    last_ip = '',
                    last_authenticated_at = 0,
                    updated_at = ?
                WHERE player_uuid = ?
                """,
                (now, player_uuid),
            )
            self._record_event_locked(connection, "unlink", current.player_uuid, current.player_name, now)
            self._record_metrics_snapshot_locked(connection, now)
            return self._get_player_locked(connection, player_uuid)

    def touch_player_auth(self, *, player_uuid: str, player_name: str, ip_address: str) -> DiscordAuthPlayerRecord:
        now = self._now()
        with self._connection() as connection:
            current = self._get_player_locked(connection, player_uuid)
            player_name_value = player_name.strip() or (current.player_name if current is not None else player_uuid)
            ip_value = ip_address.strip()
            online_since = current.online_since if current is not None and current.is_online and current.online_since > 0 else now
            if current is None:
                connection.execute(
                    """
                    INSERT INTO player_records (
                        player_uuid,
                        player_name,
                        discord_user_id,
                        discord_username,
                        discord_display_name,
                        access_state,
                        admin_status,
                        temp_ban_until,
                        temp_ban_reason,
                        admin_note,
                        last_ip,
                        last_authenticated_at,
                        is_online,
                        online_since,
                        last_seen_at,
                        updated_at
                    )
                    VALUES (?, ?, 0, '', '', 'AUTO', '', 0, '', '', ?, ?, 1, ?, ?, ?)
                    """,
                    (player_uuid, player_name_value, ip_value, now, online_since, now, now),
                )
            else:
                connection.execute(
                    """
                    UPDATE player_records
                    SET
                        player_name = ?,
                        last_ip = ?,
                        last_authenticated_at = ?,
                        is_online = 1,
                        online_since = ?,
                        last_seen_at = ?,
                        updated_at = ?
                    WHERE player_uuid = ?
                    """,
                    (player_name_value, ip_value, now, online_since, now, now, player_uuid),
                )
            record = self._get_player_locked(connection, player_uuid)
            if record is None:
                raise RuntimeError(f"Player record {player_uuid} was not created.")
            self._prune_orphan_duplicates_locked(connection, record.player_uuid, record.player_name)
            self._record_event_locked(connection, "login", record.player_uuid, record.player_name, now)
            self._record_metrics_snapshot_locked(connection, now)
            return record

    def sync_online_players(self, players: list[DiscordAuthPresenceRecord]) -> int:
        now = self._now()
        normalized: dict[str, DiscordAuthPresenceRecord] = {}
        for player in players:
            player_uuid = player.player_uuid.strip()
            if not player_uuid:
                continue
            normalized[player_uuid] = DiscordAuthPresenceRecord(
                player_uuid=player_uuid,
                player_name=player.player_name.strip() or player_uuid,
                ip_address=player.ip_address.strip(),
            )

        with self._connection() as connection:
            current_online_rows = connection.execute(
                """
                SELECT player_uuid
                FROM player_records
                WHERE is_online = 1
                """
            ).fetchall()
            current_online = {str(row["player_uuid"]) for row in current_online_rows}

            for player_uuid, player in normalized.items():
                current = self._get_player_locked(connection, player_uuid)
                online_since = current.online_since if current is not None and current.is_online and current.online_since > 0 else now
                if current is None:
                    connection.execute(
                        """
                        INSERT INTO player_records (
                            player_uuid,
                            player_name,
                            discord_user_id,
                            discord_username,
                            discord_display_name,
                            access_state,
                            admin_status,
                            temp_ban_until,
                            temp_ban_reason,
                            admin_note,
                            last_ip,
                            last_authenticated_at,
                            is_online,
                            online_since,
                            last_seen_at,
                            updated_at
                        )
                        VALUES (?, ?, 0, '', '', 'AUTO', '', 0, '', '', ?, 0, 1, ?, ?, ?)
                        """,
                        (player_uuid, player.player_name, player.ip_address, online_since, now, now),
                    )
                    self._prune_orphan_duplicates_locked(connection, player_uuid, player.player_name)
                    continue

                connection.execute(
                    """
                    UPDATE player_records
                    SET
                        player_name = ?,
                        last_ip = CASE
                            WHEN ? != '' THEN ?
                            ELSE last_ip
                        END,
                        is_online = 1,
                        online_since = ?,
                        last_seen_at = ?,
                        updated_at = ?
                    WHERE player_uuid = ?
                    """,
                    (player.player_name, player.ip_address, player.ip_address, online_since, now, now, player_uuid),
                )
                self._prune_orphan_duplicates_locked(connection, player_uuid, player.player_name)

            players_to_mark_offline = current_online - set(normalized)
            if players_to_mark_offline:
                placeholders = ", ".join("?" for _ in players_to_mark_offline)
                connection.execute(
                    f"""
                    UPDATE player_records
                    SET
                        is_online = 0,
                        online_since = 0,
                        last_seen_at = ?,
                        updated_at = ?
                    WHERE player_uuid IN ({placeholders})
                    """,
                    (now, now, *sorted(players_to_mark_offline)),
                )

            self._record_metrics_snapshot_locked(connection, now)
            return len(normalized)

    def _update_player_fields(self, player_uuid: str, **fields: object) -> DiscordAuthPlayerRecord | None:
        allowed_fields = {
            "access_state",
            "admin_status",
            "temp_ban_until",
            "temp_ban_reason",
            "admin_note",
        }
        invalid = set(fields) - allowed_fields
        if invalid:
            raise ValueError(f"Нельзя обновить поля: {', '.join(sorted(invalid))}")

        with self._connection() as connection:
            current = self._get_player_locked(connection, player_uuid)
            if current is None:
                return None

            now = self._now()
            next_values = {
                "access_state": current.access_state,
                "admin_status": current.admin_status,
                "temp_ban_until": current.temp_ban_until,
                "temp_ban_reason": current.temp_ban_reason,
                "admin_note": current.admin_note,
            }
            next_values.update(fields)
            connection.execute(
                """
                UPDATE player_records
                SET
                    access_state = ?,
                    admin_status = ?,
                    temp_ban_until = ?,
                    temp_ban_reason = ?,
                    admin_note = ?,
                    updated_at = ?
                WHERE player_uuid = ?
                """,
                (
                    next_values["access_state"],
                    next_values["admin_status"],
                    int(next_values["temp_ban_until"]),
                    next_values["temp_ban_reason"],
                    next_values["admin_note"],
                    now,
                    player_uuid,
                ),
            )
            self._record_metrics_snapshot_locked(connection, now)
            return self._get_player_locked(connection, player_uuid)

    def _get_player_locked(self, connection: sqlite3.Connection, player_uuid: str) -> DiscordAuthPlayerRecord | None:
        row = connection.execute(
            "SELECT * FROM player_records WHERE player_uuid = ?",
            (player_uuid,),
        ).fetchone()
        return self._row_to_player(row) if row is not None else None

    def _prune_orphan_duplicates_locked(
        self,
        connection: sqlite3.Connection,
        keep_player_uuid: str,
        player_name: str,
    ) -> None:
        normalized_name = player_name.strip()
        if not normalized_name:
            return
        connection.execute(
            """
            DELETE FROM player_records
            WHERE player_uuid != ?
              AND LOWER(player_name) = LOWER(?)
              AND discord_user_id = 0
              AND discord_username = ''
              AND discord_display_name = ''
              AND access_state = 'AUTO'
              AND admin_status = ''
              AND temp_ban_until <= 0
              AND temp_ban_reason = ''
              AND admin_note = ''
              AND last_ip = ''
              AND last_authenticated_at <= 0
              AND is_online = 0
              AND online_since <= 0
              AND last_seen_at <= 0
              AND NOT EXISTS (
                    SELECT 1
                    FROM login_sessions
                    WHERE login_sessions.player_uuid = player_records.player_uuid
                      AND login_sessions.status = 'PENDING'
              )
            """,
            (keep_player_uuid, normalized_name),
        )

    def _row_to_player(self, row: sqlite3.Row) -> DiscordAuthPlayerRecord:
        return DiscordAuthPlayerRecord(
            player_uuid=row["player_uuid"],
            player_name=row["player_name"],
            discord_user_id=int(row["discord_user_id"]),
            discord_username=row["discord_username"],
            discord_display_name=row["discord_display_name"],
            access_state=row["access_state"],
            admin_status=row["admin_status"],
            temp_ban_until=int(row["temp_ban_until"]),
            temp_ban_reason=row["temp_ban_reason"],
            admin_note=row["admin_note"],
            last_ip=row["last_ip"],
            last_authenticated_at=int(row["last_authenticated_at"]),
            is_online=bool(row["is_online"]),
            online_since=int(row["online_since"]),
            last_seen_at=int(row["last_seen_at"]),
        )
