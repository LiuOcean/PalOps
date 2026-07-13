from __future__ import annotations

import copy
import os
import shutil
import struct
from datetime import datetime
from pathlib import Path
from typing import Any

from .pals import get_pal
from .items import load_item_index
from .parser import character_custom_properties, locate_item_container_objects, open_world, open_world_with_raw
from .save import sha256
from .skills import describe_skills


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


def array_values(prop: dict[str, Any] | None) -> list[Any]:
    value = value_of(prop, [])
    if isinstance(value, dict):
        value = value.get("values", [])
    return list(value) if isinstance(value, list) else []


def decode_guild_raw(raw_values: Any, group_type: str) -> dict[str, object] | None:
    """Decode the stable, read-only guild subset from a 1.0 raw group payload."""
    if group_type != "EPalGroupType::Guild":
        return None

    from palworld_save_tools.archive import FArchiveReader, uuid_reader

    reader = FArchiveReader(bytes(raw_values), debug=False)
    group_id = str(reader.guid())
    reader.fstring()  # Internal group name; the user-facing name follows below.
    handle_count = reader.i32()
    if not 0 <= handle_count <= 1_000_000:
        raise ValueError(f"invalid guild handle count: {handle_count}")
    if len(reader.read(handle_count * 32)) != handle_count * 32:
        raise ValueError("truncated guild character handles")
    reader.byte()  # Organization type.
    reader.byte_list(4)
    base_ids = [str(value) for value in reader.tarray(uuid_reader)]
    reader.i32()
    base_camp_level = reader.i32()
    reader.tarray(uuid_reader)
    guild_name = reader.fstring()
    last_modifier_uid = str(reader.guid())
    reader.byte_list(4)

    players: list[dict[str, object]] = []
    admin_player_uid = last_modifier_uid
    members_decoded = False
    tail = reader.read_to_end()
    v1_marker = b"\x02\x00\x00\x00\x02\x03\x00\x00\x00\x00"
    marker_at = tail.find(v1_marker)
    if marker_at >= 0:
        tail = tail[marker_at + len(v1_marker):]
    try:
        member_reader = FArchiveReader(tail, debug=False)
        admin_player_uid = str(member_reader.guid())
        player_count = member_reader.i32()
        if not 0 <= player_count <= 10_000:
            raise ValueError(f"invalid guild player count: {player_count}")
        for _ in range(player_count):
            player_uid = str(member_reader.guid())
            last_online_ticks = member_reader.i64()
            nickname = member_reader.fstring()
            if marker_at >= 0 and not member_reader.eof():
                member_reader.byte()
            players.append({
                "player_uid": player_uid,
                "nickname": nickname,
                "last_online_ticks": last_online_ticks,
            })
        members_decoded = True
    except (EOFError, OSError, TypeError, UnicodeDecodeError, ValueError, struct.error):
        players = []

    unnamed = not guild_name.strip() or guild_name == "Unnamed Guild"
    leader = next((player for player in players if player["player_uid"] == admin_player_uid), None)
    suffix = str(leader["nickname"] if leader else admin_player_uid[-6:])
    return {
        "guild_id": group_id,
        "name": guild_name,
        "display_name": f"无名公会 · {suffix}" if unnamed else guild_name,
        "is_unnamed": unnamed,
        "base_camp_level": base_camp_level,
        "admin_player_uid": admin_player_uid,
        "players": players,
        "member_count": len(players),
        "members_decoded": members_decoded,
        "base_ids": base_ids,
    }


def decode_base_camp_raw(raw_values: Any) -> dict[str, object]:
    """Decode base identity and position without enabling its write codec."""
    from palworld_save_tools.archive import FArchiveReader

    reader = FArchiveReader(bytes(raw_values), debug=False)
    base_id = str(reader.guid())
    source_name = reader.fstring()
    state = reader.byte()
    transform = reader.ftransform()
    area_range = reader.float()
    group_id = str(reader.guid())
    reader.ftransform()
    owner_map_object_instance_id = str(reader.guid())
    return {
        "base_id": base_id,
        "source_name": source_name,
        "state": state,
        "area_range": area_range,
        "group_id": group_id,
        "location": transform["translation"],
        "owner_map_object_instance_id": owner_map_object_instance_id,
    }


