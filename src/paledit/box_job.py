from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .box_editor import apply_box_plan
from .box_plan import build_box_plan
from .remote import (
    REMOTE_DOCKER,
    SERVER_CONTAINER,
    _rcon,
    _ssh,
    get_server_status,
    list_online_players,
)
from .save import sha256
from .settings import load_settings
from .world import list_storage_containers

STATE_PATH = Path(__file__).resolve().parents[2] / ".artifacts" / "box-job-state.json"
LOCK_PATH = STATE_PATH.with_suffix(".lock")
MAINTENANCE_BACKUP_DAYS = 7
MAINTENANCE_BACKUP_MINIMUM = 3


def _target_paths() -> tuple[str, str, str, str]:
    world_id = os.environ.get("PALWORLD_WORLD_ID", "").strip()
    if not re.fullmatch(r"[0-9A-Fa-f]{32}", world_id):
        raise ValueError("必须通过 PALWORLD_WORLD_ID 配置 32 位世界 ID")
    connection = load_settings()
    remote_world = f"{connection.remote_save_root}/SaveGames/0/{world_id}"
    backup_root = f"{connection.remote_maintenance_backup_root}/box-job"
    return connection.ssh_host, world_id, remote_world, backup_root


def _result(status: str, **details: object) -> dict[str, object]:
    return {"status": status, "timestamp": datetime.now().astimezone().isoformat(), **details}


def _selected_plans(container_ids: set[str] | None = None):
    plans = tuple(
        plan for plan in build_box_plan()
        if container_ids is None or plan.container_id in container_ids
    )
    if container_ids is not None and container_ids != {plan.container_id for plan in plans}:
        missing = container_ids - {plan.container_id for plan in plans}
        raise ValueError(f"计划中不存在目标容器：{', '.join(sorted(missing))}")
    return plans


def _plan_fingerprint(container_ids: set[str] | None = None) -> str:
    payload = [(plan.container_id, plan.label, plan.items) for plan in _selected_plans(container_ids)]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _write_state(payload: dict[str, object]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, STATE_PATH)


def _rsync_from_remote(destination: Path, remote_host: str, remote_world: str) -> None:
    subprocess.run([
        "rsync", "-a", "--delete",
        "--exclude", "backup/", "--exclude", "PalEdit-Backup/",
        "--exclude", "PalEdit-Remote-Backup/",
        "-e", "ssh -o BatchMode=yes -o ConnectTimeout=10",
        f"{remote_host}:{remote_world}/", f"{destination}/",
    ], check=True, capture_output=True, text=True, timeout=180)


