from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct
from threading import Lock, RLock
from typing import Any

CHARACTER_RAW_PATH = ".worldSaveData.CharacterSaveParameterMap.Value.RawData"
ITEM_CONTAINER_RAW_PATH = ".worldSaveData.ItemContainerSaveData.Value.RawData"
ITEM_SLOT_RAW_PATH = ".worldSaveData.ItemContainerSaveData.Value.Slots.Slots.RawData"
PARSER_REVISION = "paledit-1.0-v0.12-compat-2"


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    """One coherent, read-only decode of a Level.sav payload."""

    level_path: Path
    level_sha256: str
    gvas: Any
    save_type: int
    raw_gvas: bytes


_SNAPSHOT_CACHE: dict[tuple[Path, str], WorldSnapshot] = {}
_SNAPSHOT_LOCKS: dict[Path, Lock] = {}
_SNAPSHOT_GUARD = RLock()


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


def _decode_world_bytes(level_path: Path, data: bytes) -> WorldSnapshot:
    from palworld_save_tools.gvas import GvasFile
    from palworld_save_tools.palsav import decompress_sav_to_gvas
    from .compat import install_palworld_1_0_property_support, palworld_1_0_type_hints

    install_palworld_1_0_property_support()
    raw_gvas, save_type = decompress_sav_to_gvas(data)
    gvas = GvasFile.read(raw_gvas, palworld_1_0_type_hints(), character_custom_properties())
    return WorldSnapshot(
        level_path=level_path,
        level_sha256=hashlib.sha256(data).hexdigest(),
        gvas=gvas,
        save_type=save_type,
        raw_gvas=raw_gvas,
    )


def get_world_snapshot(level_path: Path) -> WorldSnapshot:
    """Return a hash-keyed shared decode, serializing decompression per world.

    The file is read before entering the decode lock so every returned snapshot
    is internally coherent. A later external file replacement naturally creates
    a new hash generation on the next request.
    """
    resolved = level_path.expanduser().resolve()
    data = resolved.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    key = (resolved, digest)
    with _SNAPSHOT_GUARD:
        cached = _SNAPSHOT_CACHE.get(key)
        if cached is not None:
            return cached
        decode_lock = _SNAPSHOT_LOCKS.setdefault(resolved, Lock())
    with decode_lock:
        with _SNAPSHOT_GUARD:
            cached = _SNAPSHOT_CACHE.get(key)
            if cached is not None:
                return cached
        snapshot = _decode_world_bytes(resolved, data)
        with _SNAPSHOT_GUARD:
            for stale_key in [item for item in _SNAPSHOT_CACHE if item[0] == resolved]:
                _SNAPSHOT_CACHE.pop(stale_key, None)
            _SNAPSHOT_CACHE[key] = snapshot
        return snapshot


def invalidate_world_snapshot(path: Path | None = None) -> None:
    """Invalidate one world/Level.sav or the complete read cache."""
    with _SNAPSHOT_GUARD:
        if path is None:
            _SNAPSHOT_CACHE.clear()
            return
        resolved = path.expanduser().resolve()
        level_path = resolved / "Level.sav" if resolved.is_dir() or resolved.name != "Level.sav" else resolved
        for key in [item for item in _SNAPSHOT_CACHE if item[0] == level_path]:
            _SNAPSHOT_CACHE.pop(key, None)


def parser_capabilities() -> dict[str, bool]:
    return {
        "fixed_point_64": True,
        "nested_byte_property": True,
        "item_slots": True,
        "guild_members": True,
        "base_camps": True,
        "last_online_iso": True,
        "raw_map_fallback": True,
        "safe_character_writes": True,
        "safe_inventory_writes": True,
    }


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


def _container_id_prefixes(container_ids: dict[bytes, str]) -> dict[int, list[tuple[bytes, str]]]:
    """Index fixed-width GUID bytes by a cheap four-byte prefix."""
    prefixes: dict[int, list[tuple[bytes, str]]] = {}
    for encoded, container_id in container_ids.items():
        prefix = struct.unpack_from("<I", encoded)[0]
        prefixes.setdefault(prefix, []).append((encoded, container_id))
    return prefixes


def _container_matches(
    data: bytes,
    start: int,
    end: int,
    prefixes: dict[int, list[tuple[bytes, str]]],
) -> dict[bytes, str]:
    """Find known GUIDs in one small module window with a single byte scan."""
    matches: dict[bytes, str] = {}
    for position in range(start, end - 3):
        candidates = prefixes.get(struct.unpack_from("<I", data, position)[0])
        if candidates is None:
            continue
        for encoded, container_id in candidates:
            if data.startswith(encoded, position, end):
                matches[encoded] = container_id
        if len(matches) > 1:
            break
    return matches


def locate_item_container_objects(raw_gvas: bytes, container_ids: dict[bytes, str]) -> list[dict[str, object]]:
    """Associate map objects with item-container GUIDs without decoding map raw payloads.

    Palworld 1.0 added trailing bytes that the upstream map decoder rejects. This
    scanner reads only stable Unreal property framing and leaves map payloads opaque.
    """
    map_marker = struct.pack("<i", len("MapObjectId") + 1) + b"MapObjectId\x00"
    module_marker = b"EPalMapObjectConcreteModelModuleType::ItemContainer\x00"
    prefixes = _container_id_prefixes(container_ids)
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
        matches = _container_matches(raw_gvas, module, min(len(raw_gvas), module + 640), prefixes)
        if len(matches) != 1:
            continue
        labels = _localized_strings(raw_gvas, start, module)
        results.append({
            "object_id": object_id,
            "container_id": next(iter(matches.values())),
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
    snapshot = get_world_snapshot(level_path)
    world = snapshot.gvas.properties["worldSaveData"]["value"]
    characters = world["CharacterSaveParameterMap"]["value"]
    return {
        "save_type": snapshot.save_type,
        "level_sha256": snapshot.level_sha256,
        "character_count": len(characters),
        "world_property_count": len(world),
        "characters": characters,
    }
