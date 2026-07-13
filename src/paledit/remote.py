from __future__ import annotations

import shutil
import shlex
import subprocess
import json
import base64
import hashlib
import re
import secrets
import time
from datetime import datetime
from itertools import combinations
from pathlib import Path

from .save import InvalidSaveError, discover_worlds


REMOTE_HOST = "palworld-server"
REMOTE_SAVE_ROOT = "/srv/palworld/Pal/Saved"
REMOTE_DOCKER = "/usr/local/bin/docker"
SERVER_CONTAINER = "palworld-server"
RCON_BIN = "/usr/bin/rcon-cli"
REMOTE_COMPOSE = "/srv/palworld/compose.yaml"
_RESTART_TOKENS: dict[str, float] = {}
_RESTART_TOKEN_TTL = 120
_ENV_LINE = re.compile(r'^(?P<indent>\s+)(?P<key>[A-Z][A-Z0-9_]*):\s*(?P<value>.*?)(?P<newline>\r?\n)?$')
_SENSITIVE_MARKERS = ("PASSWORD", "TOKEN", "SECRET", "PRIVATE", "CREDENTIAL", "API_KEY")
_SETTING_METADATA = {
    "PUID": ("容器用户 ID", "服务器进程写入文件时使用的宿主机用户编号。通常不需要修改。"),
    "PGID": ("容器用户组 ID", "服务器进程写入文件时使用的宿主机用户组编号。通常不需要修改。"),
    "TZ": ("服务器时区", "影响日志时间、定时备份和计划任务的执行时间。"),
    "PORT": ("游戏端口", "玩家连接 Palworld 服务器所使用的 UDP 端口。"),
    "QUERY_PORT": ("服务器查询端口", "供服务器列表和状态查询使用的 UDP 端口。"),
    "PLAYERS": ("最大玩家数", "允许同时进入服务器的玩家人数上限。"),
    "SERVER_NAME": ("服务器名称", "玩家在服务器列表和连接信息中看到的名称。"),
    "SERVER_DESCRIPTION": ("服务器说明", "展示给玩家的服务器简介。"),
    "COMMUNITY": ("公开社区服务器", "是否把服务器作为公开社区服务器发布。"),
    "MULTITHREADING": ("多线程网络处理", "启用服务器的多线程网络相关处理；修改前应确认宿主机与游戏版本兼容。"),
    "UPDATE_ON_BOOT": ("启动时自动更新", "每次容器启动时检查并安装 Palworld 服务端更新。"),
    "USE_DEPOT_DOWNLOADER": ("使用 DepotDownloader 更新", "使用 DepotDownloader 获取服务端文件，常用于 ARM64 主机兼容。"),
    "BACKUP_ENABLED": ("自动备份", "是否启用服务器镜像内置的定时存档备份。"),
    "BACKUP_CRON_EXPRESSION": ("备份计划", "使用 Cron 表达式指定自动备份时间。"),
    "DELETE_OLD_BACKUPS": ("清理过期备份", "是否自动删除超过保留期限的旧备份。"),
    "OLD_BACKUP_DAYS": ("备份保留天数", "自动备份在服务器上保留的天数。"),
    "REST_API_ENABLED": ("管理 API", "是否启用 Palworld 官方 REST 管理接口。"),
    "REST_API_PORT": ("管理 API 端口", "官方 REST 管理接口监听的 TCP 端口。"),
    "RCON_ENABLED": ("远程管理控制台", "是否启用 RCON，以便保存世界、广播和管理玩家。"),
    "RCON_PORT": ("RCON 端口", "远程管理控制台监听的 TCP 端口。"),
    "ARM64_DEVICE": ("ARM64 设备模式", "为 Apple Silicon 等 ARM64 宿主机选择兼容运行模式。"),
    "CROSSPLAY_PLATFORMS": ("跨平台范围", "允许连接服务器的平台组合，例如 Steam、Xbox、PS5 和 Mac。"),
    "ALLOW_GLOBAL_PALBOX_EXPORT": ("允许导出全局帕鲁终端", "允许玩家把帕鲁导出到全局帕鲁终端。"),
    "ALLOW_GLOBAL_PALBOX_IMPORT": ("允许导入全局帕鲁终端", "允许玩家从全局帕鲁终端导入帕鲁。"),
    "DEATH_PENALTY": ("死亡惩罚", "决定玩家死亡后掉落哪些物品、装备或帕鲁。None 表示不掉落。"),
    "BUILD_OBJECT_DAMAGE_RATE": ("建筑受到的伤害倍率", "控制建筑被攻击时承受的伤害；越低越耐打。"),
    "BUILD_OBJECT_DETERIORATION_DAMAGE_RATE": ("建筑自然劣化倍率", "控制据点范围外建筑随时间损坏的速度；0 表示关闭自然劣化。"),
    "BASE_CAMP_MAX_NUM_IN_GUILD": ("每个公会据点上限", "一个公会最多可以同时拥有的据点数量。"),
    "BASE_CAMP_WORKER_MAX_NUM": ("单据点工作帕鲁上限", "每个据点最多可部署的工作帕鲁数量。"),
    "COLLECTION_DROP_RATE": ("采集掉落倍率", "控制采矿、伐木和采集获得的资源数量。"),
    "ENEMY_DROP_ITEM_RATE": ("敌人掉落倍率", "控制击败帕鲁或敌人后获得的物品数量。"),
    "EXP_RATE": ("经验获取倍率", "控制玩家和帕鲁获得经验值的速度。"),
    "NIGHTTIME_SPEEDRATE": ("夜晚流逝速度", "控制游戏内夜晚时间经过的速度；数值越高夜晚越短。"),
    "PAL_EGG_DEFAULT_HATCHING_TIME": ("帕鲁蛋孵化时间", "控制大型帕鲁蛋的基础孵化小时数；越低孵化越快。"),
    "PAL_STAMINA_DECREASE_RATE": ("帕鲁耐力消耗倍率", "控制帕鲁行动时耐力下降速度；越低越耐久。"),
    "PAL_STOMACH_DECREASE_RATE": ("帕鲁饱食度消耗倍率", "控制帕鲁饥饿速度；越低越不容易饿。"),
    "PLAYER_AUTO_HP_REGEN_RATE": ("玩家生命恢复倍率", "控制玩家非睡眠状态下的自动生命恢复速度。"),
    "PLAYER_STAMINA_DECREASE_RATE": ("玩家耐力消耗倍率", "控制奔跑、攀爬等行为的耐力消耗速度。"),
    "PLAYER_STOMACH_DECREASE_RATE": ("玩家饱食度消耗倍率", "控制玩家饥饿速度；越低越不容易饿。"),
    "ITEM_WEIGHT_RATE": ("物品重量倍率", "统一调整物品对负重的影响；越低物品越轻。"),
    "EQUIPMENT_DURABILITY_DAMAGE_RATE": ("装备耐久损耗倍率", "控制武器与防具耐久度下降速度；越低越耐用。"),
    "ITEM_CONTAINER_FORCE_MARK_DIRTY_INTERVAL": ("容器强制保存间隔", "定期把箱子等物品容器标记为已变更，降低异常退出时丢失更新的风险。"),
    "ITEM_CORRUPTION_MULTIPLIER": ("食物腐败速度倍率", "控制食物腐败速度；0 表示食物不会因时间腐败。"),
}

