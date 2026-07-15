from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .save import inspect_save, sha256


SOURCE_LABELS = {
    "sync": "服务器同步前快照",
    "editor": "PalOps 写入前备份",
    "game": "游戏自动备份",
    "box_plan": "批量箱子编辑备份",
}
RESTORE_IGNORE_NAMES = ("backup", "PalEdit-Backup", "PalEdit-Remote-Backup")


def _directory_stats(root: Path) -> tuple[int, int, bool]:
    total_size = 0
    file_count = 0
    has_level_save = False
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    file_count += 1
                    total_size += entry.stat(follow_symlinks=False).st_size
                    has_level_save = has_level_save or entry.name == "Level.sav"
            except OSError:
                continue
    return total_size, file_count, has_level_save


def _backup_row(path: Path, source: str, world_ids: list[str]) -> dict[str, object]:
    is_archive = path.is_file()
    if is_archive:
        size_bytes, file_count, has_level_save = path.stat().st_size, 1, False
    else:
        size_bytes, file_count, has_level_save = _directory_stats(path)
    stat = path.stat()
    normalized_world_ids = sorted(set(world_ids))
    created_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    is_restore_safety = source == "sync" and path.name.startswith("Restore-")
    protected_until = created_at + timedelta(hours=24) if is_restore_safety else None
    protected = protected_until is not None and datetime.now(timezone.utc) < protected_until
    return {
        "backup_id": f"{source}:{','.join(normalized_world_ids) or 'unknown'}:{path.name}",
        "name": path.name,
        "source": source,
        "source_label": SOURCE_LABELS[source],
        "created_at": created_at.isoformat(),
        "size_bytes": size_bytes,
        "file_count": file_count,
        "world_ids": normalized_world_ids,
        "path": str(path.resolve()),
        "is_archive": is_archive,
        "has_level_save": has_level_save,
        "is_restore_safety": is_restore_safety,
        "protected": protected,
        "protected_until": protected_until.isoformat() if protected_until else None,
        "deletable": not protected and not is_archive,
    }


