from __future__ import annotations

import copy
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .pals import load_pal_index
from .items import load_item_index
from .parser import character_custom_properties, open_world
from .save import sha256


def value_of(prop: Any, default: Any = None) -> Any:
    if prop is None:
        return default
    value = prop
    while isinstance(value, dict) and "value" in value:
        value = value["value"]
    return value


def set_value(prop: dict[str, Any], value: Any) -> None:
    target = prop
    while isinstance(target.get("value"), dict) and "value" in target["value"]:
        target = target["value"]
    target["value"] = value


def guid_of(prop: dict[str, Any] | None) -> str:
    return str(value_of(prop, "00000000-0000-0000-0000-000000000000"))


def stat_value(prop: dict[str, Any] | None) -> int | float:
    value = value_of(prop, 0)
    if isinstance(value, dict) and "Value" in value:
        value = value_of(value["Value"], 0)
    if isinstance(prop, dict) and prop.get("struct_type") == "FixedPoint64":
        return round(float(value) / 1000, 3)
    return value


def parameter_of(entity: dict[str, Any]) -> dict[str, Any]:
    return entity["value"]["RawData"]["value"]["object"]["SaveParameter"]["value"]


def player_inventory_ids(world_path: Path, player_uid: str) -> dict[str, str]:
    from palworld_save_tools.gvas import GvasFile
    from palworld_save_tools.palsav import decompress_sav_to_gvas
    from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS

    filename = f"{player_uid.split('-')[0].upper()}000000000000000000000000.sav"
    raw, _ = decompress_sav_to_gvas((world_path / "Players" / filename).read_bytes())
    save = GvasFile.read(raw, PALWORLD_TYPE_HINTS, {}).properties["SaveData"]["value"]
    info = save["InventoryInfo"]["value"]
    labels = {
        "CommonContainerId": "背包",
        "EssentialContainerId": "重要物品",
        "WeaponLoadOutContainerId": "武器装备",
        "PlayerEquipArmorContainerId": "防具装备",
        "FoodEquipContainerId": "食物装备",
    }
    return {label: guid_of(info[key]["value"]["ID"]) for key, label in labels.items() if key in info}


def inventory_containers(gvas: Any) -> dict[str, list[dict[str, object]]]:
    item_names = {row["id"]: row["name_zh"] for row in load_item_index()["items"]}
    rows = gvas.properties["worldSaveData"]["value"]["ItemContainerSaveData"]["value"]
    result: dict[str, list[dict[str, object]]] = {}
    for container in rows:
        container_id = guid_of(container["key"].get("ID"))
        slots = container["value"].get("Slots", {}).get("value", {}).get("values", [])
        result[container_id] = []
        for slot in slots:
            raw = slot["RawData"]["value"]
            item_id = str(raw["item"]["static_id"])
            result[container_id].append({
                "slot_index": int(raw["slot_index"]),
                "item_id": item_id,
                "name_zh": item_names.get(item_id, item_id),
                "count": int(raw["count"]),
            })
    return result


def status_points(prop: dict[str, Any] | None) -> dict[str, int]:
    labels = {
        "EPalStatusPointType::MaxHP": "生命值",
        "EPalStatusPointType::MaxSP": "体力",
        "EPalStatusPointType::Attack": "攻击",
        "EPalStatusPointType::CarryWeight": "负重",
        "EPalStatusPointType::CaptureRate": "捕获力",
        "EPalStatusPointType::WorkSpeed": "工作速度",
    }
    raw = value_of(prop, {})
    values = raw.get("values", []) if isinstance(raw, dict) else []
    result: dict[str, int] = {}
    for row in values:
        status = value_of(row.get("StatusName"), "")
        result[labels.get(status, status)] = int(value_of(row.get("StatusPoint"), 0))
    return result


def list_users(world_path: Path) -> dict[str, object]:
    world_path = world_path.expanduser().resolve()
    gvas, _ = open_world(world_path / "Level.sav")
    entities = gvas.properties["worldSaveData"]["value"]["CharacterSaveParameterMap"]["value"]
    pal_names = {row["character_id"]: row["name_zh"] for row in load_pal_index()["pals"]}
    containers = inventory_containers(gvas)
    users: dict[str, dict[str, object]] = {}
    pals_by_owner: dict[str, list[dict[str, object]]] = {}
    for entity in entities:
        param = parameter_of(entity)
        player_uid = guid_of(entity["key"].get("PlayerUId"))
        instance_id = guid_of(entity["key"].get("InstanceId"))
        if bool(value_of(param.get("IsPlayer"), False)):
            users[player_uid] = {
                "player_uid": player_uid,
                "instance_id": instance_id,
                "player_file": f"Players/{player_uid.split('-')[0].upper()}000000000000000000000000.sav",
                "nickname": value_of(param.get("NickName"), ""),
                "level": int(value_of(param.get("Level"), 1)),
                "experience": int(value_of(param.get("Exp"), 0)),
                "hp": stat_value(param.get("Hp")),
                "shield_hp": stat_value(param.get("ShieldHP")),
                "satiety": round(float(value_of(param.get("FullStomach"), 0)), 2),
                "unused_status_points": int(value_of(param.get("UnusedStatusPoint"), 0)),
                "status_points": status_points(param.get("GotStatusPointList")),
                "extra_status_points": status_points(param.get("GotExStatusPointList")),
                "voice_id": int(value_of(param.get("VoiceID"), 0)),
                "pals": [],
                "inventories": {},
            }
        else:
            owner = guid_of(param.get("OwnerPlayerUId"))
            if owner == "00000000-0000-0000-0000-000000000000":
                continue
            character_id = str(value_of(param.get("CharacterID"), ""))
            pals_by_owner.setdefault(owner, []).append({
                "instance_id": instance_id,
                "character_id": character_id,
                "name_zh": pal_names.get(character_id, character_id),
                "nickname": value_of(param.get("NickName"), ""),
                "level": int(value_of(param.get("Level"), 1)),
                "experience": int(value_of(param.get("Exp"), 0)),
                "gender": value_of(param.get("Gender"), ""),
                "is_boss": bool(value_of(param.get("IsBoss"), False)),
                "is_lucky": bool(value_of(param.get("IsRarePal"), False)),
            })
    for uid, user in users.items():
        user["pals"] = sorted(pals_by_owner.get(uid, []), key=lambda pal: (str(pal["name_zh"]), str(pal["instance_id"])))
        user["pal_count"] = len(user["pals"])
        try:
            ids = player_inventory_ids(world_path, uid)
            user["inventories"] = {label: containers.get(container_id, []) for label, container_id in ids.items()}
            user["inventory_container_ids"] = ids
        except (FileNotFoundError, KeyError):
            user["inventories"] = {}
    return {"world_id": world_path.name, "level_sha256": sha256(world_path / "Level.sav"), "users": list(users.values())}