def pal_readonly_details(param: dict[str, Any]) -> dict[str, object]:
    skill_ids = [str(value) for value in array_values(param.get("PassiveSkillList"))]
    return {
        "hp": stat_value(param.get("Hp")),
        "talents": {
            "hp": int(value_of(param.get("Talent_HP"), 0)),
            "attack": int(value_of(param.get("Talent_Shot"), 0)),
            "defense": int(value_of(param.get("Talent_Defense"), 0)),
        },
        "condensation_rank": int(value_of(param.get("Rank"), 1)),
        "rank_boosts": {
            "attack": int(value_of(param.get("Rank_Attack"), 0)),
            "defense": int(value_of(param.get("Rank_Defence"), 0)),
            "work_speed": int(value_of(param.get("Rank_CraftSpeed"), 0)),
        },
        "passive_skills": describe_skills(skill_ids),
    }


def load_player_gvas(world_path: Path, player_uid: str):
    from palworld_save_tools.gvas import GvasFile
    from palworld_save_tools.palsav import decompress_sav_to_gvas
    from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS

    filename = f"{player_uid.split('-')[0].upper()}000000000000000000000000.sav"
    player_path = world_path / "Players" / filename
    raw, save_type = decompress_sav_to_gvas(player_path.read_bytes())
    return player_path, GvasFile.read(raw, PALWORLD_TYPE_HINTS, {}), save_type


def player_inventory_ids(world_path: Path, player_uid: str) -> dict[str, str]:
    _, gvas, _ = load_player_gvas(world_path, player_uid)
    save = gvas.properties["SaveData"]["value"]
    info = save["InventoryInfo"]["value"]
    labels = {
        "CommonContainerId": "背包",
        "EssentialContainerId": "重要物品",
        "WeaponLoadOutContainerId": "武器装备",
        "PlayerEquipArmorContainerId": "防具装备",
        "FoodEquipContainerId": "食物装备",
    }
    return {label: guid_of(info[key]["value"]["ID"]) for key, label in labels.items() if key in info}


def player_file_data(world_path: Path, player_uid: str) -> dict[str, object]:
    player_path, gvas, _ = load_player_gvas(world_path, player_uid)
    save = gvas.properties["SaveData"]["value"]
    return {
        "player_file": str(player_path.relative_to(world_path)),
        "player_file_sha256": sha256(player_path),
        "technology_points": int(value_of(save.get("TechnologyPoint"), 0)),
        "boss_technology_points": int(value_of(save.get("bossTechnologyPoint"), 0)),
    }


def inventory_containers(gvas: Any) -> dict[str, list[dict[str, object]]]:
    item_data = {row["id"]: row for row in load_item_index()["items"]}
    rows = gvas.properties["worldSaveData"]["value"]["ItemContainerSaveData"]["value"]
    result: dict[str, list[dict[str, object]]] = {}
    for container in rows:
        container_id = guid_of(container["key"].get("ID"))
        slots = container["value"].get("Slots", {}).get("value", {}).get("values", [])
        result[container_id] = []
        for slot in slots:
            raw = slot["RawData"]["value"]
            item_id = str(raw["item"]["static_id"])
            item = item_data.get(item_id, {})
            result[container_id].append({
                "slot_index": int(raw["slot_index"]),
                "item_id": item_id,
                "name_zh": item.get("name_zh", item_id),
                "icon_url": item.get("icon_url", ""),
                "category": item.get("category", "其他"),
                "description": item.get("description", "未知或未收录的 Palworld 内部道具。"),
                "count": int(raw["count"]),
            })
    return result


def list_storage_containers(world_path: Path) -> dict[str, object]:
    from palworld_save_tools.archive import FArchiveWriter

    world_path = world_path.expanduser().resolve()
    gvas, _, raw_gvas = open_world_with_raw(world_path / "Level.sav")
    rows = gvas.properties["worldSaveData"]["value"]["ItemContainerSaveData"]["value"]
    containers = inventory_containers(gvas)
    metadata: dict[str, dict[str, object]] = {}
    encoded_ids: dict[bytes, str] = {}
    for row in rows:
        container_id = guid_of(row["key"].get("ID"))
        writer = FArchiveWriter()
        writer.guid(container_id)
        encoded_ids[writer.bytes()] = container_id
        metadata[container_id] = {
            "slot_capacity": int(value_of(row["value"].get("SlotNum"), 0)),
            "slots": containers.get(container_id, []),
        }
    objects = locate_item_container_objects(raw_gvas, encoded_ids)
    storage_markers = ("ItemChest", "Refrigerator", "CoolerBox", "FoodBox", "DeathPenaltyStorage")
    type_names = {
        "ItemChest_01": "木制箱",
        "ItemChest_02": "金属箱",
        "ItemChest_03": "精炼金属箱",
        "ItemChest_04": "高等文明箱",
    }
    result = []
    for item in objects:
        if not any(marker in str(item["object_id"]) for marker in storage_markers):
            continue
        detail = metadata.get(str(item["container_id"]))
        if detail is None:
            continue
        slots = detail["slots"]
        result.append({
            **item,
            **detail,
            "type_name": type_names.get(str(item["object_id"]), str(item["object_id"])),
            "occupied_slots": sum(1 for slot in slots if slot["item_id"] != "None" and slot["count"] > 0),
            "total_items": sum(slot["count"] for slot in slots if slot["item_id"] != "None"),
        })
    result.sort(key=lambda row: (not bool(row["label"]), str(row["label"]), str(row["object_id"]), str(row["container_id"])))
    return {
        "world_id": world_path.name,
        "level_sha256": sha256(world_path / "Level.sav"),
        "containers": result,
        "count": len(result),
        "labeled_count": sum(bool(row["label"]) for row in result),
    }


