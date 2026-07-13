from pathlib import Path

import pytest

from paledit.backups import delete_backup, list_backups, prepare_backup_restore, restore_backup
from paledit.save import sha256


def _write_world(root: Path, world_id: str, payload: bytes = b"level") -> Path:
    world = root / "SaveGames" / "0" / world_id
    world.mkdir(parents=True)
    (world / "Level.sav").write_bytes(payload)
    return world


def _save_payload(marker: bytes) -> bytes:
    return b"\0" * 8 + b"PlM" + b"\x32" + marker


def test_list_backups_combines_fixed_read_only_sources(tmp_path: Path) -> None:
    save_root = tmp_path / "Save"
    world = _write_world(save_root, "WORLD")

    sync = tmp_path / ".paledit-backups" / "Save-20260713-120000-000000"
    _write_world(sync, "WORLD", b"sync")

    editor = world / "PalEdit-Backup" / "2026-07-13_12-30-00_000000"
    editor.mkdir(parents=True)
    (editor / "Level.sav").write_bytes(b"editor")

    game = world / "backup" / "world" / "2026.07.13-13.00.00"
    game.mkdir(parents=True)
    (game / "Level.sav").write_bytes(b"game")

    box_plan = world.parent / "WORLD.before-box-plan-20260713-133000"
    box_plan.mkdir()
    (box_plan / "Level.sav").write_bytes(b"box-plan")

    result = list_backups(save_root, tmp_path / ".paledit-backups")

    assert result["count"] == 4
    assert result["counts"] == {"sync": 1, "editor": 1, "game": 1, "box_plan": 1}
    assert result["read_only"] is True
    assert result["retention"]["protected_count"] == 0
    assert {row["source"] for row in result["backups"]} == {"sync", "editor", "game", "box_plan"}
    assert all(row["world_ids"] == ["WORLD"] for row in result["backups"])
    assert all(row["has_level_save"] for row in result["backups"])
    assert result["total_size_bytes"] == len(b"sync") + len(b"editor") + len(b"game") + len(b"box-plan")


def test_list_backups_ignores_symlinked_snapshot(tmp_path: Path) -> None:
    save_root = tmp_path / "Save"
    save_root.mkdir()
    backup_root = tmp_path / ".paledit-backups"
    backup_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("do not scan")
    (backup_root / "linked").symlink_to(outside, target_is_directory=True)

    result = list_backups(save_root, backup_root)

    assert result["count"] == 0
    assert result["total_size_bytes"] == 0


def test_restore_backup_preserves_current_world_before_atomic_swap(tmp_path: Path) -> None:
    save_root = tmp_path / "Save"
    current = _write_world(save_root, "WORLD", _save_payload(b"current"))
    (current / "Players").mkdir()
    (current / "Players" / "CURRENT.sav").write_bytes(b"current-player")
    backup_root = tmp_path / ".paledit-backups"
    snapshot = backup_root / "Save-20260713-120000-000000"
    archived = _write_world(snapshot, "WORLD", _save_payload(b"archived"))
    (archived / "Players").mkdir()
    (archived / "Players" / "ARCHIVED.sav").write_bytes(b"archived-player")
    backup_id = list_backups(save_root, backup_root)["backups"][0]["backup_id"]

    prepared = prepare_backup_restore(backup_id, "WORLD", save_root, backup_root)
    result = restore_backup(backup_id, "WORLD", prepared["current_sha256"], save_root, backup_root)

    assert result["restored"] is True
    assert result["after_sha256"] == sha256(archived / "Level.sav")
    assert (current / "Players" / "ARCHIVED.sav").read_bytes() == b"archived-player"
    assert not (current / "Players" / "CURRENT.sav").exists()
    safety_world = Path(result["safety_backup_path"]) / "SaveGames" / "0" / "WORLD"
    assert sha256(safety_world / "Level.sav") == result["before_sha256"]
    assert (safety_world / "Players" / "CURRENT.sav").read_bytes() == b"current-player"


