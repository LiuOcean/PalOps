import base64
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from paledit.remote import (
    _compose_environment, _parse_players, get_server_config, list_online_players, prepare_server_restart,
    pull_latest_save, restart_server, run_server_action, update_server_config,
)


COMPOSE = '''services:
  palworld-server:
    image: example
    environment:
      SERVER_NAME: "Palworld"
      SERVER_PASSWORD: "hidden"
      PLAYERS: "16"
      EXP_RATE: "3"
    volumes:
      - ./palworld:/palworld
  another-service:
    environment:
      SERVER_NAME: "not-this-one"
'''


def test_pull_latest_save_replaces_only_after_valid_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    destination = tmp_path / "Save"
    destination.mkdir()
    (destination / "old.txt").write_text("keep me")

    def fake_run(command, **kwargs):
        target = Path(command[-1])
        world = target / "0" / "WORLD"
        world.mkdir(parents=True)
        (world / "Level.sav").write_bytes(b"valid enough for mocked discovery")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("paledit.remote.subprocess.run", fake_run)
    monkeypatch.setattr("paledit.remote.discover_worlds", lambda root: [object()])

    result = pull_latest_save(destination)

    assert (destination / "SaveGames" / "0" / "WORLD" / "Level.sav").exists()
    assert not (destination / "old.txt").exists()
    assert Path(result["backup_path"]).joinpath("old.txt").read_text() == "keep me"
    assert result["world_count"] == 1


def test_pull_latest_save_excludes_rotating_backup_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured = []

    def fake_run(command, **kwargs):
        captured.append(command)
        target = Path(command[-1]) / "0" / "WORLD"
        target.mkdir(parents=True)
        (target / "Level.sav").write_bytes(b"valid enough for mocked discovery")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("paledit.remote.subprocess.run", fake_run)
    monkeypatch.setattr("paledit.remote.discover_worlds", lambda root: [object()])

    pull_latest_save(tmp_path / "Save")

    command = captured[0]
    excluded = [command[index + 1] for index, value in enumerate(command) if value == "--exclude"]
    assert excluded == ["backup/", "PalEdit-Backup/", "PalEdit-Remote-Backup/"]


