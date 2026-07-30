from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile


ACTIVE_DATABASES = (
    "tickets.sqlite3",
    "kompromat.sqlite3",
    "panel_registry.sqlite3",
)
ARCHIVE_ONLY_DATABASES = (
    "discordauth.sqlite3",
    "moderation.sqlite3",
)
ENABLED_MODULES = "tickets,welcome,rules,roles,kompromat,presence,flytrap,greetings,maintenance"


def read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {"'", '"'}
        ):
            quote = normalized_value[0]
            normalized_value = normalized_value[1:-1]
            if quote == '"':
                normalized_value = _unescape_double_quoted(normalized_value)
        values[normalized_key] = normalized_value
    return values


def collect_update_user_ids(panel_env: dict[str, str]) -> tuple[str, ...]:
    user_ids = {
        value.strip()
        for value in panel_env.get("PANEL_INITIAL_ALLOWED_DISCORD_IDS", "").split(",")
        if value.strip().isdigit()
    }

    allowed_users_path = panel_env.get("PANEL_ALLOWED_USERS_FILE", "").strip()
    if allowed_users_path:
        try:
            payload = json.loads(Path(allowed_users_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        users = payload.get("users", []) if isinstance(payload, dict) else []
        for user in users:
            if not isinstance(user, dict):
                continue
            user_id = user.get("user_id")
            if isinstance(user_id, str) and user_id.isdigit():
                user_ids.add(user_id)

    return tuple(sorted(user_ids, key=int))


def build_production_env(
    legacy_env: dict[str, str],
    panel_env: dict[str, str],
) -> dict[str, str]:
    discord_token = legacy_env.get("DISCORD_TOKEN", "").strip()
    if not discord_token:
        raise RuntimeError("Legacy environment does not contain DISCORD_TOKEN.")

    values = {
        "DISCORD_TOKEN": discord_token,
        "ENABLED_MODULES": ENABLED_MODULES,
        "BOT_UPDATE_ALLOWED_USER_IDS": ",".join(collect_update_user_ids(panel_env)),
    }
    guild_id = legacy_env.get("APP_COMMAND_GUILD_ID", "").strip()
    if guild_id:
        values["APP_COMMAND_GUILD_ID"] = guild_id

    ai_base_url = (
        legacy_env.get("MODERATION_AI_BASE_URL", "").strip()
        or legacy_env.get("MODERATION_AI_URL", "").strip()
    )
    ai_model = legacy_env.get("MODERATION_AI_MODEL", "").strip()
    if ai_base_url and ai_model:
        values["AI_BASE_URL"] = ai_base_url
        values["AI_MODEL"] = ai_model
        values["AI_API_KEY"] = (
            legacy_env.get("MODERATION_AI_API_KEY", "").strip()
            or legacy_env.get("MODERATION_AI_TOKEN", "").strip()
        )
        values["AI_TIMEOUT_SECONDS"] = legacy_env.get(
            "MODERATION_AI_TIMEOUT",
            "30",
        ).strip() or "30"
        values["AI_MAX_RESPONSE_BYTES"] = "1000000"

    return values


def write_systemd_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{key}={_quote_env_value(value)}"
        for key, value in values.items()
    ]

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as env_file:
            env_file.write("\n".join(lines) + "\n")
            env_file.flush()
            os.fsync(env_file.fileno())
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(path)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise


def backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    with closing(sqlite3.connect(source)) as source_connection:
        with closing(sqlite3.connect(destination)) as destination_connection:
            source_connection.backup(destination_connection)
            destination_connection.commit()


def migrate_databases(
    legacy_data_dir: Path,
    backup_data_dir: Path,
    target_data_dir: Path,
) -> tuple[int, int]:
    archived_count = 0
    active_count = 0
    for database_name in (*ACTIVE_DATABASES, *ARCHIVE_ONLY_DATABASES):
        source = legacy_data_dir / database_name
        if not source.is_file():
            continue

        backup_sqlite(source, backup_data_dir / database_name)
        archived_count += 1
        if database_name not in ACTIVE_DATABASES:
            continue

        target = target_data_dir / database_name
        backup_sqlite(source, target)
        active_count += 1

        if database_name == "panel_registry.sqlite3":
            with closing(sqlite3.connect(target)) as connection:
                table_exists = connection.execute(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'panel_records'
                    """
                ).fetchone()
                if table_exists is not None:
                    connection.execute(
                        "DELETE FROM panel_records WHERE namespace = ?",
                        ("discordauth",),
                    )
                    connection.commit()

    return active_count, archived_count


def _quote_env_value(value: str) -> str:
    if "\n" in value or "\r" in value or "\0" in value:
        raise ValueError("Environment values must be single-line strings.")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _unescape_double_quoted(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character == "\\" and index + 1 < len(value):
            escaped_character = value[index + 1]
            if escaped_character in {'"', "\\"}:
                result.append(escaped_character)
                index += 2
                continue
        result.append(character)
        index += 1
    return "".join(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-env", type=Path, required=True)
    parser.add_argument("--panel-env", type=Path, required=True)
    parser.add_argument("--legacy-data", type=Path, required=True)
    parser.add_argument("--backup-data", type=Path, required=True)
    parser.add_argument("--target-data", type=Path, required=True)
    parser.add_argument("--target-env", type=Path, required=True)
    args = parser.parse_args()

    legacy_env = read_env_file(args.legacy_env)
    panel_env = read_env_file(args.panel_env)
    production_env = build_production_env(legacy_env, panel_env)
    active_count, archived_count = migrate_databases(
        args.legacy_data,
        args.backup_data,
        args.target_data,
    )
    write_systemd_env(args.target_env, production_env)

    print(f"active_database_count={active_count}")
    print(f"archived_database_count={archived_count}")
    print(
        "update_user_count="
        f"{len(collect_update_user_ids(panel_env))}"
    )


if __name__ == "__main__":
    main()
