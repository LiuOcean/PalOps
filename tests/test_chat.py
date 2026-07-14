import subprocess
from pathlib import Path

from paledit import api
from paledit.chat import archive_system_message, parse_chat_logs, sync_chat_history


LOGS = """2026-07-13T17:33:01.588701253Z [2026-07-14 01:33:00] [CHAT] <测试会长> 。。。。？
2026-07-13T17:33:06.627874618Z [2026-07-14 01:33:05] [CHAT] <玩家乙> 测试消息二
2026-07-13T17:33:07.000000000Z [2026-07-14 01:33:06] [LOG] player left the server.
"""


def test_parse_chat_logs_extracts_chat_and_tracks_latest_log_timestamp():
    messages, cursor = parse_chat_logs(LOGS)

    assert [(row["player_name"], row["message"]) for row in messages] == [
        ("测试会长", "。。。。？"),
        ("测试成员", "测试消息二"),
    ]
    assert cursor == "2026-07-13T17:33:07.000000000Z"
    assert len(messages[0]["id"]) == 64


def test_sync_chat_history_persists_and_deduplicates(tmp_path: Path, monkeypatch):
    calls = []

    def fake_ssh(arguments, timeout=30):
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout=LOGS, stderr="")

    monkeypatch.setattr("paledit.chat._ssh", fake_ssh)
    database = tmp_path / "chat.sqlite3"

    first = sync_chat_history(database)
    second = sync_chat_history(database)

    assert first["imported"] == 2
    assert second["imported"] == 0
    assert second["stored_count"] == 2
    assert [row["player_name"] for row in second["messages"]] == ["测试会长", "测试成员"]
    assert calls[0][-3:-1] == ["--since", "168h"]
    assert calls[1][-3:-1] == ["--since", "2026-07-13T17:33:07.000000000Z"]


def test_sync_chat_history_returns_local_messages_when_remote_is_unavailable(tmp_path: Path, monkeypatch):
    database = tmp_path / "chat.sqlite3"
    monkeypatch.setattr(
        "paledit.chat._ssh",
        lambda arguments, timeout=30: subprocess.CompletedProcess(arguments, 0, stdout=LOGS, stderr=""),
    )
    sync_chat_history(database)

    def unavailable(arguments, timeout=30):
        raise RuntimeError("palworld-server 不可用")

    monkeypatch.setattr("paledit.chat._ssh", unavailable)
    result = sync_chat_history(database)

    assert result["stored_count"] == 2
    assert result["warning"] == "palworld-server 不可用"
    assert len(result["messages"]) == 2


def test_archive_system_message_is_visible_in_local_chat_history(tmp_path: Path, monkeypatch):
    database = tmp_path / "chat.sqlite3"
    monkeypatch.setattr(
        "paledit.chat._ssh",
        lambda arguments, timeout=30: subprocess.CompletedProcess(arguments, 0, stdout="", stderr=""),
    )

    archived = archive_system_message(database, "  欢迎   来到服务器  ")
    result = sync_chat_history(database)

    assert archived["player_name"] == "系统"
    assert archived["message"] == "欢迎 来到服务器"
    assert result["messages"] == [archived]


def test_broadcast_api_archives_the_successfully_sent_message(tmp_path: Path, monkeypatch):
    database = tmp_path / "chat.sqlite3"
    monkeypatch.setattr(api, "DEFAULT_CHAT_DB", database)
    monkeypatch.setattr(
        api,
        "run_server_action",
        lambda action, **kwargs: {
            "action": action,
            "results": [{"command": "Broadcast", "response": "ok"}],
        },
    )

    result = api.server_action({
        "action": "broadcast",
        "message": "服务器维护完成",
        "confirmed": True,
    })

    assert result["archived_message"]["player_name"] == "系统"
    assert result["archived_message"]["message"] == "服务器维护完成"