def test_restore_backup_rejects_changed_world(tmp_path: Path) -> None:
    save_root = tmp_path / "Save"
    current = _write_world(save_root, "WORLD", _save_payload(b"current"))
    backup_root = tmp_path / ".paledit-backups"
    snapshot = backup_root / "Save-20260713-120000-000000"
    _write_world(snapshot, "WORLD", _save_payload(b"archived"))
    backup_id = list_backups(save_root, backup_root)["backups"][0]["backup_id"]
    prepared = prepare_backup_restore(backup_id, "WORLD", save_root, backup_root)
    (current / "Level.sav").write_bytes(_save_payload(b"changed"))

    with pytest.raises(ValueError, match="已变化"):
        restore_backup(backup_id, "WORLD", prepared["current_sha256"], save_root, backup_root)

    assert (current / "Level.sav").read_bytes() == _save_payload(b"changed")


def test_prepare_restore_rejects_symlink_inside_backup(tmp_path: Path) -> None:
    save_root = tmp_path / "Save"
    _write_world(save_root, "WORLD", _save_payload(b"current"))
    backup_root = tmp_path / ".paledit-backups"
    snapshot = backup_root / "Save-20260713-120000-000000"
    archived = _write_world(snapshot, "WORLD", _save_payload(b"archived"))
    outside = tmp_path / "outside"
    outside.mkdir()
    (archived / "linked").symlink_to(outside, target_is_directory=True)
    backup_id = list_backups(save_root, backup_root)["backups"][0]["backup_id"]

    with pytest.raises(ValueError, match="符号链接"):
        prepare_backup_restore(backup_id, "WORLD", save_root, backup_root)


def test_delete_backup_requires_unchanged_scan_metadata(tmp_path: Path) -> None:
    save_root = tmp_path / "Save"
    _write_world(save_root, "WORLD", _save_payload(b"current"))
    backup_root = tmp_path / ".paledit-backups"
    snapshot = backup_root / "Save-20260713-120000-000000"
    archived = _write_world(snapshot, "WORLD", _save_payload(b"archived"))
    backup = list_backups(save_root, backup_root)["backups"][0]
    (archived / "extra.bin").write_bytes(b"changed-after-scan")

    with pytest.raises(ValueError, match="已变化"):
        delete_backup(
            str(backup["backup_id"]), str(backup["created_at"]), int(backup["size_bytes"]), save_root, backup_root,
        )

    assert snapshot.is_dir()


def test_delete_backup_removes_only_selected_snapshot(tmp_path: Path) -> None:
    save_root = tmp_path / "Save"
    current = _write_world(save_root, "WORLD", _save_payload(b"current"))
    backup_root = tmp_path / ".paledit-backups"
    snapshot = backup_root / "Save-20260713-120000-000000"
    _write_world(snapshot, "WORLD", _save_payload(b"archived"))
    backup = list_backups(save_root, backup_root)["backups"][0]

    result = delete_backup(
        str(backup["backup_id"]), str(backup["created_at"]), int(backup["size_bytes"]), save_root, backup_root,
    )

    assert result["deleted"] is True
    assert result["freed_bytes"] == backup["size_bytes"]
    assert not snapshot.exists()
    assert current.is_dir()


def test_recent_restore_safety_snapshot_is_protected_from_delete(tmp_path: Path) -> None:
    save_root = tmp_path / "Save"
    _write_world(save_root, "WORLD", _save_payload(b"current"))
    backup_root = tmp_path / ".paledit-backups"
    snapshot = backup_root / "Restore-20260713-120000-000000"
    _write_world(snapshot, "WORLD", _save_payload(b"safety"))
    backup = list_backups(save_root, backup_root)["backups"][0]

    assert backup["protected"] is True
    with pytest.raises(ValueError, match="受保护"):
        delete_backup(
            str(backup["backup_id"]), str(backup["created_at"]), int(backup["size_bytes"]), save_root, backup_root,
        )

    assert snapshot.is_dir()
