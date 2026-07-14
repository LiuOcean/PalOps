from __future__ import annotations

import argparse
import hashlib
import json
import os
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
    REMOTE_HOST,
    REMOTE_SAVE_ROOT,
    SERVER_CONTAINER,
    _rcon,
    _ssh,
    get_server_status,
    list_online_players,
)
from .save import sha256
from .world import list_storage_containers

WORLD_ID = "00000000000000000000000000000000"
REMOTE_WORLD = f"{REMOTE_SAVE_ROOT}/SaveGames/0/{WORLD_ID}"
REMOTE_BACKUP_ROOT = f"{REMOTE_SAVE_ROOT}/PalEdit-Remote-Backup"
STATE_PATH = Path(__file__).resolve().parents[2] / ".artifacts" / "box-job-state.json"
LOCK_PATH = STATE_PATH.with_suffix(".lock")


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


def _rsync_from_remote(destination: Path) -> None:
    subprocess.run([
        "rsync", "-a", "--delete",
        "--exclude", "backup/", "--exclude", "PalEdit-Backup/",
        "-e", "ssh -o BatchMode=yes -o ConnectTimeout=10",
        f"{REMOTE_HOST}:{REMOTE_WORLD}/", f"{destination}/",
    ], check=True, capture_output=True, text=True, timeout=180)


def _rsync_level_to_remote(level_path: Path, remote_temporary: str) -> None:
    subprocess.run([
        "rsync", "-a", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=10",
        str(level_path), f"{REMOTE_HOST}:{remote_temporary}",
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
        if row["label"] != plan.label or slots != plan.items:
            raise RuntimeError(f"箱子验证不一致：{container_id} {row['label']}")
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
    state = get_server_status()
    players = list_online_players()
    level = _ssh(["/usr/bin/stat", "-f", "%z|%m", f"{REMOTE_WORLD}/Level.sav"]).stdout.strip()
    return _result("ready" if not players else "players_online", server=state, players=players, remote_level=level)


def run_once(*, force_with_players: bool = False, container_ids: set[str] | None = None) -> dict[str, object]:
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
    remote_temporary = f"{REMOTE_WORLD}/.Level.sav.paledit-boxes-{os.getpid()}.tmp"
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

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{REMOTE_BACKUP_ROOT}/{stamp}/{WORLD_ID}"
        _ssh(["/bin/mkdir", "-p", str(Path(backup).parent)])
        _ssh(["/bin/cp", "-a", REMOTE_WORLD, backup], timeout=180)

        with tempfile.TemporaryDirectory(prefix="paledit-box-job-") as temporary:
            world = Path(temporary) / WORLD_ID
            world.mkdir()
            _rsync_from_remote(world)
            before = sha256(world / "Level.sav")
            edit = apply_box_plan(world, expected_sha256=before, container_ids=container_ids)
            local_verification = _verify_world(world, container_ids)
            _rsync_level_to_remote(world / "Level.sav", remote_temporary)
            _ssh(["/bin/mv", remote_temporary, f"{REMOTE_WORLD}/Level.sav"])
            replaced = True

            _ssh([REMOTE_DOCKER, "start", SERVER_CONTAINER], timeout=60)
            stopped = False
            server = _wait_until_healthy()
            time.sleep(5)
            verify_world = Path(temporary) / "verify" / WORLD_ID
            verify_world.mkdir(parents=True)
            _rsync_from_remote(verify_world)
            remote_verification = _verify_world(verify_world, container_ids)

        result = _result(
            "complete", plan_fingerprint=fingerprint, backup=backup, rcon_save=save_response, edit=edit,
            local_verification=local_verification,
            remote_verification=remote_verification, server=server,
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
                _ssh(["/bin/cp", "-a", f"{backup}/Level.sav", f"{REMOTE_WORLD}/Level.sav"], timeout=180)
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
