from pathlib import Path

import pytest
from fastapi import HTTPException

from paledit import api, backup_diff
from paledit.backup_diff import diff_projections, group_changes, validate_backup_pair
from paledit.backups import list_backups


def _record(
    category: str,
    entity_type: str,
    entity_id: str,
    label: str,
    fields: dict[str, object],
    *,
    important_fields: tuple[str, ...] = (),
    important_default: bool = False,
    group_id: str | None = None,
    group_label: str | None = None,
    group_entity_type: str | None = None,
) -> dict[str, object]:
    return {
        "category": category,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_label": label,
        "fields": fields,
        "important_fields": list(important_fields),
        "important_default": important_default,
        "group_id": group_id or entity_id,
        "group_label": group_label or label,
        "group_entity_type": group_entity_type or entity_type,
    }


def test_diff_projections_returns_semantic_added_modified_and_removed_rows() -> None:
    base = {"records": {
        "players:player:p1": _record(
            "players", "player", "p1", "测试玩家", {"等级": 54, "科技点": 2},
            important_fields=("等级", "科技点"), important_default=True,
        ),
        "containers:slot:c1:0": _record(
            "containers", "container_slot", "c1:0", "材料箱 · 槽位 1", {"道具": "木材", "数量": 100},
            important_fields=("道具", "数量"), important_default=True,
        ),
    }}
    target = {"records": {
        "players:player:p1": _record(
            "players", "player", "p1", "测试玩家", {"等级": 55, "科技点": 2},
            important_fields=("等级", "科技点"), important_default=True,
        ),
        "guilds:guild:g1": _record(
            "guilds", "guild", "g1", "测试公会", {"成员数量": 1},
            important_fields=("成员数量",), important_default=True,
        ),
    }}

    result = diff_projections(base, target)

    assert result["summary"] == {
        "added": 1, "modified": 1, "removed": 1, "total": 3, "important": 3, "field_total": 3,
    }
    assert result["overview"]["headline"] == "变化主要集中在玩家和储物箱"
    assert {(row["change_type"], row["field"]) for row in result["changes"]} == {
        ("added", "记录"), ("modified", "等级"), ("removed", "记录"),
    }
    assert next(row for row in result["changes"] if row["change_type"] == "modified")["after"] == "55"


def test_group_changes_collects_fields_under_their_affected_entity() -> None:
    base = {"records": {
        "players:player:p1": _record(
            "players", "player", "p1", "测试玩家", {"等级": 54, "科技点": 2},
            important_fields=("等级", "科技点"), important_default=True,
        ),
    }}
    target = {"records": {
        "players:player:p1": _record(
            "players", "player", "p1", "测试玩家", {"等级": 55, "科技点": 4},
            important_fields=("等级", "科技点"), important_default=True,
        ),
    }}

    groups = group_changes(diff_projections(base, target)["changes"])

    assert len(groups) == 1
    assert groups[0]["entity_type_label"] == "玩家"
    assert groups[0]["field_count"] == 2
    assert [change["field"] for change in groups[0]["changes"]] == ["科技点", "等级"]


def test_group_changes_rolls_child_records_up_to_their_business_object() -> None:
    base = {"records": {}}
    target = {"records": {
        "containers:container:c1": _record(
            "containers", "container", "c1", "材料箱", {"物品总数": 20},
        ),
        "containers:container_slot:c1:0": _record(
            "containers", "container_slot", "c1:0", "材料箱 · 槽位 1", {"道具": "木材", "数量": 20},
            group_id="c1", group_label="材料箱", group_entity_type="container",
        ),
    }}

    result = diff_projections(base, target)

    assert result["summary"]["total"] == 1
    groups = group_changes(result["changes"])
    assert groups[0]["entity_label"] == "材料箱"
    assert groups[0]["field_count"] == 2


