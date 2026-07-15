from __future__ import annotations

import argparse
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import struct
from typing import Any, Callable
from uuid import UUID, uuid4

from .compat import install_palworld_1_0_property_support, palworld_1_0_type_hints
from .parser import (
    CHARACTER_CONTAINER_SLOT_RAW_PATH,
    CHARACTER_RAW_PATH,
    invalidate_world_snapshot,
)
from .save import sha256
from .world import (
    guid_of,
    parameter_of,
    player_pal_container_ids,
    set_value,
    value_of,
)


ZERO_GUID = "00000000-0000-0000-0000-000000000000"
_EDITABLE_WORLD_PROPERTIES = {
    "CharacterSaveParameterMap",
    "CharacterContainerSaveData",
    "GroupSaveDataMap",
}


def _skip_decode(reader: Any, type_name: str, size: int, path: str) -> dict[str, Any]:
    if type_name == "ArrayProperty":
        return {
            "skip_type": type_name,
            "array_type": reader.fstring(),
            "id": reader.optional_guid(),
            "value": reader.read(size),
        }
    if type_name == "MapProperty":
        return {
            "skip_type": type_name,
            "key_type": reader.fstring(),
            "value_type": reader.fstring(),
            "id": reader.optional_guid(),
            "value": reader.read(size),
        }
    if type_name == "StructProperty":
        return {
            "skip_type": type_name,
            "struct_type": reader.fstring(),
            "struct_id": reader.guid(),
            "id": reader.optional_guid(),
            "value": reader.read(size),
        }
    raise ValueError(f"不支持原字节保留的属性类型：{type_name} ({path})")


def _skip_encode(writer: Any, property_type: str, properties: dict[str, Any]) -> int:
    if "skip_type" not in properties:
        from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES

        return PALWORLD_CUSTOM_PROPERTIES[properties["custom_type"]][1](writer, property_type, properties)
    properties.pop("custom_type", None)
    properties.pop("skip_type", None)
    if property_type == "ArrayProperty":
        writer.fstring(properties["array_type"])
        writer.optional_guid(properties.get("id"))
    elif property_type == "MapProperty":
        writer.fstring(properties["key_type"])
        writer.fstring(properties["value_type"])
        writer.optional_guid(properties.get("id"))
    elif property_type == "StructProperty":
        writer.fstring(properties["struct_type"])
        writer.guid(properties["struct_id"])
        writer.optional_guid(properties.get("id"))
    else:
        raise ValueError(f"不支持原字节写回的属性类型：{property_type}")
    writer.write(properties["value"])
    return len(properties["value"])


def _safe_custom_properties(world_properties: dict[str, Any]) -> dict[str, object]:
    from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES

    custom: dict[str, object] = {
        CHARACTER_RAW_PATH: PALWORLD_CUSTOM_PROPERTIES[CHARACTER_RAW_PATH],
        CHARACTER_CONTAINER_SLOT_RAW_PATH: PALWORLD_CUSTOM_PROPERTIES[CHARACTER_CONTAINER_SLOT_RAW_PATH],
    }
    for name, prop in world_properties.items():
        if name not in _EDITABLE_WORLD_PROPERTIES and prop.get("type") in {
            "ArrayProperty",
            "MapProperty",
            "StructProperty",
        }:
            custom[f".worldSaveData.{name}"] = (_skip_decode, _skip_encode)
    return custom


def _open_safe_world(level_path: Path):
    from palworld_save_tools.gvas import GvasFile
    from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES
    from palworld_save_tools.palsav import decompress_sav_to_gvas

    install_palworld_1_0_property_support()
    raw, save_type = decompress_sav_to_gvas(level_path.read_bytes())
    probe = GvasFile.read(raw, palworld_1_0_type_hints(), {
        CHARACTER_RAW_PATH: PALWORLD_CUSTOM_PROPERTIES[CHARACTER_RAW_PATH],
        CHARACTER_CONTAINER_SLOT_RAW_PATH: PALWORLD_CUSTOM_PROPERTIES[CHARACTER_CONTAINER_SLOT_RAW_PATH],
    })
    custom = _safe_custom_properties(probe.properties["worldSaveData"]["value"])
    return GvasFile.read(raw, palworld_1_0_type_hints(), custom), save_type, custom


