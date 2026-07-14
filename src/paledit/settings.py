from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID


DEFAULT_SETTINGS_PATH = Path.cwd() / ".paledit-data" / "settings.json"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?$")


@dataclass(frozen=True)
class AppSettings:
    owner_player_uid: str = "00000000-0000-0000-0000-000000000000"
    status_refresh_seconds: int = 15
    chat_refresh_seconds: int = 5
    connection_method: str = "ssh"
    ssh_host: str = "palworld-server"
    public_access_host: str = ""
    remote_save_root: str = "/srv/palworld/Pal/Saved"
    remote_compose_path: str = "/srv/palworld/compose.yaml"
    docker_path: str = "/usr/local/bin/docker"
    container_name: str = "palworld-server"
    rcon_path: str = "/usr/bin/rcon-cli"
    rcon_port: int = 25575

    def dump(self) -> dict[str, object]:
        return asdict(self)


def _revision(settings: AppSettings) -> str:
    encoded = json.dumps(settings.dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _valid_public_host(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        labels = value.split(".")
        return len(value) <= 253 and all(_HOST_LABEL.fullmatch(label) for label in labels)


def _validated(payload: dict[str, object]) -> AppSettings:
    allowed = set(AppSettings.__dataclass_fields__)
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"未知基础设置：{', '.join(unknown)}")

    merged = AppSettings().dump()
    merged.update(payload)
    try:
        owner_player_uid = str(UUID(str(merged["owner_player_uid"]))).lower()
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("我的角色 UID 格式无效") from error

    def interval(key: str, label: str, minimum: int, maximum: int) -> int:
        try:
            value = int(merged[key])
        except (TypeError, ValueError) as error:
            raise ValueError(f"{label}必须是整数秒") from error
        if not minimum <= value <= maximum:
            raise ValueError(f"{label}必须在 {minimum}–{maximum} 秒之间")
        return value

    def absolute_path(key: str, label: str) -> str:
        value = str(merged[key]).strip()
        if not value.startswith("/") or "\n" in value or "\r" in value or len(value) > 512:
            raise ValueError(f"{label}必须是有效的绝对路径")
        return value

    ssh_host = str(merged["ssh_host"]).strip()
    public_access_host = str(merged["public_access_host"]).strip()
    container_name = str(merged["container_name"]).strip()
    if not _SAFE_NAME.fullmatch(ssh_host):
        raise ValueError("SSH 主机必须是安全的主机名或 SSH 别名")
    if public_access_host and not _valid_public_host(public_access_host):
        raise ValueError("公网访问地址必须是有效的域名或 IP，且不包含协议和端口")
    if not _SAFE_NAME.fullmatch(container_name):
        raise ValueError("容器名称格式无效")
    connection_method = str(merged["connection_method"]).strip()
    if connection_method not in {"ssh", "direct"}:
        raise ValueError("连接方式必须是 SSH 或 Docker 直连")

    try:
        rcon_port = int(merged["rcon_port"])
    except (TypeError, ValueError) as error:
        raise ValueError("RCON 端口必须是整数") from error
    if not 1 <= rcon_port <= 65535:
        raise ValueError("RCON 端口必须在 1–65535 之间")

    return AppSettings(
        owner_player_uid=owner_player_uid,
        status_refresh_seconds=interval("status_refresh_seconds", "状态刷新周期", 5, 300),
        chat_refresh_seconds=interval("chat_refresh_seconds", "聊天刷新周期", 2, 300),
        connection_method=connection_method,
        ssh_host=ssh_host,
        public_access_host=public_access_host,
        remote_save_root=absolute_path("remote_save_root", "远端存档目录"),
        remote_compose_path=absolute_path("remote_compose_path", "Compose 路径"),
        docker_path=absolute_path("docker_path", "Docker 路径"),
        container_name=container_name,
        rcon_path=absolute_path("rcon_path", "RCON 工具路径"),
        rcon_port=rcon_port,
    )


def load_settings(path: Path = DEFAULT_SETTINGS_PATH) -> AppSettings:
    if not path.exists():
        return AppSettings()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"读取基础设置失败：{error}") from error
    if not isinstance(payload, dict):
        raise ValueError("基础设置文件格式无效")
    return _validated(payload)


def settings_payload(path: Path = DEFAULT_SETTINGS_PATH) -> dict[str, object]:
    settings = load_settings(path)
    return {
        "settings": settings.dump(),
        "revision": _revision(settings),
        "storage_path": str(path.expanduser().resolve()),
        "note": "设置只保存在本机；密码、密钥和 Cookie 不会写入此文件。",
    }


def save_settings(
    updates: dict[str, object], expected_revision: str, path: Path = DEFAULT_SETTINGS_PATH,
) -> dict[str, object]:
    current = load_settings(path)
    if expected_revision != _revision(current):
        raise ValueError("基础设置已被其他操作修改，请刷新后重试")
    if not updates:
        raise ValueError("没有需要保存的基础设置")
    merged = current.dump()
    merged.update(updates)
    updated = _validated(merged)
    if updated == current:
        raise ValueError("基础设置没有发生变化")

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".settings.", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(updated.dump(), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return settings_payload(path)