_BOOLEAN_SETTING_KEYS = {
    "COMMUNITY",
    "MULTITHREADING",
    "UPDATE_ON_BOOT",
    "USE_DEPOT_DOWNLOADER",
    "BACKUP_ENABLED",
    "DELETE_OLD_BACKUPS",
    "REST_API_ENABLED",
    "RCON_ENABLED",
    "ALLOW_GLOBAL_PALBOX_EXPORT",
    "ALLOW_GLOBAL_PALBOX_IMPORT",
}

_PLATFORM_LABELS = (
    ("Steam", "电脑平台"),
    ("Xbox", "微软主机"),
    ("PS5", "索尼主机"),
    ("Mac", "苹果电脑"),
)


def _crossplay_options() -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            f"({','.join(value for value, _ in selected)})",
            "、".join(label for _, label in selected),
        )
        for size in range(1, len(_PLATFORM_LABELS) + 1)
        for selected in combinations(_PLATFORM_LABELS, size)
    )


_SETTING_OPTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    **{key: (("true", "开启"), ("false", "关闭")) for key in _BOOLEAN_SETTING_KEYS},
    "ARM64_DEVICE": (
        ("generic", "通用设备"),
        ("m1", "苹果芯片设备"),
        ("rpi5", "树莓派 5"),
        ("adlink", "凌华设备"),
    ),
    "CROSSPLAY_PLATFORMS": _crossplay_options(),
    "DEATH_PENALTY": (
        ("None", "不掉落"),
        ("Item", "仅掉落非装备物品"),
        ("ItemAndEquipment", "掉落物品和装备"),
        ("All", "掉落物品、装备和全部帕鲁"),
    ),
}