def _write_world(world_path: Path, gvas: Any) -> Path:
    from palworld_save_tools.palsav import compress_gvas_to_sav

    level_path = world_path / "Level.sav"
    backup_root = world_path / "PalEdit-Backup" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    shutil.copytree(world_path, backup_root, ignore=shutil.ignore_patterns("backup", "PalEdit-Backup"))
    raw = copy.deepcopy(gvas).write(character_custom_properties())
    output = compress_gvas_to_sav(raw, 0x32, True)
    temp_path = level_path.with_suffix(".sav.paledit.tmp")
    temp_path.write_bytes(output)
    open_world(temp_path)
    os.replace(temp_path, level_path)
    return backup_root


def update_user(world_path: Path, player_uid: str, changes: dict[str, object], expected_sha256: str) -> dict[str, object]:
    world_path = world_path.expanduser().resolve()
    level_path = world_path / "Level.sav"
    current_hash = sha256(level_path)
    if current_hash != expected_sha256:
        raise ValueError("Level.sav 已变化，请重新加载后再保存")
    allowed = {"nickname", "level", "experience", "unused_status_points", "satiety"}
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"不支持修改字段：{', '.join(sorted(unknown))}")
    gvas, save_type = open_world(level_path)
    entities = gvas.properties["worldSaveData"]["value"]["CharacterSaveParameterMap"]["value"]
    target = None
    for entity in entities:
        param = parameter_of(entity)
        if bool(value_of(param.get("IsPlayer"), False)) and guid_of(entity["key"].get("PlayerUId")) == player_uid:
            target = param
            break
    if target is None:
        raise ValueError(f"用户不存在：{player_uid}")
    validators = {
        "nickname": lambda value: str(value)[:64],
        "level": lambda value: max(1, min(100, int(value))),
        "experience": lambda value: max(0, min(2**63 - 1, int(value))),
        "unused_status_points": lambda value: max(0, min(65535, int(value))),
        "satiety": lambda value: max(0.0, min(100.0, float(value))),
    }
    pal_fields = {
        "nickname": "NickName", "level": "Level", "experience": "Exp",
        "unused_status_points": "UnusedStatusPoint", "satiety": "FullStomach",
    }
    for field, raw_value in changes.items():
        prop_name = pal_fields[field]
        if prop_name not in target:
            raise ValueError(f"当前用户没有可安全修改的字段：{field}")
        set_value(target[prop_name], validators[field](raw_value))
        if field == "nickname" and "FilteredNickName" in target:
            set_value(target["FilteredNickName"], value_of(target[prop_name]))

    backup_root = _write_world(world_path, gvas)
    result = list_users(world_path)
    result["backup_path"] = str(backup_root)
    return result


def update_inventory_slot(world_path: Path, player_uid: str, category: str, slot_index: int, item_id: str, count: int, expected_sha256: str) -> dict[str, object]:
    world_path = world_path.expanduser().resolve()
    level_path = world_path / "Level.sav"
    if sha256(level_path) != expected_sha256:
        raise ValueError("Level.sav 已变化，请重新加载后再保存")
    valid_items = {row["id"] for row in load_item_index()["items"]}
    if item_id not in valid_items:
        raise ValueError(f"Palworld 不存在该道具 ID：{item_id}")
    count = max(0, min(999999, int(count)))
    ids = player_inventory_ids(world_path, player_uid)
    if category not in ids:
        raise ValueError(f"用户没有该容器：{category}")
    gvas, _ = open_world(level_path)
    rows = gvas.properties["worldSaveData"]["value"]["ItemContainerSaveData"]["value"]
    target_id = ids[category]
    found = False
    for container in rows:
        if guid_of(container["key"].get("ID")) != target_id:
            continue
        for slot in container["value"].get("Slots", {}).get("value", {}).get("values", []):
            raw = slot["RawData"]["value"]
            if int(raw["slot_index"]) == slot_index:
                raw["item"]["static_id"] = item_id
                raw["count"] = count
                found = True
                break
    if not found:
        raise ValueError(f"没有找到槽位：{category} #{slot_index}")
    backup_root = _write_world(world_path, gvas)
    result = list_users(world_path)
    result["backup_path"] = str(backup_root)
    return result
