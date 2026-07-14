from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .remote import REMOTE_DOCKER, SERVER_CONTAINER, _ssh


DEFAULT_CHAT_DB = Path.cwd() / ".paledit-data" / "chat.sqlite3"
_INITIAL_HISTORY = "168h"
_DOCKER_LINE = re.compile(r"^(?P<logged_at>\S+)\s+(?P<body>.*)$")
_CHAT_LINE = re.compile(
    r"^\[(?P<game_at>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+"
    r"\[CHAT\]\s+<(?P<player>.*?)>\s?(?P<message>.*)$"
)
_SYNC_LOCK = threading.Lock()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            logged_at TEXT NOT NULL,
            game_at TEXT NOT NULL,
            player_name TEXT NOT NULL,
            message TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chat_messages_logged_at
            ON chat_messages(logged_at DESC);
        CREATE TABLE IF NOT EXISTS chat_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    return connection


def parse_chat_logs(text: str) -> tuple[list[dict[str, str]], str | None]:
    messages: list[dict[str, str]] = []
    newest_timestamp: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        docker_match = _DOCKER_LINE.match(line)
        if not docker_match:
            continue
        logged_at = docker_match.group("logged_at")
        if newest_timestamp is None or logged_at > newest_timestamp:
            newest_timestamp = logged_at
        chat_match = _CHAT_LINE.match(docker_match.group("body"))
        if not chat_match:
            continue
        player = chat_match.group("player")
        message = chat_match.group("message")
        message_id = hashlib.sha256(f"{logged_at}\0{player}\0{message}".encode()).hexdigest()
        messages.append({
            "id": message_id,
            "logged_at": logged_at,
            "game_at": chat_match.group("game_at"),
            "player_name": player,
            "message": message,
        })
    return messages, newest_timestamp


def _remote_logs(since: str | None) -> str:
    arguments = [REMOTE_DOCKER, "logs", "--timestamps"]
    arguments.extend(["--since", since or _INITIAL_HISTORY])
    arguments.append(SERVER_CONTAINER)
    result = _ssh(arguments, timeout=30)
    return "\n".join(part for part in (result.stdout, result.stderr) if part)


def _stored_messages(connection: sqlite3.Connection, limit: int) -> list[dict[str, str]]:
    rows = connection.execute(
        """
        SELECT id, logged_at, game_at, player_name, message
        FROM chat_messages
        ORDER BY logged_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def archive_system_message(path: Path, message: str) -> dict[str, str]:
    clean_message = " ".join(message.split()).strip()
    if not clean_message:
        raise ValueError("系统消息不能为空")

    now = datetime.now().astimezone()
    logged_at = now.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    row = {
        "id": hashlib.sha256(f"system\0{logged_at}\0{clean_message}".encode()).hexdigest(),
        "logged_at": logged_at,
        "game_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "player_name": "系统",
        "message": clean_message,
    }
    with _SYNC_LOCK, _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO chat_messages(id, logged_at, game_at, player_name, message)
            VALUES (:id, :logged_at, :game_at, :player_name, :message)
            """,
            row,
        )
    return row


def sync_chat_history(path: Path = DEFAULT_CHAT_DB, limit: int = 300) -> dict[str, object]:
    with _SYNC_LOCK, _connect(path) as connection:
        cursor_row = connection.execute(
            "SELECT value FROM chat_meta WHERE key = 'docker_cursor'"
        ).fetchone()
        cursor = str(cursor_row["value"]) if cursor_row else None
        imported = 0
        warning = None
        try:
            messages, newest_timestamp = parse_chat_logs(_remote_logs(cursor))
            before = connection.total_changes
            connection.executemany(
                """
                INSERT OR IGNORE INTO chat_messages(id, logged_at, game_at, player_name, message)
                VALUES (:id, :logged_at, :game_at, :player_name, :message)
                """,
                messages,
            )
            imported = connection.total_changes - before
            if newest_timestamp is not None:
                connection.execute(
                    """
                    INSERT INTO chat_meta(key, value) VALUES ('docker_cursor', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (newest_timestamp,),
                )
        except RuntimeError as error:
            warning = str(error)

        stored_count = int(connection.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0])
        return {
            "messages": _stored_messages(connection, limit),
            "stored_count": stored_count,
            "imported": imported,
            "database_path": str(path.resolve()),
            "warning": warning,
        }