def _add_guild_handles(group_rows: list[dict[str, Any]], owner_player_uid: str, instance_ids: list[str]) -> None:
    from palworld_save_tools.archive import FArchiveReader, FArchiveWriter, UUID as PalUUID
    from .world import decode_guild_raw

    target_raw: dict[str, Any] | None = None
    for row in group_rows:
        group_type = str(value_of(row["value"].get("GroupType"), ""))
        raw = value_of(row["value"].get("RawData"), {})
        values = raw.get("values", ()) if isinstance(raw, dict) else ()
        guild = decode_guild_raw(values, group_type)
        if guild and any(member["player_uid"] == owner_player_uid for member in guild["players"]):
            target_raw = raw
            break
    if target_raw is None:
        raise ValueError("没有找到目标玩家所属的公会记录")

    payload = bytes(target_raw["values"])
    reader = FArchiveReader(payload, debug=False)
    reader.guid()
    reader.fstring()
    count_offset = reader.data.tell()
    old_count = reader.i32()
    handles_end = reader.data.tell() + old_count * 32
    if handles_end > len(payload):
        raise ValueError("公会角色句柄表已截断")
    writer = FArchiveWriter()
    for instance_id in instance_ids:
        writer.guid(PalUUID.from_str(ZERO_GUID))
        writer.guid(PalUUID.from_str(instance_id))
    target_raw["values"] = list(
        payload[:count_offset]
        + struct.pack("<i", old_count + len(instance_ids))
        + payload[count_offset + 4:handles_end]
        + writer.bytes()
        + payload[handles_end:]
    )


def _write_safe_world(world_path: Path, gvas: Any, custom_properties: dict[str, object]) -> Path:
    from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
    from palworld_save_tools.gvas import GvasFile

    level_path = world_path / "Level.sav"
    backup_root = world_path / "PalEdit-Backup" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    shutil.copytree(world_path, backup_root, ignore=shutil.ignore_patterns("backup", "PalEdit-Backup"))
    raw = copy.deepcopy(gvas).write(custom_properties)
    output = compress_gvas_to_sav(raw, 0x32, True)
    raw_check, _ = decompress_sav_to_gvas(output)
    GvasFile.read(raw_check, palworld_1_0_type_hints(), custom_properties)
    temp_path = level_path.with_suffix(".sav.paledit.tmp")
    temp_path.write_bytes(output)
    os.replace(temp_path, level_path)
    invalidate_world_snapshot(level_path)
    return backup_root


def _slot_instance_id(slot: dict[str, Any]) -> str:
    raw = slot.get("RawData", {}).get("value")
    if not isinstance(raw, dict):
        return "00000000-0000-0000-0000-000000000000"
    return str(raw.get("instance_id") or "00000000-0000-0000-0000-000000000000")


def _clone_pal_records(
    entities: list[dict[str, Any]],
    container: dict[str, Any],
    *,
    source_container: dict[str, Any] | None = None,
    owner_player_uid: str,
    source_instance_id: str,
    count: int,
    id_factory: Callable[[], UUID] = uuid4,
) -> list[dict[str, object]]:
    owner_player_uid = str(UUID(owner_player_uid)).lower()
    source_instance_id = str(UUID(source_instance_id)).lower()
    if not 1 <= count <= 100:
        raise ValueError("克隆数量必须在 1–100 之间")

    source = next(
        (
            entity for entity in entities
            if guid_of(entity["key"].get("InstanceId")).lower() == source_instance_id
            and guid_of(parameter_of(entity).get("OwnerPlayerUId")).lower() == owner_player_uid
        ),
        None,
    )
    if source is None:
        raise ValueError("没有找到属于目标玩家的源帕鲁实例")

    slots = container["value"].get("Slots", {}).get("value", {}).get("values", [])
    capacity = int(value_of(container["value"].get("SlotNum"), len(slots)))
    if capacity < len(slots):
        raise ValueError("帕鲁终端槽位数据超过声明容量")

    source_slots = (source_container or container)["value"].get("Slots", {}).get("value", {}).get("values", [])
    source_slot = next((slot for slot in source_slots if _slot_instance_id(slot).lower() == source_instance_id), None)
    if source_slot is None:
        raise ValueError("源帕鲁实体与终端槽位引用不一致")

    occupied = {int(value_of(slot.get("SlotIndex"), -1)) for slot in slots}
    free_slots = [
        index for index in range(capacity)
        if index not in occupied
    ]
    if len(free_slots) < count:
        raise ValueError(f"帕鲁终端空槽不足：需要 {count}，当前只有 {len(free_slots)}")

    existing_ids = {guid_of(entity["key"].get("InstanceId")).lower() for entity in entities}
    target_container_id = guid_of(container["key"].get("ID"))
    created: list[dict[str, object]] = []
    for slot_index in free_slots[:count]:
        new_instance_id = str(id_factory()).lower()
        if new_instance_id in existing_ids:
            raise ValueError("生成了重复的帕鲁实例 ID")
        existing_ids.add(new_instance_id)

        clone = copy.deepcopy(source)
        set_value(clone["key"]["InstanceId"], new_instance_id)
        set_value(clone["key"]["PlayerUId"], ZERO_GUID)
        clone_param = parameter_of(clone)
        clone_param.pop("MapObjectConcreteInstanceIdAssignedToExpedition", None)
        if "EquipItemContainerId" in clone_param:
            equip_id = value_of(clone_param["EquipItemContainerId"], {})
            set_value(equip_id["ID"], str(id_factory()).lower())
        slot_id = value_of(clone_param["SlotId"], {})
        set_value(value_of(slot_id["ContainerId"], {})["ID"], target_container_id)
        set_value(slot_id["SlotIndex"], slot_index)
        entities.append(clone)

        slot = copy.deepcopy(source_slot)
        raw = slot["RawData"]["value"]
        raw["instance_id"] = new_instance_id
        set_value(slot["SlotIndex"], slot_index)
        slots.append(slot)
        created.append({"instance_id": new_instance_id, "slot_index": slot_index})
    return created


