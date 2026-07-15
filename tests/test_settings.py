import json
from pathlib import Path

import pytest

from paledit.settings import AppSettings, load_settings, save_settings, settings_payload


def test_settings_use_safe_paledit_defaults_when_file_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"

    result = settings_payload(path)

    assert result["settings"] == AppSettings().dump()
    assert result["settings"]["owner_player_uid"] == "00000000-0000-0000-0000-000000000000"
    assert result["settings"]["ssh_host"] == "palworld-server"
    assert result["settings"]["public_access_host"] == ""
    assert not path.exists()


def test_settings_are_validated_and_written_atomically(tmp_path: Path) -> None:
    path = tmp_path / ".paledit-data" / "settings.json"
    initial = settings_payload(path)

    result = save_settings(
        {
            "status_refresh_seconds": 30,
            "chat_refresh_seconds": 10,
            "ssh_host": "pal-server",
            "public_access_host": "play.example.com",
        },
        str(initial["revision"]),
        path,
    )

    assert load_settings(path).status_refresh_seconds == 30
    assert result["settings"]["ssh_host"] == "pal-server"
    assert result["settings"]["public_access_host"] == "play.example.com"
    assert json.loads(path.read_text())["chat_refresh_seconds"] == 10
    assert list(path.parent.glob(".settings.*.json")) == []


def test_settings_accept_docker_direct_connection(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    initial = settings_payload(path)

    result = save_settings(
        {
            "connection_method": "direct",
            "remote_save_root": "/srv/palworld/Pal/Saved",
            "remote_compose_path": "/srv/palworld/compose.yaml",
            "docker_path": "/usr/bin/docker",
        },
        str(initial["revision"]),
        path,
    )

    assert result["settings"]["connection_method"] == "direct"
    assert load_settings(path).remote_save_root == "/srv/palworld/Pal/Saved"


def test_settings_keep_maintenance_backups_outside_saved_tree() -> None:
    settings = AppSettings(remote_save_root="/srv/palworld/Pal/Saved")

    assert settings.remote_maintenance_backup_root == "/srv/palworld/palops-backups"


def test_settings_keep_nonstandard_save_root_backup_beside_save_tree() -> None:
    settings = AppSettings(remote_save_root="/server/palworld-saved")

    assert settings.remote_maintenance_backup_root == "/server/palops-backups"


@pytest.mark.parametrize(
    "host",
    ["play.example.com", "play.example.com:80", "192.0.2.10:8211", "2001:db8::10", "[2001:db8::10]:8211"],
)
def test_settings_accept_public_host_names_and_ip_addresses(tmp_path: Path, host: str) -> None:
    path = tmp_path / "settings.json"
    initial = settings_payload(path)

    result = save_settings({"public_access_host": host}, str(initial["revision"]), path)

    assert result["settings"]["public_access_host"] == host


def test_settings_reject_stale_revision_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"

    with pytest.raises(ValueError, match="已被其他操作修改"):
        save_settings({"status_refresh_seconds": 30}, "stale", path)

    assert not path.exists()


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"owner_player_uid": "not-a-uuid"}, "角色 UID"),
        ({"status_refresh_seconds": 1}, "5–300"),
        ({"ssh_host": "bad host"}, "SSH 主机"),
        ({"public_access_host": "https://play.example.com:8211"}, "公网访问地址"),
        ({"public_access_host": "play.example.com:0"}, "公网访问地址"),
        ({"public_access_host": "play.example.com:70000"}, "公网访问地址"),
        ({"remote_save_root": "relative/path"}, "绝对路径"),
        ({"rcon_port": 70000}, "1–65535"),
        ({"connection_method": "http"}, "SSH 或 Docker 直连"),
    ],
)
def test_settings_reject_invalid_values(tmp_path: Path, updates: dict[str, object], message: str) -> None:
    path = tmp_path / "settings.json"
    revision = str(settings_payload(path)["revision"])

    with pytest.raises(ValueError, match=message):
        save_settings(updates, revision, path)
