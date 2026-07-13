from __future__ import annotations

from pathlib import Path
import struct
from typing import Any

CHARACTER_RAW_PATH = ".worldSaveData.CharacterSaveParameterMap.Value.RawData"
ITEM_CONTAINER_RAW_PATH = ".worldSaveData.ItemContainerSaveData.Value.RawData"
ITEM_SLOT_RAW_PATH = ".worldSaveData.ItemContainerSaveData.Value.Slots.Slots.RawData"


def character_custom_properties() -> dict[str, object]:
    from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES

    paths = [CHARACTER_RAW_PATH, ITEM_CONTAINER_RAW_PATH, ITEM_SLOT_RAW_PATH]
    return {path: PALWORLD_CUSTOM_PROPERTIES[path] for path in paths}


def open_world(level_path: Path):
    from palworld_save_tools.gvas import GvasFile
    from palworld_save_tools.palsav import decompress_sav_to_gvas
    from .compat import install_palworld_1_0_property_support, palworld_1_0_type_hints

    install_palworld_1_0_property_support()
    data = level_path.expanduser().resolve().read_bytes()
    raw_gvas, save_type = decompress_sav_to_gvas(data)
    gvas = GvasFile.read(raw_gvas, palworld_1_0_type_hints(), character_custom_properties())
    return gvas, save_type


def open_world_with_raw(level_path: Path):
    """Read the safe world subset and retain decompressed bytes for map-object lookup."""
    from palworld_save_tools.gvas import GvasFile
    from palworld_save_tools.palsav import decompress_sav_to_gvas
    from .compat import install_palworld_1_0_property_support, palworld_1_0_type_hints

    install_palworld_1_0_property_support()
    data = level_path.expanduser().resolve().read_bytes()
    raw_gvas, save_type = decompress_sav_to_gvas(data)
    gvas = GvasFile.read(raw_gvas, palworld_1_0_type_hints(), character_custom_properties())
    return gvas, save_type, raw_gvas


def _read_fstring(data: bytes, offset: int) -> tuple[str, int]:
    length = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    if length == 0:
        return "", offset
    if length > 0:
        end = offset + length
        return data[offset:end - 1].decode("utf-8", errors="replace"), end
    end = offset + (-length * 2)
    return data[offset:end - 2].decode("utf-16le", errors="replace"), end


def _map_object_id(data: bytes, marker: int) -> str:
    _, offset = _read_fstring(data, marker)
    _, offset = _read_fstring(data, offset)
    offset += 9  # property size plus the NameProperty terminator byte
    value, _ = _read_fstring(data, offset)
    return value


def _localized_strings(data: bytes, start: int, end: int) -> list[str]:
    values: list[str] = []
    cursor = start
    while cursor + 6 <= end:
        length = struct.unpack_from("<i", data, cursor)[0]
        if -128 <= length <= -2:
            byte_length = -length * 2
            stop = cursor + 4 + byte_length
            if stop <= end and data[stop - 2:stop] == b"\x00\x00":
                try:
                    value = data[cursor + 4:stop - 2].decode("utf-16le")
                except UnicodeDecodeError:
                    value = ""
                if value and any("\u4e00" <= char <= "\u9fff" for char in value):
                    values.append(value)
                cursor = stop
                continue
        cursor += 1
    return list(dict.fromkeys(values))


def locate_item_container_objects(raw_gvas: bytes, container_ids: dict[bytes, str]) -> list[dict[str, object]]:
    """Associate map objects with item-container GUIDs without decoding map raw payloads.

    Palworld 1.0 added trailing bytes that the upstream map decoder rejects. This
    scanner reads only stable Unreal property framing and leaves map payloads opaque.
    """
    map_marker = struct.pack("<i", len("MapObjectId") + 1) + b"MapObjectId\x00"
    module_marker = b"EPalMapObjectConcreteModelModuleType::ItemContainer\x00"
    results: list[dict[str, object]] = []
    cursor = 0
    while True:
        module = raw_gvas.find(module_marker, cursor)
        if module < 0:
            break
        cursor = module + len(module_marker)
        start = raw_gvas.rfind(map_marker, max(0, module - 20000), module)
        if start < 0:
            continue
        try:
            object_id = _map_object_id(raw_gvas, start)
        except (UnicodeDecodeError, struct.error):
            continue
        matches = [
            (raw_gvas.find(encoded, module, module + 640), container_id)
            for encoded, container_id in container_ids.items()
        ]
        matches = [(position, container_id) for position, container_id in matches if position >= 0]
        if len(matches) != 1:
            continue
        labels = _localized_strings(raw_gvas, start, module)
        results.append({
            "object_id": object_id,
            "container_id": matches[0][1],
            "label": labels[-1] if labels else "",
            "labels": labels,
        })
    unique = {(row["object_id"], row["container_id"]): row for row in results}
    return list(unique.values())


def load_character_data(level_path: Path) -> dict[str, Any]:
    """Load the 1.0 world while decoding only the proven character raw structure.

    Unknown and currently incompatible raw structures remain opaque, which is
    essential for future lossless writes.
    """
    gvas, save_type = open_world(level_path)
    world = gvas.properties["worldSaveData"]["value"]
    characters = world["CharacterSaveParameterMap"]["value"]
    return {
        "save_type": save_type,
        "character_count": len(characters),
        "world_property_count": len(world),
        "characters": characters,
    }
