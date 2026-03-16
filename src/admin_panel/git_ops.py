from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str


@dataclass(frozen=True)
class GitSnapshot:
    remote_name: str
    remote_url: str
    current_branch: str
    commit: str
    subject: str
    upstream: str
    ahead: int
    behind: int
    worktree_status: str
    branches: tuple[str, ...]


class CommandRunner(Protocol):
    def __call__(self, args: list[str], *, timeout: int = 30) -> CommandResult: ...


def parse_branch_list(output: str, remote_name: str) -> list[str]:
    branches: set[str] = set()
    prefix = f"{remote_name}/"
    for raw_line in output.splitlines():
        ref = raw_line.strip()
        if not ref:
            continue
        if ref == f"{remote_name}/HEAD" or ref.endswith("/HEAD"):
            continue
        if ref.startswith(prefix):
            ref = ref[len(prefix) :]
        branches.add(ref)
    return sorted(branches)


def summarize_worktree(output: str) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    if not lines:
        return "clean"
    return f"dirty ({len(lines)} changes)"


def parse_ahead_behind(output: str) -> tuple[int, int]:
    parts = output.strip().split()
    if len(parts) != 2:
        return 0, 0
    behind_raw, ahead_raw = parts
    if not behind_raw.isdigit() or not ahead_raw.isdigit():
        return 0, 0
    return int(ahead_raw), int(behind_raw)


def format_tracking_status(ahead: int, behind: int) -> str:
    if ahead == 0 and behind == 0:
        return "up to date"
    parts: list[str] = []
    if ahead:
        parts.append(f"ahead {ahead}")
    if behind:
        parts.append(f"behind {behind}")
    return ", ".join(parts)


class GitRepository:
    def __init__(self, runner: CommandRunner, *, app_dir: str, app_user: str, remote_name: str) -> None:
        self._runner = runner
        self._app_dir = app_dir
        self._app_user = app_user
        self.remote_name = remote_name

    def snapshot(self) -> GitSnapshot:
        remote_url_result = self.git("remote", "get-url", self.remote_name)
        branch_result = self.git("branch", "--show-current")
        commit_result = self.git("rev-parse", "--short", "HEAD")
        subject_result = self.git("log", "-1", "--pretty=%s")
        upstream_result = self.git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
        status_result = self.git("status", "--short")
        branches_result = self.git("for-each-ref", "--format=%(refname:short)", f"refs/remotes/{self.remote_name}")

        ahead = 0
        behind = 0
        upstream = upstream_result.output if upstream_result.returncode == 0 else ""
        if upstream:
            tracking_result = self.git("rev-list", "--left-right", "--count", f"{upstream}...HEAD")
            if tracking_result.returncode == 0:
                ahead, behind = parse_ahead_behind(tracking_result.output)

        return GitSnapshot(
            remote_name=self.remote_name,
            remote_url=remote_url_result.output or f"{self.remote_name} is not configured",
            current_branch=branch_result.output or "detached",
            commit=commit_result.output or "unknown",
            subject=subject_result.output or "No commit subject available",
            upstream=upstream,
            ahead=ahead,
            behind=behind,
            worktree_status=summarize_worktree(status_result.output),
            branches=tuple(parse_branch_list(branches_result.output, self.remote_name)),
        )

    def fetch_remote(self) -> CommandResult:
        return self.git("fetch", "--prune", self.remote_name, timeout=300)

    def update_current_branch(self) -> list[CommandResult]:
        snapshot = self.snapshot()
        if snapshot.current_branch == "detached":
            return [CommandResult(returncode=1, output="Repository is in detached HEAD state. Switch to a branch first.")]

        return [
            self.fetch_remote(),
            self.git("pull", "--ff-only", snapshot.remote_name, snapshot.current_branch, timeout=300),
            self.pip_install(timeout=600),
        ]

    def switch_branch(self, branch: str) -> list[CommandResult]:
        target_branch = branch.strip()
        if not target_branch:
            return [CommandResult(returncode=1, output="Select a branch before switching.")]

        validation = self.git("check-ref-format", "--branch", target_branch)
        if validation.returncode != 0:
            return [validation]

        remote_ref = f"{self.remote_name}/{target_branch}"
        current_branch = self.git("branch", "--show-current").output.strip()
        results: list[CommandResult] = [self.fetch_remote()]
        if results[-1].returncode != 0:
            return results

        remote_exists = self.git("show-ref", "--verify", "--quiet", f"refs/remotes/{remote_ref}")
        if remote_exists.returncode != 0:
            return results + [CommandResult(returncode=1, output=f"Remote branch {remote_ref} does not exist.")]

        local_exists = self.git("show-ref", "--verify", "--quiet", f"refs/heads/{target_branch}")
        if current_branch != target_branch:
            if local_exists.returncode == 0:
                switch_result = self.git("switch", target_branch, timeout=60)
            else:
                switch_result = self.git("switch", "--track", "-c", target_branch, remote_ref, timeout=60)
            results.append(switch_result)
            if switch_result.returncode != 0:
                return results

        results.append(self.git("branch", "--set-upstream-to", remote_ref, target_branch, timeout=30))
        results.append(self.git("pull", "--ff-only", self.remote_name, target_branch, timeout=300))
        results.append(self.pip_install(timeout=600))
        return results

    def git(self, *args: str, timeout: int = 30) -> CommandResult:
        return self._run_as_app_user(["git", "-C", self._app_dir, *args], timeout=timeout)

    def pip_install(self, *, timeout: int = 600) -> CommandResult:
        python_bin = f"{self._app_dir}/.venv/bin/python"
        requirements_file = f"{self._app_dir}/requirements.txt"
        return self._run_as_app_user([python_bin, "-m", "pip", "install", "-r", requirements_file], timeout=timeout)

    def _run_as_app_user(self, args: list[str], *, timeout: int) -> CommandResult:
        return self._runner(["sudo", "-n", "-u", self._app_user, "-H", *args], timeout=timeout)
