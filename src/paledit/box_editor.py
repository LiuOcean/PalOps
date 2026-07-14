from __future__ import annotations

import copy
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .box_plan import BoxPlan, build_box_plan
from .items import load_item_index
from .map_labels import map_custom_property
from .parser import ITEM_CONTAINER_RAW_PATH, ITEM_SLOT_RAW_PATH
from .save import sha256
from .world import guid_of, value_of

MAP_OBJECT_PATH = ".worldSaveData.MapObjectSaveData"


def _custom_properties() -> dict[str, object]:
    from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES

    return {
        MAP_OBJECT_PATH: map_custom_property(),
        ITEM_CONTAINER_RAW_PATH: PALWORLD_CUSTOM_PROPERTIES[ITEM_CONTAINER_RAW_PATH],
        ITEM_SLOT_RAW_PATH: PALWORLD_CUSTOM_PROPERTIES[ITEM_SLOT_RAW_PATH],
    }


def _open(level_path: Path):
    from palworld_save_tools.gvas import GvasFile
    from palworld_save_tools.palsav import decompress_sav_to_gvas
    from .compat import install_palworld_1_0_property_support, palworld_1_0_type_hints

    install_palworld_1_0_property_support()
    raw, save_type = decompress_sav_to_gvas(level_path.read_bytes())
    return GvasFile.read(raw, palworld_1_0_type_hints(), _custom_properties()), save_type


def _slot_template(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        slots = row["value"].get("Slots", {}).get("value", {}).get("values", [])
        if slots:
            return copy.deepcopy(slots[0])
    raise ValueError("存档中没有可复用的物品槽位结构")


def _fill_container(row: dict[str, Any], plan: BoxPlan, template: dict[str, Any]) -> None:
    slots = []
    for index, (item_id, count) in enumerate(plan.items):
        slot = copy.deepcopy(template)
        raw = slot["RawData"]["value"]
        raw["slot_index"] = index
        raw["item"]["static_id"] = item_id
        raw["count"] = count
        slots.append(slot)
    row["value"]["Slots"]["value"]["values"] = slots


def upsert_container_items(
    world_path: Path,
    container_id: str,
    items: dict[str, int],
    *,
    expected_sha256: str | None = None,
) -> dict[str, object]:
    """Set selected item stacks while preserving every other container slot."""
    from palworld_save_tools.palsav import compress_gvas_to_sav

    world_path = world_path.expanduser().resolve()
    level_path = world_path / "Level.sav"
    before_hash = sha256(level_path)
    if expected_sha256 and before_hash != expected_sha256:
        raise ValueError("Level.sav 已变化，拒绝应用旧计划")

    valid_items = {str(row["id"]) for row in load_item_index()["items"]}
    unknown = set(items) - valid_items
    if unknown:
        raise ValueError(f"Palworld 不存在道具 ID：{', '.join(sorted(unknown))}")

    gvas, _ = _open(level_path)
    rows = gvas.properties["worldSaveData"]["value"]["ItemContainerSaveData"]["value"]
    target = next((row for row in rows if guid_of(row["key"].get("ID")) == container_id), None)
    if target is None:
        raise ValueError(f"没有找到容器：{container_id}")
    slots = target["value"].get("Slots", {}).get("value", {}).get("values", [])
    if not slots:
        raise ValueError(f"容器没有可复用的槽位结构：{container_id}")
    capacity = int(value_of(target["value"].get("SlotNum"), len(slots)))
    occupied = {int(slot["RawData"]["value"]["slot_index"]) for slot in slots}
    free = [index for index in range(capacity) if index not in occupied]
    added: dict[str, int] = {}
    updated: dict[str, int] = {}
    template = slots[0]
    for item_id, requested_count in items.items():
        count = max(1, min(999999, int(requested_count)))
        existing = next(
            (slot for slot in slots if str(slot["RawData"]["value"]["item"]["static_id"]) == item_id),
            None,
        )
        if existing is not None:
            existing["RawData"]["value"]["count"] = count
            updated[item_id] = int(existing["RawData"]["value"]["slot_index"])
            continue
        if not free:
            raise ValueError(f"容器空槽不足：{container_id}")
        slot_index = free.pop(0)
        slot = copy.deepcopy(template)
        raw = slot["RawData"]["value"]
        raw["slot_index"] = slot_index
        raw["item"]["static_id"] = item_id
        raw["count"] = count
        slots.append(slot)
        added[item_id] = slot_index
    slots.sort(key=lambda slot: int(slot["RawData"]["value"]["slot_index"]))

    raw = copy.deepcopy(gvas).write(_custom_properties())
    output = compress_gvas_to_sav(raw, 0x32, True)
    temp_path = level_path.with_suffix(".sav.paledit-container.tmp")
    temp_path.write_bytes(output)
    _open(temp_path)
    os.replace(temp_path, level_path)
    return {
        "before_sha256": before_hash,
        "after_sha256": sha256(level_path),
        "container_id": container_id,
        "added_slots": added,
        "updated_slots": updated,
    }


def apply_box_plan(
    world_path: Path,
    *,
    expected_sha256: str | None = None,
    container_ids: set[str] | None = None,
) -> dict[str, object]:
    from palworld_save_tools.palsav import compress_gvas_to_sav

    world_path = world_path.expanduser().resolve()
    level_path = world_path / "Level.sav"
    before_hash = sha256(level_path)
    if expected_sha256 and before_hash != expected_sha256:
        raise ValueError("Level.sav 已变化，拒绝应用旧计划")

    plans = tuple(
        plan for plan in build_box_plan()
        if container_ids is None or plan.container_id in container_ids
    )
    if container_ids is not None:
        unknown = container_ids - {plan.container_id for plan in plans}
        if unknown:
            raise ValueError(f"计划中不存在目标容器：{', '.join(sorted(unknown))}")
    if not plans:
        raise ValueError("至少需要指定一个目标容器")
    planned = {plan.container_id for plan in plans}
    gvas, _ = _open(level_path)
    world = gvas.properties["worldSaveData"]["value"]
    rows = world["ItemContainerSaveData"]["value"]
    by_id = {guid_of(row["key"].get("ID")): row for row in rows}
    if planned - set(by_id):
        raise ValueError(f"缺少目标容器：{', '.join(sorted(planned - set(by_id)))}")

    template = _slot_template(rows)
    for plan in plans:
        _fill_container(by_id[plan.container_id], plan, template)

    raw = copy.deepcopy(gvas).write(_custom_properties())
    output = compress_gvas_to_sav(raw, 0x32, True)
    temp_path = level_path.with_suffix(".sav.paledit-boxes.tmp")
    temp_path.write_bytes(output)
    _open(temp_path)
    os.replace(temp_path, level_path)
    return {
        "before_sha256": before_hash,
        "after_sha256": sha256(level_path),
        "box_count": len(plans),
        "slot_count": sum(len(plan.items) for plan in plans),
    }


def apply_box_plan_with_backup(
    world_path: Path,
    *,
    expected_sha256: str | None = None,
    container_ids: set[str] | None = None,
) -> dict[str, object]:
    world_path = world_path.expanduser().resolve()
    backup = world_path.parent / f"{world_path.name}.before-box-plan-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copytree(world_path, backup, ignore=shutil.ignore_patterns("backup", "PalEdit-Backup"))
    result = apply_box_plan(world_path, expected_sha256=expected_sha256, container_ids=container_ids)
    result["backup_path"] = str(backup)
    return result