def test_build_projection_exposes_each_pal_as_its_own_category_and_detects_owner_transfer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    def snapshot(owner_uid: str, level: int) -> dict[str, object]:
        users = []
        for uid, name in (("PLAYER-A", "玩家甲"), ("PLAYER-B", "玩家乙")):
            pals = []
            if uid == owner_uid:
                pals.append({
                    "instance_id": "PAL-1",
                    "character_id": "TestPal",
                    "name_zh": "测试帕鲁",
                    "nickname": "小测试",
                    "level": level,
                    "experience": 100,
                    "location_type": "帕鲁终端",
                    "container_id": "CONTAINER-1",
                    "slot_index": 0,
                    "condensation_rank": 1,
                    "rank_boosts": {"attack": 0, "defense": 0, "work_speed": 0},
                    "talents": {"hp": 90, "attack": 80, "defense": 70},
                    "passive_skills": [],
                })
            users.append({
                "player_uid": uid,
                "nickname": name,
                "level": 10,
                "pal_count": len(pals),
                "inventories": {},
                "pals": pals,
            })
        return {
            "world_id": "WORLD",
            "level_sha256": "hash",
            "summary": {},
            "users": users,
            "containers": [],
            "guilds": [],
        }

    monkeypatch.setattr(backup_diff, "world_snapshot_payload", lambda _path: snapshot("PLAYER-A", 10))
    base = backup_diff.build_projection(tmp_path, [])
    monkeypatch.setattr(backup_diff, "world_snapshot_payload", lambda _path: snapshot("PLAYER-B", 11))
    target = backup_diff.build_projection(tmp_path, [])

    pal_record = target["records"]["pals:pal:PAL-1"]
    assert pal_record["category"] == "pals"
    assert pal_record["group_entity_type"] == "pal"
    result = diff_projections(base, target)
    pal_changes = [row for row in result["changes"] if row["category"] == "pals"]
    assert {row["field"] for row in pal_changes} == {"所属玩家", "所属玩家 UID", "等级"}
    assert next(category for category in result["categories"] if category["key"] == "pals")["total"] == 1


def test_validate_backup_pair_requires_same_world_and_different_versions(tmp_path: Path) -> None:
    save_root = tmp_path / "Save"
    world = save_root / "SaveGames" / "0" / "WORLD"
    world.mkdir(parents=True)
    (world / "Level.sav").write_bytes(b"current")
    for name in ("one", "two"):
        backup = world / "PalEdit-Backup" / name
        backup.mkdir(parents=True)
        (backup / "Level.sav").write_bytes(name.encode())
    rows = list_backups(save_root, tmp_path / ".paledit-backups")["backups"]
    ids = [str(row["backup_id"]) for row in rows]

    pair = validate_backup_pair(ids[0], ids[1], "WORLD", save_root, tmp_path / ".paledit-backups")

    assert pair["world_id"] == "WORLD"
    with pytest.raises(ValueError, match="两个不同"):
        validate_backup_pair(ids[0], ids[0], "WORLD", save_root, tmp_path / ".paledit-backups")
    with pytest.raises(ValueError, match="不包含所选世界"):
        validate_backup_pair(ids[0], ids[1], "OTHER", save_root, tmp_path / ".paledit-backups")


class _FakeDiffService:
    def start(self, *args):
        return {"job_id": "job-1", "status": "running", "args": [str(value) for value in args[:3]]}

    def status(self, job_id: str):
        if job_id == "missing":
            raise KeyError("比较任务不存在或已过期")
        return {"job_id": job_id, "status": "ready"}

    def changes(self, job_id: str, **filters):
        return {"job_id": job_id, "filters": filters, "changes": []}

    def groups(self, job_id: str, **filters):
        return {"job_id": job_id, "filters": filters, "groups": []}


def test_backup_diff_api_exposes_job_status_and_filtered_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "BACKUP_DIFF_SERVICE", _FakeDiffService())
    monkeypatch.setattr(api, "_game_backup_root", lambda: None)

    created = api.create_backup_diff({
        "base_backup_id": "base", "target_backup_id": "target", "world_id": "WORLD",
    })
    status = api.backup_diff_status("job-1")
    changes = api.backup_diff_changes("job-1", category="players", change_type="modified", q="等级")
    groups = api.backup_diff_groups("job-1", category="players", change_type="modified", q="等级")

    assert created["job_id"] == "job-1"
    assert status["status"] == "ready"
    assert changes["filters"]["category"] == "players"
    assert changes["filters"]["query"] == "等级"
    assert groups["filters"]["query"] == "等级"
    with pytest.raises(HTTPException) as caught:
        api.backup_diff_status("missing")
    assert caught.value.status_code == 404
