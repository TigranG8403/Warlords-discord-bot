from __future__ import annotations

import time

from .config import LOGIN_SESSION_TTL_SECONDS, LoginSessionRecord


class DiscordAuthSessionsMixin:
    def create_login_session(
        self,
        *,
        player_uuid: str,
        player_name: str,
        address: str,
        ip_address: str,
        ttl_seconds: int = LOGIN_SESSION_TTL_SECONDS,
    ) -> LoginSessionRecord:
        player = self.get_player(player_uuid)
        if player is None or not player.linked:
            raise ValueError("Игрок ещё не привязан к Discord.")

        now = self._now()
        session = LoginSessionRecord(
            session_id=str(int(time.time_ns())),
            player_uuid=player_uuid,
            player_name=player_name.strip() or player.player_name,
            discord_user_id=player.discord_user_id,
            address=address.strip(),
            ip_address=ip_address.strip(),
            status="PENDING",
            created_at=now,
            expires_at=now + max(ttl_seconds, 30),
        )
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            connection.execute(
                """
                INSERT INTO login_sessions (
                    session_id,
                    player_uuid,
                    player_name,
                    discord_user_id,
                    address,
                    ip_address,
                    status,
                    created_at,
                    expires_at,
                    message_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.player_uuid,
                    session.player_name,
                    session.discord_user_id,
                    session.address,
                    session.ip_address,
                    session.status,
                    session.created_at,
                    session.expires_at,
                    session.message_id,
                ),
            )
            self._record_metrics_snapshot_locked(connection, now)
        return session

    def get_login_session(self, session_id: str) -> LoginSessionRecord | None:
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            row = connection.execute(
                "SELECT * FROM login_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            session = self._row_to_session(row)
            if session.status == "PENDING" and session.expires_at <= self._now():
                connection.execute(
                    "UPDATE login_sessions SET status = 'TIMEOUT' WHERE session_id = ?",
                    (session_id,),
                )
                row = connection.execute(
                    "SELECT * FROM login_sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                return self._row_to_session(row) if row is not None else None
            return session

    def set_login_message_id(self, session_id: str, message_id: int) -> LoginSessionRecord | None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE login_sessions SET message_id = ? WHERE session_id = ?",
                (message_id, session_id),
            )
            row = connection.execute(
                "SELECT * FROM login_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return self._row_to_session(row) if row is not None else None

    def resolve_login_session(self, session_id: str, status: str) -> LoginSessionRecord | None:
        normalized = status.strip().upper()
        if normalized not in {"APPROVED", "DENIED", "TIMEOUT", "DM_FAILED", "CANCELLED"}:
            raise ValueError("Недопустимый статус сессии.")
        with self._connection() as connection:
            now = self._now()
            connection.execute(
                """
                UPDATE login_sessions
                SET status = ?
                WHERE session_id = ? AND status = 'PENDING'
                """,
                (normalized, session_id),
            )
            row = connection.execute(
                "SELECT * FROM login_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if normalized == "APPROVED" and row is not None:
                player_uuid = str(row["player_uuid"])
                player_name = str(row["player_name"]).strip() or player_uuid
                ip_address = str(row["ip_address"]).strip()
                discord_user_id = int(row["discord_user_id"])
                current = self._get_player_locked(connection, player_uuid)
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
                        VALUES (?, ?, ?, '', '', 'AUTO', '', 0, '', '', ?, ?, 0, 0, 0, ?)
                        """,
                        (
                            player_uuid,
                            player_name,
                            discord_user_id,
                            ip_address,
                            now,
                            now,
                        ),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE player_records
                        SET
                            player_name = ?,
                            discord_user_id = CASE
                                WHEN discord_user_id = 0 THEN ?
                                ELSE discord_user_id
                            END,
                            last_ip = CASE
                                WHEN ? != '' THEN ?
                                ELSE last_ip
                            END,
                            last_authenticated_at = ?,
                            updated_at = ?
                        WHERE player_uuid = ?
                        """,
                        (
                            player_name,
                            discord_user_id,
                            ip_address,
                            ip_address,
                            now,
                            now,
                            player_uuid,
                        ),
                    )
            self._record_metrics_snapshot_locked(connection, now)
        return self._row_to_session(row) if row is not None else None

    def cancel_login_session(self, session_id: str) -> LoginSessionRecord | None:
        return self.resolve_login_session(session_id, "CANCELLED")

    def list_pending_login_sessions(self) -> list[LoginSessionRecord]:
        with self._connection() as connection:
            self._cleanup_expired_locked(connection)
            rows = connection.execute(
                """
                SELECT *
                FROM login_sessions
                WHERE status = 'PENDING'
                ORDER BY created_at DESC, session_id DESC
                """
            ).fetchall()
        return [self._row_to_session(row) for row in rows]