def _create_remote_level_backup(remote_world: str, remote_backup_root: str, world_id: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = f"{remote_backup_root}/{stamp}/{world_id}"
    _ssh(["/bin/mkdir", "-p", backup])
    _ssh(["/bin/cp", "-p", f"{remote_world}/Level.sav", f"{backup}/Level.sav"], timeout=180)
    manifest_script = (
        "import datetime,hashlib,json,os,sys,tempfile;"
        "root,source=sys.argv[1:];target=os.path.join(root,'Level.sav');"
        "digest=lambda p:hashlib.sha256(open(p,'rb').read()).hexdigest();"
        "source_sha=digest(source);backup_sha=digest(target);"
        "assert source_sha==backup_sha,'backup hash mismatch';"
        "data={'version':1,'operation':'box-job','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),"
        "'files':[{'path':'Level.sav','sha256':backup_sha,'size_bytes':os.path.getsize(target)}]};"
        "fd,tmp=tempfile.mkstemp(prefix='.manifest.',dir=root);"
        "f=os.fdopen(fd,'w');json.dump(data,f,separators=(',',':'));f.write('\\n');f.close();"
        "os.replace(tmp,os.path.join(root,'manifest.json'))"
    )
    _ssh(["python3", "-c", manifest_script, backup, f"{remote_world}/Level.sav"], timeout=30)
    return backup


def _prune_remote_level_backups(
    remote_backup_root: str,
    *,
    keep_days: int = MAINTENANCE_BACKUP_DAYS,
    minimum: int = MAINTENANCE_BACKUP_MINIMUM,
) -> dict[str, object]:
    if not remote_backup_root.endswith("/palops-backups/box-job"):
        raise ValueError("拒绝清理非 PalOps 箱子任务备份目录")
    script = (
        "import json,os,shutil,sys,time;"
        "requested=sys.argv[1];"
        "assert not os.path.islink(requested),'backup root is a symlink';"
        "root=os.path.realpath(requested);"
        "assert os.path.basename(root)=='box-job' and os.path.basename(os.path.dirname(root))=='palops-backups',"
        "'unexpected backup root';"
        "days=int(sys.argv[2]);minimum=int(sys.argv[3]);"
        "rows=[] if not os.path.isdir(root) else [(os.path.getmtime(os.path.join(root,n)),n,os.path.join(root,n)) "
        "for n in os.listdir(root) if not os.path.islink(os.path.join(root,n)) and os.path.isdir(os.path.join(root,n))];"
        "rows.sort(reverse=True);cutoff=time.time()-days*86400;deleted=[];"
        "[deleted.append(n) or shutil.rmtree(p) for m,n,p in rows[minimum:] if m<cutoff];"
        "print(json.dumps({'policy_days':days,'minimum_kept':minimum,'count_before':len(rows),"
        "'deleted':deleted,'count_after':len(rows)-len(deleted)},separators=(',',':')))"
    )
    result = _ssh(
        ["python3", "-c", script, remote_backup_root, str(keep_days), str(minimum)],
        timeout=180,
    )
    return json.loads(result.stdout)


def _rsync_level_to_remote(level_path: Path, remote_host: str, remote_temporary: str) -> None:
    subprocess.run([
        "rsync", "-a", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=10",
        str(level_path), f"{remote_host}:{remote_temporary}",
    ], check=True, capture_output=True, text=True, timeout=180)


def _verify_world(world_path: Path, container_ids: set[str] | None = None) -> dict[str, object]:
    expected = {plan.container_id: plan for plan in _selected_plans(container_ids)}
    report = list_storage_containers(world_path)
    actual = {str(row["container_id"]): row for row in report["containers"]}
    missing = sorted(set(expected) - set(actual))
    if missing:
        raise RuntimeError(f"验证缺少目标箱子：{', '.join(missing)}")
    for container_id, plan in expected.items():
        row = actual[container_id]
        slots = tuple((str(slot["item_id"]), int(slot["count"])) for slot in row["slots"])
        if slots != plan.items:
            raise RuntimeError(f"箱子验证不一致：{container_id}")
    return {
        "level_sha256": report["level_sha256"],
        "box_count": len(expected),
        "slot_count": sum(len(plan.items) for plan in expected.values()),
    }


def _wait_until_healthy(timeout: int = 180) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        last = get_server_status()
        if last["state"] == "running" and last["health"] in {"healthy", "unknown", ""}:
            return last
        time.sleep(5)
    raise RuntimeError(f"服务器启动后未恢复健康：{last}")


def preflight() -> dict[str, object]:
    _, _, remote_world, _ = _target_paths()
    state = get_server_status()
    players = list_online_players()
    level = _ssh(["/usr/bin/stat", "-f", "%z|%m", f"{remote_world}/Level.sav"]).stdout.strip()
    return _result("ready" if not players else "players_online", server=state, players=players, remote_level=level)


def run_once(*, force_with_players: bool = False, container_ids: set[str] | None = None) -> dict[str, object]:
    remote_host, world_id, remote_world, remote_backup_root = _target_paths()
    fingerprint = _plan_fingerprint(container_ids)
    if STATE_PATH.exists():
        previous = json.loads(STATE_PATH.read_text())
        if previous.get("status") == "complete" and previous.get("plan_fingerprint") == fingerprint:
            return previous
    try:
        LOCK_PATH.mkdir(parents=True)
    except FileExistsError:
        return _result("already_running")

    stopped = False
    replaced = False
    backup = ""
    remote_temporary = f"{remote_world}/.Level.sav.paledit-boxes-{os.getpid()}.tmp"
    try:
        players = list_online_players()
        if players and not force_with_players:
            return _result("players_online", players=players)
        # Close the race window immediately before the first mutating operation.
        players = list_online_players()
        if players and not force_with_players:
            return _result("players_online", players=players)

        save_response = _rcon("Save", timeout=30)
        time.sleep(3)
        _ssh([REMOTE_DOCKER, "stop", "--time", "60", SERVER_CONTAINER], timeout=90)
        stopped = True

        backup = _create_remote_level_backup(remote_world, remote_backup_root, world_id)

        with tempfile.TemporaryDirectory(prefix="paledit-box-job-") as temporary:
            world = Path(temporary) / world_id
            world.mkdir()
            _rsync_from_remote(world, remote_host, remote_world)
            before = sha256(world / "Level.sav")
            edit = apply_box_plan(world, expected_sha256=before, container_ids=container_ids)
            local_verification = _verify_world(world, container_ids)
            _rsync_level_to_remote(world / "Level.sav", remote_host, remote_temporary)
            _ssh(["/bin/mv", remote_temporary, f"{remote_world}/Level.sav"])
            replaced = True

            _ssh([REMOTE_DOCKER, "start", SERVER_CONTAINER], timeout=60)
            stopped = False
            server = _wait_until_healthy()
            time.sleep(5)
            verify_world = Path(temporary) / "verify" / world_id
            verify_world.mkdir(parents=True)
            _rsync_from_remote(verify_world, remote_host, remote_world)
            remote_verification = _verify_world(verify_world, container_ids)

        try:
            retention = _prune_remote_level_backups(remote_backup_root)
            retention_warning = None
        except Exception as error:
            retention = None
            retention_warning = str(error)

        result = _result(
            "complete", plan_fingerprint=fingerprint, backup=backup, rcon_save=save_response, edit=edit,
            local_verification=local_verification,
            remote_verification=remote_verification, server=server, retention=retention,
            retention_warning=retention_warning,
        )
        _write_state(result)
        return result
    except Exception as error:
        recovery_error = None
        try:
            if replaced and backup:
                if get_server_status().get("state") == "running":
                    _ssh([REMOTE_DOCKER, "stop", "--time", "60", SERVER_CONTAINER], timeout=90)
                    stopped = True
                _ssh(["/bin/cp", "-a", f"{backup}/Level.sav", f"{remote_world}/Level.sav"], timeout=180)
            if stopped or get_server_status().get("state") != "running":
                _ssh([REMOTE_DOCKER, "start", SERVER_CONTAINER], timeout=60)
                _wait_until_healthy()
        except Exception as recovery:
            recovery_error = str(recovery)
        failure = _result("failed", error=str(error), backup=backup or None, recovery_error=recovery_error)
        _write_state(failure)
        return failure
    finally:
        try:
            _ssh(["/bin/rm", "-f", remote_temporary])
        except Exception:
            pass
        shutil.rmtree(LOCK_PATH, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="无人时一次性应用 14 箱道具计划")
    parser.add_argument("--preflight", action="store_true", help="只读检查，不修改服务器")
    parser.add_argument("--force-with-players", action="store_true", help="已获明确授权时允许有玩家在线仍停服")
    parser.add_argument("--container-id", action="append", default=[], help="只更新指定容器，可重复传入")
    args = parser.parse_args()
    container_ids = set(args.container_id) or None
    payload = preflight() if args.preflight else run_once(
        force_with_players=args.force_with_players,
        container_ids=container_ids,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