def test_pull_latest_save_keeps_current_data_when_download_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    destination = tmp_path / "Save"
    destination.mkdir()
    (destination / "old.txt").write_text("keep me")

    def fake_run(command, **kwargs):
        raise subprocess.CalledProcessError(23, command, stderr="remote unavailable")

    monkeypatch.setattr("paledit.remote.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="remote unavailable"):
        pull_latest_save(destination)

    assert (destination / "old.txt").read_text() == "keep me"


def test_parse_players_uses_display_name_but_preserves_real_ids():
    output = "name,playeruid,steamid\nAlice,123456789,steam_76561198000000000\n"

    assert _parse_players(output) == [{
        "name": "Alice",
        "player_uid": "123456789",
        "steam_id": "steam_76561198000000000",
    }]


def test_online_players_expose_rest_api_locations(monkeypatch: pytest.MonkeyPatch):
    payload = {
        "players": [{
            "name": "Alice",
            "playerId": "PLAYER_UID",
            "userId": "steam_123",
            "level": 42,
            "location_x": -123.5,
            "location_y": 456.25,
        }],
    }
    completed = subprocess.CompletedProcess([], 0, stdout=json.dumps(payload), stderr="")
    monkeypatch.setattr("paledit.remote._ssh", lambda arguments: completed)

    assert list_online_players() == [{
        "name": "Alice",
        "player_uid": "PLAYER_UID",
        "steam_id": "steam_123",
        "command_id": "steam_123",
        "level": "42",
        "location_x": -123.5,
        "location_y": 456.25,
    }]


def test_safe_restart_builds_only_whitelisted_commands(monkeypatch: pytest.MonkeyPatch):
    commands = []
    monkeypatch.setattr("paledit.remote._rcon", lambda command, timeout=20: commands.append(command) or "ok")

    result = run_server_action(
        "safe_restart",
        message="服务器将在 5 分钟后重启，请尽快返回安全区域。",
        seconds=300,
    )

    assert commands == ["Save", "Shutdown 300 服务器将在 5 分钟后重启，请尽快返回安全区域。"]
    assert [row["command"] for row in result["results"]] == ["Save", "Shutdown"]


def test_player_action_rejects_an_id_not_from_online_player_list(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "paledit.remote.list_online_players",
        lambda: [{"name": "Alice", "player_uid": "known", "steam_id": "steam_known"}],
    )
    monkeypatch.setattr("paledit.remote._rcon", lambda command, timeout=20: "ok")

    with pytest.raises(ValueError, match="请选择当前在线玩家"):
        run_server_action("kick", player_uid="typed-or-forged-id")


@pytest.mark.parametrize("seconds", [1, 45, 999])
def test_shutdown_rejects_freeform_countdowns(seconds: int):
    with pytest.raises(ValueError, match="必须使用预设值"):
        run_server_action("shutdown", message="维护", seconds=seconds)


def test_server_config_hides_credentials_and_limits_to_target_service(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("paledit.remote._read_compose", lambda: COMPOSE)

    result = get_server_config()

    assert [row["key"] for row in result["settings"]] == ["SERVER_NAME", "PLAYERS", "EXP_RATE"]
    assert all("hidden" not in row["value"] for row in result["settings"])
    assert next(row for row in result["settings"] if row["key"] == "EXP_RATE")["label"] == "经验获取倍率"
    assert "经验值" in next(row for row in result["settings"] if row["key"] == "EXP_RATE")["description"]
    assert next(row for row in result["settings"] if row["key"] == "EXP_RATE")["control"] == "text"
    assert result["revision"] == hashlib.sha256(COMPOSE.encode()).hexdigest()


def test_server_config_exposes_chinese_select_options(monkeypatch: pytest.MonkeyPatch):
    compose = COMPOSE.replace(
        '      EXP_RATE: "3"\n',
        '      EXP_RATE: "3"\n      COMMUNITY: "false"\n      ARM64_DEVICE: "m1"\n'
        '      CROSSPLAY_PLATFORMS: "(Steam,Xbox,PS5,Mac)"\n      DEATH_PENALTY: "None"\n',
    )
    monkeypatch.setattr("paledit.remote._read_compose", lambda: compose)

    settings = {row["key"]: row for row in get_server_config()["settings"]}

    assert settings["COMMUNITY"]["options"] == [
        {"value": "true", "label": "开启"},
        {"value": "false", "label": "关闭"},
    ]
    assert settings["ARM64_DEVICE"]["control"] == "select"
    assert {option["label"] for option in settings["DEATH_PENALTY"]["options"]} == {
        "不掉落", "仅掉落非装备物品", "掉落物品和装备", "掉落物品、装备和全部帕鲁",
    }
    assert len(settings["CROSSPLAY_PLATFORMS"]["options"]) == 15
    assert all(option["label"] for option in settings["CROSSPLAY_PLATFORMS"]["options"])


def test_compose_environment_stops_before_next_service():
    settings, _, _ = _compose_environment(COMPOSE)

    assert settings["SERVER_NAME"]["value"] == "Palworld"
    assert settings["PLAYERS"]["value"] == "16"


def test_update_server_config_backs_up_and_writes_only_allowed_values(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("paledit.remote._read_compose", lambda: COMPOSE)
    captured = {}

    def fake_ssh(arguments, timeout=20):
        captured["arguments"] = arguments
        return subprocess.CompletedProcess(arguments, 0, stdout="/tmp/compose.backup\n", stderr="")

    monkeypatch.setattr("paledit.remote._ssh", fake_ssh)
    result = update_server_config({"EXP_RATE": "4"}, hashlib.sha256(COMPOSE.encode()).hexdigest())

    written = base64.b64decode(captured["arguments"][-1]).decode()
    assert 'EXP_RATE: "4"' in written
    assert 'SERVER_PASSWORD: "hidden"' in written
    assert result["changed"] == ["EXP_RATE"]
    assert result["restart_required"] is True


def test_update_server_config_rejects_hidden_or_unknown_keys(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("paledit.remote._read_compose", lambda: COMPOSE)

    with pytest.raises(ValueError, match="不可编辑"):
        update_server_config({"SERVER_PASSWORD": "new"}, hashlib.sha256(COMPOSE.encode()).hexdigest())


def test_update_server_config_rejects_value_outside_select_options(monkeypatch: pytest.MonkeyPatch):
    compose = COMPOSE.replace('      EXP_RATE: "3"\n', '      EXP_RATE: "3"\n      DEATH_PENALTY: "None"\n')
    monkeypatch.setattr("paledit.remote._read_compose", lambda: compose)

    with pytest.raises(ValueError, match="不在允许的选项中"):
        update_server_config({"DEATH_PENALTY": "Everything"}, hashlib.sha256(compose.encode()).hexdigest())


def test_restart_requires_a_single_use_confirmation_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("paledit.remote._rcon", lambda command, timeout=20: "Complete Save")
    monkeypatch.setattr(
        "paledit.remote._ssh",
        lambda arguments, timeout=20: subprocess.CompletedProcess(arguments, 0, stdout="running|healthy\n", stderr=""),
    )
    token = prepare_server_restart()["confirmation_token"]

    result = restart_server(token)

    assert result["saved"] is True
    assert result["status"] == "running|healthy"
    with pytest.raises(ValueError, match="确认已失效"):
        restart_server(token)
