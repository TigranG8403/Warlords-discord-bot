from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests import support  # noqa: F401
from modules.discordauth.config import DiscordAuthPresenceRecord
from modules.discordauth.service import DiscordAuthService


class DiscordAuthServiceTests(unittest.TestCase):
    def _make_service(self) -> tuple[tempfile.TemporaryDirectory[str], DiscordAuthService]:
        temp_dir = tempfile.TemporaryDirectory()
        service = DiscordAuthService(Path(temp_dir.name) / "discordauth.sqlite3")
        return temp_dir, service

    def test_touch_player_auth_marks_player_online_and_records_login_activity(self) -> None:
        temp_dir, service = self._make_service()
        self.addCleanup(temp_dir.cleanup)

        player = service.touch_player_auth(
            player_uuid="player-1",
            player_name="XxNagibator228xX",
            ip_address="10.0.0.10",
        )

        summary = service.build_dashboard_summary()
        metrics = service.build_dashboard_metrics()

        self.assertTrue(player.is_online)
        self.assertEqual(summary.total_players, 1)
        self.assertEqual(summary.online_players, 1)
        self.assertEqual(metrics.online_now, 1)
        self.assertEqual(sum(point.login_count for point in metrics.activity_history), 1)

    def test_sync_online_players_updates_presence_and_clears_offline_players(self) -> None:
        temp_dir, service = self._make_service()
        self.addCleanup(temp_dir.cleanup)

        service.sync_online_players(
            [
                DiscordAuthPresenceRecord(
                    player_uuid="player-2",
                    player_name="zxc_Danil_zxc",
                    ip_address="10.0.0.20",
                )
            ]
        )

        summary = service.build_dashboard_summary()
        player = service.get_player("player-2")
        self.assertIsNotNone(player)
        assert player is not None
        self.assertTrue(player.is_online)
        self.assertEqual(summary.online_players, 1)

        service.sync_online_players([])

        summary = service.build_dashboard_summary()
        player = service.get_player("player-2")
        self.assertIsNotNone(player)
        assert player is not None
        self.assertFalse(player.is_online)
        self.assertEqual(summary.online_players, 0)

    def test_touch_player_auth_prunes_empty_duplicate_record_with_same_name(self) -> None:
        temp_dir, service = self._make_service()
        self.addCleanup(temp_dir.cleanup)

        with service._connection() as connection:
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
                VALUES (?, ?, 0, '', '', 'AUTO', '', 0, '', '', '', 0, 0, 0, 0, 0)
                """,
                ("online-uuid", "Nagibator_228"),
            )

        service.touch_player_auth(
            player_uuid="offline-uuid",
            player_name="Nagibator_228",
            ip_address="10.0.0.99",
        )

        self.assertIsNone(service.get_player("online-uuid"))
        self.assertIsNotNone(service.get_player("offline-uuid"))

    def test_consume_link_code_records_link_activity(self) -> None:
        temp_dir, service = self._make_service()
        self.addCleanup(temp_dir.cleanup)

        service.register_link_code(
            code="ABC123",
            player_uuid="player-3",
            player_name="Makson4ik228",
        )
        player = service.consume_link_code(
            code="ABC123",
            discord_user_id=42,
            discord_username="makson4ik228",
            discord_display_name="Makson4ik228",
        )

        metrics = service.build_dashboard_metrics()

        self.assertIsNotNone(player)
        self.assertEqual(sum(point.link_count for point in metrics.activity_history), 1)

    def test_ban_and_tempban_are_recorded_in_restriction_history(self) -> None:
        temp_dir, service = self._make_service()
        self.addCleanup(temp_dir.cleanup)

        service.touch_player_auth(
            player_uuid="player-4",
            player_name="Krutoi_Pacanchik",
            ip_address="10.0.0.40",
        )

        banned = service.ban_player("player-4", reason="Rule violation")
        temp_banned = service.apply_temp_ban("player-4", minutes=30, reason="Spam")
        restrictions = service.list_recent_restrictions(limit=5, player_uuid="player-4")
        history = service.build_sanction_history()

        self.assertIsNotNone(banned)
        self.assertIsNotNone(temp_banned)
        self.assertEqual([event.event_type for event in restrictions[:2]], ["tempban", "ban"])
        self.assertEqual(restrictions[0].reason, "Spam")
        self.assertEqual(sum(point.moderation_count for point in history), 2)

    def test_approved_login_session_updates_player_session_fields(self) -> None:
        temp_dir, service = self._make_service()
        self.addCleanup(temp_dir.cleanup)

        service.register_link_code(
            code="XYZ789",
            player_uuid="player-5",
            player_name="Vlad_A4_Fan228",
        )
        linked = service.consume_link_code(
            code="XYZ789",
            discord_user_id=55,
            discord_username="vlad_a4_fan228",
            discord_display_name="Vlad_A4_Fan228",
        )
        self.assertIsNotNone(linked)

        session = service.create_login_session(
            player_uuid="player-5",
            player_name="Vlad_A4_Fan228",
            address="127.0.0.1:25565",
            ip_address="10.0.0.55",
        )
        resolved = service.resolve_login_session(session.session_id, "APPROVED")
        player = service.get_player("player-5")

        self.assertIsNotNone(resolved)
        self.assertIsNotNone(player)
        assert player is not None
        self.assertEqual(player.last_ip, "10.0.0.55")
        self.assertGreater(player.last_authenticated_at, 0)
        self.assertEqual(player.discord_user_id, 55)

if __name__ == "__main__":
    unittest.main()
