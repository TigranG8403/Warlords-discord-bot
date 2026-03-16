from __future__ import annotations

import unittest

from tests import support  # noqa: F401
from admin_panel.git_ops import GitSnapshot, format_tracking_status, parse_ahead_behind, parse_branch_list, summarize_worktree
from admin_panel.render import DashboardPageData, FlashMessage, LoginPageData, build_branch_picker, render_dashboard_page, render_login_page
from admin_panel.server import SessionStore, build_status_text, constant_time_equal, parse_key_value_output, trim_output


HERO_DESCRIPTION = "Панель для управления ботом, сервисом и ветками."


class PanelHelpersTests(unittest.TestCase):
    def test_parse_key_value_output_preserves_values_with_equals(self) -> None:
        output = "ActiveState=active\nFragmentPath=/etc/systemd/system/x=y.service\nIgnoredLine\n"
        parsed = parse_key_value_output(output)
        self.assertEqual(parsed["ActiveState"], "active")
        self.assertEqual(parsed["FragmentPath"], "/etc/systemd/system/x=y.service")
        self.assertNotIn("IgnoredLine", parsed)

    def test_constant_time_equal_handles_unicode_without_crashing(self) -> None:
        self.assertTrue(constant_time_equal("пароль", "пароль"))
        self.assertFalse(constant_time_equal("пароль", "password"))

    def test_trim_output_keeps_tail_when_truncating(self) -> None:
        output = "A" * 5 + "B" * 20
        trimmed = trim_output(output, limit=12)
        self.assertTrue(trimmed.startswith("[output truncated]"))
        self.assertTrue(trimmed.endswith("B" * 12))

    def test_session_store_expires_entries(self) -> None:
        current_time = 100.0

        def fake_time() -> float:
            return current_time

        store = SessionStore(ttl_seconds=10, time_func=fake_time)
        session_id, session = store.create()
        self.assertEqual(store.get(session_id), session)

        current_time = 200.0
        self.assertIsNone(store.get(session_id))

    def test_build_status_text_formats_pairs(self) -> None:
        self.assertEqual(build_status_text("active", "running"), "Active / running")
        self.assertEqual(build_status_text("failed", ""), "Failed")

    def test_parse_branch_list_skips_remote_head(self) -> None:
        output = "origin/HEAD\norigin/v2\norigin/v1-old\norigin/v2\n"
        self.assertEqual(parse_branch_list(output, "origin"), ["v1-old", "v2"])

    def test_summarize_worktree_and_tracking_status(self) -> None:
        self.assertEqual(summarize_worktree(""), "clean")
        self.assertEqual(summarize_worktree(" M foo.py\n?? bar.py\n"), "dirty (2 changes)")
        self.assertEqual(format_tracking_status(0, 0), "up to date")
        self.assertEqual(format_tracking_status(3, 1), "ahead 3, behind 1")

    def test_parse_ahead_behind_counts(self) -> None:
        self.assertEqual(parse_ahead_behind("2\t5"), (5, 2))
        self.assertEqual(parse_ahead_behind("oops"), (0, 0))

    def test_login_page_escapes_error_message(self) -> None:
        page = render_login_page(LoginPageData(title="Panel", error='<bad "input">'))
        self.assertIn("&lt;bad &quot;input&quot;&gt;", page)

    def test_dashboard_page_renders_branch_picker_and_flash(self) -> None:
        page = render_dashboard_page(
            DashboardPageData(
                csrf_token="token-1",
                service_name="warlords-bot",
                service_data={"Id": "warlords-bot", "status_text": "Active / running", "ActiveState": "active"},
                git_data=GitSnapshot(
                    remote_name="origin",
                    remote_url="https://example.com/repo.git",
                    current_branch="v2",
                    commit="abc123",
                    subject="Latest commit",
                    upstream="origin/v2",
                    ahead=0,
                    behind=0,
                    worktree_status="clean",
                    branches=("v1-old", "v2"),
                ),
                tracking_status="up to date",
                logs="log line",
                flash=FlashMessage(level="success", title="Done", output="Updated"),
            )
        )
        self.assertIn('data-value="v1-old"', page)
        self.assertIn('data-value="v2"', page)
        self.assertIn("Done", page)
        self.assertIn("Updated", page)
        self.assertIn(HERO_DESCRIPTION, page)
        self.assertIn('class="branch-picker"', page)
        self.assertIn("dropdown-bloom", page)
        self.assertIn('data-branch-trigger', page)
        self.assertIn('data-branch-menu', page)
        self.assertIn('content="240"', page)

    def test_build_branch_picker_returns_empty_state(self) -> None:
        markup = build_branch_picker("v2", ())
        self.assertIn("No remote branches", markup)
        self.assertIn('data-branch-input', markup)
        self.assertIn('disabled', markup)


if __name__ == "__main__":
    unittest.main()