def list_guilds(world_path: Path) -> dict[str, object]:
    world_path = world_path.expanduser().resolve()
    gvas, _ = open_world(world_path / "Level.sav")
    world = gvas.properties["worldSaveData"]["value"]

    base_camps: list[dict[str, object]] = []
    for row in value_of(world.get("BaseCampSaveData"), []):
        raw = value_of(row["value"].get("RawData"), {})
        values = raw.get("values", ()) if isinstance(raw, dict) else ()
        base_camps.append(decode_base_camp_raw(values))

    guilds: list[dict[str, object]] = []
    for row in value_of(world.get("GroupSaveDataMap"), []):
        group_type = str(value_of(row["value"].get("GroupType"), ""))
        raw = value_of(row["value"].get("RawData"), {})
        values = raw.get("values", ()) if isinstance(raw, dict) else ()
        guild = decode_guild_raw(values, group_type)
        if guild is None:
            continue
        base_ids = set(guild["base_ids"])
        guild_bases = [
            base for base in base_camps
            if base["base_id"] in base_ids or base["group_id"] == guild["guild_id"]
        ]
        guild_bases.sort(key=lambda base: str(base["base_id"]))
        guild["base_camps"] = guild_bases
        guild["base_count"] = len(guild_bases)
        guilds.append(guild)

    guilds.sort(key=lambda guild: (-int(guild["base_camp_level"]), str(guild["display_name"])))
    return {
        "world_id": world_path.name,
        "level_sha256": sha256(world_path / "Level.sav"),
        "guilds": guilds,
        "count": len(guilds),
        "base_count": len(base_camps),
    }


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
            pal_meta = get_pal(character_id) or {}
            pals_by_owner.setdefault(owner, []).append({
                "instance_id": instance_id,
                "character_id": character_id,
                "name_zh": pal_meta.get("name_zh", character_id),
                "icon_url": pal_meta.get("icon_url", ""),
                "nickname": value_of(param.get("NickName"), ""),
                "level": int(value_of(param.get("Level"), 1)),
                "experience": int(value_of(param.get("Exp"), 0)),
                "gender": value_of(param.get("Gender"), ""),
                "is_boss": bool(value_of(param.get("IsBoss"), False)),
                "is_lucky": bool(value_of(param.get("IsRarePal"), False)),
                "is_tower": character_id.casefold().startswith("gym_"),
                **pal_readonly_details(param),
            })
    for uid, user in users.items():
        user["pals"] = sorted(pals_by_owner.get(uid, []), key=lambda pal: (str(pal["name_zh"]), str(pal["instance_id"])))
        user["pal_count"] = len(user["pals"])
        try:
            ids = player_inventory_ids(world_path, uid)
            user.update(player_file_data(world_path, uid))
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


def _write_player(player_path: Path, gvas: Any) -> None:
    from palworld_save_tools.palsav import compress_gvas_to_sav

    raw = copy.deepcopy(gvas).write({})
    output = compress_gvas_to_sav(raw, 0x32, True)
    temp_path = player_path.with_suffix(".sav.paledit.tmp")
    temp_path.write_bytes(output)
    raw_check, _ = __import__("palworld_save_tools.palsav", fromlist=["decompress_sav_to_gvas"]).decompress_sav_to_gvas(output)
    from palworld_save_tools.gvas import GvasFile
    from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS
    GvasFile.read(raw_check, PALWORLD_TYPE_HINTS, {})
    os.replace(temp_path, player_path)