def list_backups(
    save_root: Path,
    sync_backup_root: Path,
    game_backup_root: Path | None = None,
) -> dict[str, object]:
    """List fixed local backup roots without exposing restore or delete operations."""
    save_root = save_root.expanduser().resolve()
    sync_backup_root = sync_backup_root.expanduser().resolve()
    game_backup_root = game_backup_root.expanduser().resolve() if game_backup_root is not None else None
    rows: list[dict[str, object]] = []

    if sync_backup_root.is_dir():
        for snapshot in sync_backup_root.iterdir():
            if snapshot.name.startswith(".") or not snapshot.is_dir() or snapshot.is_symlink():
                continue
            worlds_root = snapshot / "SaveGames" / "0"
            world_ids = (
                [child.name for child in worlds_root.iterdir() if child.is_dir() and not child.is_symlink()]
                if worlds_root.is_dir()
                else []
            )
            rows.append(_backup_row(snapshot, "sync", world_ids))

    if game_backup_root is not None and game_backup_root.is_dir():
        for archive in game_backup_root.iterdir():
            if (
                archive.name.startswith(".")
                or archive.is_symlink()
                or not archive.is_file()
                or not archive.name.endswith((".tar.gz", ".tgz"))
            ):
                continue
            rows.append(_backup_row(archive, "game", []))

    worlds_root = save_root / "SaveGames" / "0"
    if worlds_root.is_dir():
        for world in worlds_root.iterdir():
            if not world.is_dir() or world.is_symlink():
                continue
            for source, root in (("editor", world / "PalEdit-Backup"), ("game", world / "backup" / "world")):
                if not root.is_dir():
                    continue
                for backup in root.iterdir():
                    if not backup.name.startswith(".") and backup.is_dir() and not backup.is_symlink():
                        rows.append(_backup_row(backup, source, [world.name]))
            for backup in world.parent.glob(f"{world.name}.before-box-plan-*"):
                if backup.is_dir() and not backup.is_symlink():
                    rows.append(_backup_row(backup, "box_plan", [world.name]))

    rows.sort(key=lambda row: str(row["created_at"]), reverse=True)
    counts = {source: sum(row["source"] == source for row in rows) for source in SOURCE_LABELS}
    review_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    review_rows = [
        row for row in rows
        if not row["protected"] and datetime.fromisoformat(str(row["created_at"])) < review_cutoff
    ]
    return {
        "backups": rows,
        "count": len(rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "counts": counts,
        "read_only": True,
        "retention": {
            "protected_count": sum(bool(row["protected"]) for row in rows),
            "review_after_days": 30,
            "review_count": len(review_rows),
            "review_size_bytes": sum(int(row["size_bytes"]) for row in review_rows),
        },
    }


def _safe_world_id(world_id: str) -> str:
    world_id = world_id.strip()
    if not world_id or world_id in {".", ".."} or Path(world_id).name != world_id:
        raise ValueError("无效的世界 ID")
    return world_id


def _find_backup(backup_id: str, save_root: Path, sync_backup_root: Path) -> dict[str, object]:
    for row in list_backups(save_root, sync_backup_root)["backups"]:
        if row["backup_id"] == backup_id:
            return row
    raise ValueError("备份不存在或已被移动，请重新扫描")


def _has_symlink(root: Path) -> bool:
    pending = [root]
    while pending:
        current = pending.pop()
        for entry in os.scandir(current):
            if entry.is_symlink():
                return True
            if entry.is_dir(follow_symlinks=False):
                pending.append(Path(entry.path))
    return False


def _restorable_world(
    backup_id: str, world_id: str, save_root: Path, sync_backup_root: Path,
) -> tuple[dict[str, object], Path, Path]:
    world_id = _safe_world_id(world_id)
    backup = _find_backup(backup_id, save_root, sync_backup_root)
    if world_id not in backup["world_ids"]:
        raise ValueError("所选备份不包含该世界")
    backup_path = Path(str(backup["path"]))
    source = backup_path / "SaveGames" / "0" / world_id if backup["source"] == "sync" else backup_path
    target = save_root.expanduser().resolve() / "SaveGames" / "0" / world_id
    if not source.is_dir() or source.is_symlink() or _has_symlink(source):
        raise ValueError("备份目录无效或包含符号链接，已拒绝恢复")
    if not target.is_dir() or target.is_symlink() or _has_symlink(target):
        raise ValueError("当前世界目录不存在、无效或包含符号链接")
    source_info = inspect_save(source / "Level.sav")
    if source_info.magic not in {"PlM", "PlZ"}:
        raise ValueError("备份中的 Level.sav 格式无法识别")
    return backup, source, target


def prepare_backup_restore(
    backup_id: str, world_id: str, save_root: Path, sync_backup_root: Path,
) -> dict[str, object]:
    backup, source, target = _restorable_world(backup_id, world_id, save_root, sync_backup_root)
    target_info = inspect_save(target / "Level.sav")
    if target_info.magic not in {"PlM", "PlZ"}:
        raise ValueError("当前世界的 Level.sav 格式无法识别")
    return {
        "backup_id": backup_id,
        "backup_name": backup["name"],
        "source_label": backup["source_label"],
        "world_id": world_id,
        "current_sha256": sha256(target / "Level.sav"),
        "backup_sha256": sha256(source / "Level.sav"),
        "backup_created_at": backup["created_at"],
        "backup_size_bytes": backup["size_bytes"],
        "requires_confirmation": True,
    }


def restore_backup(
    backup_id: str,
    world_id: str,
    expected_sha256: str,
    save_root: Path,
    sync_backup_root: Path,
) -> dict[str, object]:
    backup, source, target = _restorable_world(backup_id, world_id, save_root, sync_backup_root)
    before_sha256 = sha256(target / "Level.sav")
    if before_sha256 != expected_sha256:
        raise ValueError("当前 Level.sav 已变化，请重新检查备份后再恢复")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    safety_root = sync_backup_root.expanduser().resolve() / f"Restore-{stamp}"
    safety_world = safety_root / "SaveGames" / "0" / world_id
    stage = target.parent / f".{world_id}.paledit-restore-{uuid.uuid4().hex}"
    rollback = target.parent / f".{world_id}.paledit-rollback-{uuid.uuid4().hex}"
    ignore = shutil.ignore_patterns(*RESTORE_IGNORE_NAMES)
    safety_world.parent.mkdir(parents=True, exist_ok=False)
    try:
        shutil.copytree(target, safety_world, ignore=ignore)
        if sha256(safety_world / "Level.sav") != expected_sha256:
            raise ValueError("恢复前安全快照校验失败，当前世界未被替换")
        shutil.copytree(source, stage, ignore=ignore)
        backup_sha256 = sha256(source / "Level.sav")
        staged_sha256 = sha256(stage / "Level.sav")
        if staged_sha256 != backup_sha256:
            raise ValueError("备份复制校验失败，当前世界未被替换")
        staged_info = inspect_save(stage / "Level.sav")
        if staged_info.magic not in {"PlM", "PlZ"}:
            raise ValueError("临时恢复目录中的 Level.sav 格式无法识别")
        if sha256(target / "Level.sav") != expected_sha256:
            raise ValueError("恢复准备期间 Level.sav 已变化，当前世界未被替换")

        os.replace(target, rollback)
        try:
            os.replace(stage, target)
        except Exception:
            os.replace(rollback, target)
            raise
        shutil.rmtree(rollback, ignore_errors=True)
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    return {
        "backup_id": backup_id,
        "backup_name": backup["name"],
        "world_id": world_id,
        "before_sha256": before_sha256,
        "after_sha256": sha256(target / "Level.sav"),
        "safety_backup_path": str(safety_root),
        "restored": True,
    }


def delete_backup(
    backup_id: str,
    expected_created_at: str,
    expected_size_bytes: int,
    save_root: Path,
    sync_backup_root: Path,
) -> dict[str, object]:
    backup = _find_backup(backup_id, save_root, sync_backup_root)
    if backup["protected"]:
        raise ValueError(f"恢复前安全快照在 {backup['protected_until']} 前受保护")
    if backup["created_at"] != expected_created_at or int(backup["size_bytes"]) != expected_size_bytes:
        raise ValueError("备份内容或时间已变化，请重新扫描后再删除")
    path = Path(str(backup["path"]))
    if not path.is_dir() or path.is_symlink():
        raise ValueError("备份目录不存在或无效")

    quarantine = path.parent / f".{path.name}.paledit-deleting-{uuid.uuid4().hex}"
    os.replace(path, quarantine)
    try:
        shutil.rmtree(quarantine)
    except Exception:
        if quarantine.exists() and not path.exists():
            os.replace(quarantine, path)
        raise
    return {
        "backup_id": backup_id,
        "backup_name": backup["name"],
        "freed_bytes": backup["size_bytes"],
        "deleted": True,
    }