def _ssh(arguments: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    remote_command = shlex.join(arguments)
    try:
        return subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", REMOTE_HOST, remote_command],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("连接 palworld-server 超时") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        raise RuntimeError(f"palworld-server 操作失败：{detail}") from error


def _rcon(command: str, timeout: int = 20) -> str:
    result = _ssh(
        [REMOTE_DOCKER, "exec", SERVER_CONTAINER, RCON_BIN, command],
        timeout=timeout,
    )
    return result.stdout.strip()


def _read_compose() -> str:
    return _ssh(["cat", REMOTE_COMPOSE]).stdout


def _decode_yaml_scalar(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return str(json.loads(value))
        except ValueError:
            pass
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _compose_environment(text: str) -> tuple[dict[str, dict[str, object]], int, int]:
    lines = text.splitlines(keepends=True)
    service_start = next((i for i, line in enumerate(lines) if re.match(r'^  palworld-server:\s*$', line.rstrip())), -1)
    if service_start < 0:
        raise RuntimeError("compose.yaml 中未找到 palworld-server 服务")
    service_end = next((i for i in range(service_start + 1, len(lines)) if re.match(r'^  [^\s#][^:]*:\s*$', lines[i].rstrip())), len(lines))
    env_start = next((i for i in range(service_start + 1, service_end) if re.match(r'^    environment:\s*$', lines[i].rstrip())), -1)
    if env_start < 0:
        raise RuntimeError("compose.yaml 中未找到 palworld-server.environment")
    env_end = next((i for i in range(env_start + 1, service_end) if lines[i].strip() and not lines[i].startswith("      ")), service_end)
    settings: dict[str, dict[str, object]] = {}
    for index in range(env_start + 1, env_end):
        match = _ENV_LINE.match(lines[index])
        if not match or match.group("indent") != "      ":
            continue
        key = match.group("key")
        if any(marker in key for marker in _SENSITIVE_MARKERS):
            continue
        settings[key] = {"value": _decode_yaml_scalar(match.group("value")), "line": index}
    return settings, env_start, env_end


def _setting_category(key: str) -> str:
    if key in {"SERVER_NAME", "SERVER_DESCRIPTION", "PLAYERS", "COMMUNITY", "CROSSPLAY_PLATFORMS"}:
        return "基础"
    if any(word in key for word in ("RATE", "DAMAGE", "DEATH", "HATCH", "STAMINA", "STOMACH", "CORRUPTION")):
        return "游戏倍率"
    if any(word in key for word in ("BASE_CAMP", "GUILD", "PALBOX")):
        return "据点与公会"
    if any(word in key for word in ("BACKUP", "UPDATE", "DEPOT")):
        return "维护"
    if any(word in key for word in ("PORT", "RCON", "REST_API")):
        return "连接"
    return "其他"


def _setting_metadata(key: str) -> tuple[str, str]:
    return _SETTING_METADATA.get(key, (key.replace("_", " ").title(), "该参数由当前服务器镜像提供；修改后需重启才能应用。"))


def _setting_options(key: str) -> list[dict[str, str]] | None:
    options = _SETTING_OPTIONS.get(key)
    if options is None:
        return None
    return [{"value": value, "label": label} for value, label in options]


def get_server_config() -> dict[str, object]:
    text = _read_compose()
    settings, _, _ = _compose_environment(text)
    return {
        "host": REMOTE_HOST,
        "path": REMOTE_COMPOSE,
        "revision": hashlib.sha256(text.encode()).hexdigest(),
        "settings": [
            {
                "key": key,
                "label": _setting_metadata(key)[0],
                "description": _setting_metadata(key)[1],
                "value": row["value"],
                "category": _setting_category(key),
                "control": "select" if key in _SETTING_OPTIONS else "text",
                "options": _setting_options(key),
            }
            for key, row in settings.items()
        ],
        "note": "密码及凭据字段已隐藏；保存目标为 Compose，INI 会在重启后重新生成。",
    }


def update_server_config(updates: dict[str, object], expected_revision: str) -> dict[str, object]:
    text = _read_compose()
    revision = hashlib.sha256(text.encode()).hexdigest()
    if revision != expected_revision:
        raise ValueError("服务器配置已被其他操作修改，请刷新后重试")
    settings, _, _ = _compose_environment(text)
    if not updates:
        raise ValueError("没有需要保存的配置变更")
    unknown = sorted(set(updates) - set(settings))
    if unknown:
        raise ValueError(f"配置项不可编辑：{', '.join(unknown)}")

    lines = text.splitlines(keepends=True)
    changed: list[str] = []
    for key, raw_value in updates.items():
        value = str(raw_value).strip()
        if not value or len(value) > 256 or "\n" in value or "\r" in value:
            raise ValueError(f"{key} 的值为空、过长或包含换行")
        allowed_options = _SETTING_OPTIONS.get(key)
        if allowed_options is not None and value not in {option[0] for option in allowed_options}:
            raise ValueError(f"{key} 的值不在允许的选项中")
        if value == settings[key]["value"]:
            continue
        index = int(settings[key]["line"])
        newline = "\n" if lines[index].endswith("\n") else ""
        lines[index] = f"      {key}: {json.dumps(value, ensure_ascii=False)}{newline}"
        changed.append(key)
    if not changed:
        raise ValueError("配置没有发生变化")

    new_text = "".join(lines)
    encoded = base64.b64encode(new_text.encode()).decode()
    script = (
        "import base64,hashlib,os,shutil,sys,tempfile,time;"
        "p,e,d=sys.argv[1:];b=open(p,'rb').read();"
        "assert hashlib.sha256(b).hexdigest()==e,'配置已变化';"
        "backup=p+'.paledit-'+time.strftime('%Y%m%d-%H%M%S')+'.bak';shutil.copy2(p,backup);"
        "fd,tmp=tempfile.mkstemp(prefix='.compose.',dir=os.path.dirname(p));f=os.fdopen(fd,'wb');"
        "f.write(base64.b64decode(d));f.close();os.chmod(tmp,os.stat(p).st_mode);os.replace(tmp,p);print(backup)"
    )
    result = _ssh(["python3", "-c", script, REMOTE_COMPOSE, revision, encoded], timeout=30)
    return {
        "changed": changed,
        "backup_path": result.stdout.strip(),
        "revision": hashlib.sha256(new_text.encode()).hexdigest(),
        "restart_required": True,
    }


def prepare_server_restart() -> dict[str, object]:
    now = time.time()
    for token, expiry in list(_RESTART_TOKENS.items()):
        if expiry <= now:
            _RESTART_TOKENS.pop(token, None)
    token = secrets.token_urlsafe(24)
    _RESTART_TOKENS[token] = now + _RESTART_TOKEN_TTL
    return {"confirmation_token": token, "expires_in": _RESTART_TOKEN_TTL}


def restart_server(confirmation_token: str) -> dict[str, object]:
    expiry = _RESTART_TOKENS.pop(confirmation_token, None)
    if expiry is None or expiry <= time.time():
        raise ValueError("重启确认已失效，请重新发起并再次确认")
    save_response = _rcon("Save", timeout=30)
    script = (
        f"{shlex.quote(REMOTE_DOCKER)} compose -f {shlex.quote(REMOTE_COMPOSE)} restart {SERVER_CONTAINER} >/dev/null && "
        f"i=0; while [ $i -lt 45 ]; do s=$({shlex.quote(REMOTE_DOCKER)} inspect {SERVER_CONTAINER} "
        "--format '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null || true); "
        "[ \"$s\" = 'running|healthy' ] && { echo \"$s\"; exit 0; }; i=$((i+1)); sleep 2; done; echo \"$s\"; exit 1"
    )
    result = _ssh(["sh", "-lc", script], timeout=110)
    return {"saved": True, "save_response": save_response, "status": result.stdout.strip(), "restarted": True}


def get_server_status() -> dict[str, object]:
    result = _ssh([
        REMOTE_DOCKER, "inspect", SERVER_CONTAINER,
        "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.State.StartedAt}}|{{.HostConfig.RestartPolicy.Name}}",
    ])
    values = result.stdout.strip().split("|", 3)
    if len(values) != 4:
        raise RuntimeError("无法解析 palworld-server 容器状态")
    state, health, started_at, restart_policy = values
    return {
        "host": REMOTE_HOST,
        "container": SERVER_CONTAINER,
        "state": state,
        "health": health or "unknown",
        "started_at": started_at,
        "restart_policy": restart_policy,
        "online": state == "running" and health in {"healthy", "unknown", ""},
        "rcon_enabled": True,
    }


def _parse_players(output: str) -> list[dict[str, str]]:
    players: list[dict[str, str]] = []
    for line in output.splitlines():
        line = line.strip().lstrip("/")
        if not line or line.lower().startswith("name,playeruid,steamid"):
            continue
        parts = [part.strip() for part in line.split(",", 2)]
        if len(parts) != 3 or not parts[1]:
            continue
        players.append({"name": parts[0] or "未命名玩家", "player_uid": parts[1], "steam_id": parts[2]})
    return players


def list_online_players() -> list[dict[str, str]]:
    result = _ssh([
        REMOTE_DOCKER, "exec", SERVER_CONTAINER, "sh", "-lc",
        'curl -fsS --max-time 10 -u "admin:$ADMIN_PASSWORD" http://127.0.0.1:8212/v1/api/players',
    ])
    try:
        payload = json.loads(result.stdout)
        return [{
            "name": str(player.get("name") or "未命名玩家"),
            "player_uid": str(player.get("playerId") or ""),
            "steam_id": str(player.get("userId") or ""),
            "command_id": str(player.get("userId") or ""),
            "level": str(player.get("level") or ""),
        } for player in payload.get("players", []) if player.get("userId")]
    except (TypeError, ValueError) as error:
        raise RuntimeError("无法解析 palworld-server 在线玩家列表") from error


def run_server_action(
    action: str,
    *,
    message: str | None = None,
    seconds: int | None = None,
    player_uid: str | None = None,
) -> dict[str, object]:
    allowed_actions = {"save", "broadcast", "kick", "ban", "shutdown", "safe_restart"}
    if action not in allowed_actions:
        raise ValueError("不支持的服务器操作")

    clean_message = " ".join((message or "").split()).strip()
    if len(clean_message) > 200:
        raise ValueError("广播内容不能超过 200 个字符")
    if action in {"broadcast", "shutdown", "safe_restart"} and not clean_message:
        raise ValueError("请选择预设消息或填写广播内容")

    countdown = 0 if seconds is None else int(seconds)
    if action in {"shutdown", "safe_restart"} and countdown not in {30, 60, 120, 300, 600}:
        raise ValueError("关服倒计时必须使用预设值")

    if action in {"kick", "ban"}:
        online = {player.get("command_id", player["player_uid"]) for player in list_online_players()}
        if not player_uid or player_uid not in online:
            raise ValueError("请选择当前在线玩家")

    commands: list[str]
    if action == "save":
        commands = ["Save"]
    elif action == "broadcast":
        commands = [f"Broadcast {clean_message}"]
    elif action == "kick":
        commands = [f"KickPlayer {player_uid}"]
    elif action == "ban":
        commands = [f"BanPlayer {player_uid}"]
    elif action == "shutdown":
        commands = [f"Shutdown {countdown} {clean_message}"]
    else:
        commands = ["Save", f"Shutdown {countdown} {clean_message}"]

    results = [{"command": command.split(" ", 1)[0], "response": _rcon(command, timeout=30)} for command in commands]
    return {"action": action, "results": results}


def pull_latest_save(destination: Path) -> dict[str, object]:
    destination = destination.expanduser().resolve()
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".{destination.name}.pulling"
    backup = parent / ".paledit-backups" / datetime.now().strftime("Save-%Y%m%d-%H%M%S-%f")

    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        subprocess.run(
            [
                "rsync", "-a", "--delete",
                "--exclude", "backup/",
                "--exclude", "PalEdit-Backup/",
                "--exclude", "PalEdit-Remote-Backup/",
                "-e", "ssh -o BatchMode=yes -o ConnectTimeout=10",
                f"{REMOTE_HOST}:{REMOTE_SAVE_ROOT}/SaveGames/",
                str(staging / "SaveGames") + "/",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        worlds = discover_worlds(staging)
        if not worlds:
            raise InvalidSaveError("远端数据中没有发现 Level.sav，已保留当前本地存档")

        replaced = destination.exists()
        if replaced:
            backup.parent.mkdir(parents=True, exist_ok=True)
            destination.rename(backup)
        try:
            staging.rename(destination)
        except Exception:
            if replaced and backup.exists() and not destination.exists():
                backup.rename(destination)
            raise
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("从 palworld-server 拉取存档超时，已保留当前本地存档") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        raise RuntimeError(f"从 palworld-server 拉取失败：{detail}") from error
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return {
        "source": f"{REMOTE_HOST}:{REMOTE_SAVE_ROOT}/SaveGames",
        "destination": str(destination),
        "world_count": len(worlds),
        "backup_path": str(backup) if replaced else None,
    }