def update_user(world_path: Path, player_uid: str, changes: dict[str, object], expected_sha256: str, expected_player_sha256: str | None = None) -> dict[str, object]:
    world_path = world_path.expanduser().resolve()
    level_path = world_path / "Level.sav"
    current_hash = sha256(level_path)
    if current_hash != expected_sha256:
        raise ValueError("Level.sav 已变化，请重新加载后再保存")
    allowed = {"nickname", "level", "experience", "unused_status_points", "satiety", "technology_points"}
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
        "technology_points": lambda value: max(0, min(9999, int(value))),
    }
    pal_fields = {
        "nickname": "NickName", "level": "Level", "experience": "Exp",
        "unused_status_points": "UnusedStatusPoint", "satiety": "FullStomach",
    }
    world_changes = {field: value for field, value in changes.items() if field != "technology_points"}
    for field, raw_value in world_changes.items():
        prop_name = pal_fields[field]
        if prop_name not in target:
            raise ValueError(f"当前用户没有可安全修改的字段：{field}")
        set_value(target[prop_name], validators[field](raw_value))
        if field == "nickname" and "FilteredNickName" in target:
            set_value(target["FilteredNickName"], value_of(target[prop_name]))

    backup_root = world_path / "PalEdit-Backup" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    shutil.copytree(world_path, backup_root, ignore=shutil.ignore_patterns("backup", "PalEdit-Backup"))
    if world_changes:
        raw = copy.deepcopy(gvas).write(character_custom_properties())
        from palworld_save_tools.palsav import compress_gvas_to_sav
        output = compress_gvas_to_sav(raw, 0x32, True)
        temp_path = level_path.with_suffix(".sav.paledit.tmp")
        temp_path.write_bytes(output)
        open_world(temp_path)
        os.replace(temp_path, level_path)
    if "technology_points" in changes:
        player_path, player_gvas, _ = load_player_gvas(world_path, player_uid)
        if expected_player_sha256 and sha256(player_path) != expected_player_sha256:
            raise ValueError("玩家文件已变化，请重新加载后再保存")
        player_save = player_gvas.properties["SaveData"]["value"]
        if "TechnologyPoint" not in player_save:
            raise ValueError("当前玩家文件没有 TechnologyPoint 字段")
        set_value(player_save["TechnologyPoint"], validators["technology_points"](changes["technology_points"]))
        _write_player(player_path, player_gvas)
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


def grant_inventory_items(
    world_path: Path,
    player_uid: str,
    category: str,
    items: dict[str, int],
    expected_sha256: str,
) -> dict[str, object]:
    """Add item stacks without replacing occupied inventory slots."""
    world_path = world_path.expanduser().resolve()
    level_path = world_path / "Level.sav"
    if sha256(level_path) != expected_sha256:
        raise ValueError("Level.sav 已变化，请重新加载后再发放")
    valid_items = {str(row["id"]) for row in load_item_index()["items"]}
    unknown = sorted(set(items) - valid_items)
    if unknown:
        raise ValueError(f"Palworld 不存在道具 ID：{', '.join(unknown)}")
    grants = {item_id: max(1, min(999999, int(count))) for item_id, count in items.items()}

    ids = player_inventory_ids(world_path, player_uid)
    if category not in ids:
        raise ValueError(f"用户没有该容器：{category}")
    gvas, _ = open_world(level_path)
    rows = gvas.properties["worldSaveData"]["value"]["ItemContainerSaveData"]["value"]
    target_id = ids[category]
    target = next((row for row in rows if guid_of(row["key"].get("ID")) == target_id), None)
    if target is None:
        raise ValueError(f"没有找到容器：{category}")
    slots = target["value"].get("Slots", {}).get("value", {}).get("values", [])
    if not slots:
        raise ValueError(f"容器没有可复用的槽位结构：{category}")
    capacity = int(value_of(target["value"].get("SlotNum"), len(slots)))
    occupied = {int(slot["RawData"]["value"]["slot_index"]) for slot in slots}
    free = [index for index in range(capacity) if index not in occupied]
    if len(free) < len(grants):
        raise ValueError(f"{category} 空槽不足：需要 {len(grants)}，实际 {len(free)}")

    added: dict[str, int] = {}
    template = slots[0]
    for slot_index, (item_id, count) in zip(free, grants.items(), strict=False):
        slot = copy.deepcopy(template)
        raw = slot["RawData"]["value"]
        raw["slot_index"] = slot_index
        raw["item"]["static_id"] = item_id
        raw["count"] = count
        slots.append(slot)
        added[item_id] = slot_index
    slots.sort(key=lambda slot: int(slot["RawData"]["value"]["slot_index"]))

    backup_root = _write_world(world_path, gvas)
    result = list_users(world_path)
    result["backup_path"] = str(backup_root)
    result["granted_slots"] = added
    return result