def clone_owned_pal(
    world_path: Path,
    *,
    owner_player_uid: str,
    source_instance_id: str,
    count: int,
    expected_sha256: str,
) -> dict[str, object]:
    world_path = world_path.expanduser().resolve()
    level_path = world_path / "Level.sav"
    before_hash = sha256(level_path)
    if before_hash != expected_sha256:
        raise ValueError("Level.sav 已变化，拒绝应用旧的帕鲁克隆计划")

    terminal_id = player_pal_container_ids(world_path, owner_player_uid)["帕鲁终端"]
    gvas, _, custom_properties = _open_safe_world(level_path)
    world = gvas.properties["worldSaveData"]["value"]
    entities = world["CharacterSaveParameterMap"]["value"]
    container = next(
        (
            row for row in world["CharacterContainerSaveData"]["value"]
            if guid_of(row["key"].get("ID")) == terminal_id
        ),
        None,
    )
    if container is None:
        raise ValueError("没有找到目标玩家的帕鲁终端容器")
    source = next(
        entity for entity in world["CharacterSaveParameterMap"]["value"]
        if guid_of(entity["key"].get("InstanceId")).lower() == source_instance_id.lower()
    )
    source_container_id = guid_of(
        value_of(value_of(parameter_of(source)["SlotId"], {})["ContainerId"], {}).get("ID")
    )
    source_container = next(
        (
            row for row in world["CharacterContainerSaveData"]["value"]
            if guid_of(row["key"].get("ID")) == source_container_id
        ),
        None,
    )
    if source_container is None:
        raise ValueError("没有找到源帕鲁所在的容器")

    created = _clone_pal_records(
        entities,
        container,
        source_container=source_container,
        owner_player_uid=owner_player_uid,
        source_instance_id=source_instance_id,
        count=count,
    )
    _add_guild_handles(
        world["GroupSaveDataMap"]["value"],
        owner_player_uid.lower(),
        [str(row["instance_id"]) for row in created],
    )
    backup_root = _write_safe_world(world_path, gvas, custom_properties)
    return {
        "before_sha256": before_hash,
        "after_sha256": sha256(level_path),
        "backup_path": str(backup_root),
        "created": created,
        "count": len(created),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="按实例 ID 克隆玩家帕鲁到帕鲁终端空槽")
    parser.add_argument("world", type=Path)
    parser.add_argument("--owner-player-uid", required=True)
    parser.add_argument("--source-instance-id", required=True)
    parser.add_argument("--count", required=True, type=int)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    result = clone_owned_pal(
        args.world,
        owner_player_uid=args.owner_player_uid,
        source_instance_id=args.source_instance_id,
        count=args.count,
        expected_sha256=args.expected_sha256,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
