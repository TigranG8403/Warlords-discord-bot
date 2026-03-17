from __future__ import annotations

import subprocess
from http.server import ThreadingHTTPServer
from pathlib import Path

from .access_store import AllowedUserStore
from .git_ops import GitRepository, GitSnapshot
from .server_shared import (
    OAUTH_STATE_TTL_SECONDS,
    CommandResult,
    ExpiringTokenStore,
    PanelConfig,
    SessionStore,
    build_status_text,
    parse_key_value_output,
    trim_output,
)


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], request_handler_class, config: PanelConfig) -> None:
        super().__init__(server_address, request_handler_class)
        self.config = config
        self.sessions = SessionStore()
        self.oauth_states = ExpiringTokenStore(ttl_seconds=OAUTH_STATE_TTL_SECONDS)
        self.allowed_users = AllowedUserStore(Path(self.config.allowed_users_file), protected_ids=set(self.config.protected_discord_ids))
        self.repo = GitRepository(
            self.run,
            app_dir=self.config.app_dir,
            app_user=self.config.app_user,
            remote_name=self.config.git_remote,
        )

    def run(self, args: list[str], *, timeout: int = 30) -> CommandResult:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part).strip()
        return CommandResult(returncode=completed.returncode, output=trim_output(output))

    def sudo_systemctl(self, *args: str, timeout: int = 30) -> CommandResult:
        return self.run(["sudo", "-n", "systemctl", *args], timeout=timeout)

    def service_snapshot(self) -> dict[str, str]:
        result = self.sudo_systemctl(
            "show",
            self.config.service_name,
            "--property=Id,Description,LoadState,ActiveState,SubState,MainPID,ExecMainPID,ExecMainStatus,ActiveEnterTimestamp,FragmentPath",
        )
        if result.returncode != 0:
            raise RuntimeError(result.output or "Failed to query service status.")
        data = parse_key_value_output(result.output)
        data["status_text"] = build_status_text(data.get("ActiveState", ""), data.get("SubState", ""))
        return data

    def git_snapshot(self) -> GitSnapshot:
        return self.repo.snapshot()

    def logs_snapshot(self) -> str:
        result = self.run(
            [
                "sudo",
                "-n",
                "journalctl",
                "-u",
                self.config.service_name,
                "-n",
                str(self.config.log_lines),
                "--no-pager",
            ],
            timeout=30,
        )
        return result.output or "No logs yet."

    def perform_action(self, action: str, *, branch: str = "") -> tuple[str, str, str]:
        actions = {
            "fetch": self._fetch_remote,
            "start": self._start_service,
            "stop": self._stop_service,
            "restart": self._restart_service,
            "update": self._update_service,
            "switch_branch": lambda: self._switch_branch(branch),
        }
        handler = actions.get(action)
        if handler is None:
            return ("error", "Unknown action", f"Unsupported action: {action}")
        return handler()

    def _fetch_remote(self) -> tuple[str, str, str]:
        result = self.repo.fetch_remote()
        if result.returncode != 0:
            return ("error", "Fetch failed", result.output or "git fetch failed")
        return ("success", "Git refs updated", result.output or f"Fetched {self.config.git_remote}.")

    def _start_service(self) -> tuple[str, str, str]:
        result = self.sudo_systemctl("start", self.config.service_name)
        if result.returncode != 0:
            return ("error", "Start failed", result.output or "systemctl start failed")
        status = self.sudo_systemctl("is-active", self.config.service_name)
        return ("success", "Bot started", status.output or "Service started.")

    def _stop_service(self) -> tuple[str, str, str]:
        result = self.sudo_systemctl("stop", self.config.service_name)
        if result.returncode != 0:
            return ("error", "Stop failed", result.output or "systemctl stop failed")
        status = self.sudo_systemctl("is-active", self.config.service_name)
        return ("success", "Bot stopped", status.output or "Service stopped.")

    def _restart_service(self) -> tuple[str, str, str]:
        result = self.sudo_systemctl("restart", self.config.service_name, timeout=60)
        if result.returncode != 0:
            return ("error", "Restart failed", result.output or "systemctl restart failed")
        status = self.sudo_systemctl("status", "--no-pager", self.config.service_name, timeout=60)
        return ("success", "Bot restarted", status.output or "Service restarted.")

    def _update_service(self) -> tuple[str, str, str]:
        results = self.repo.update_current_branch()
        restart_result = self.sudo_systemctl("restart", self.config.service_name, timeout=60)
        return combine_action_results(
            success_title="Bot updated",
            failure_title="Update failed",
            final_failure_title="Restart after update failed",
            results=results,
            final_result=restart_result,
            fallback_output="Update completed.",
        )

    def _switch_branch(self, branch: str) -> tuple[str, str, str]:
        results = self.repo.switch_branch(branch)
        restart_result = self.sudo_systemctl("restart", self.config.service_name, timeout=60)
        return combine_action_results(
            success_title=f"Switched to {branch}",
            failure_title=f"Switch to {branch} failed",
            final_failure_title="Restart after branch switch failed",
            results=results,
            final_result=restart_result,
            fallback_output="Branch switched.",
        )


def combine_action_results(
    *,
    success_title: str,
    failure_title: str,
    final_failure_title: str,
    results: list[CommandResult],
    final_result: CommandResult,
    fallback_output: str,
) -> tuple[str, str, str]:
    parts = [part for part in [*(result.output for result in results), final_result.output] if part]
    output = "\n\n".join(parts).strip() or fallback_output
    for result in results:
        if result.returncode != 0:
            return ("error", failure_title, output)
    if final_result.returncode != 0:
        return ("error", final_failure_title, output)
    return ("success", success_title, output)
