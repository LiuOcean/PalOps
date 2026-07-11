from __future__ import annotations

from pathlib import Path
from typing import Any

CHARACTER_RAW_PATH = ".worldSaveData.CharacterSaveParameterMap.Value.RawData"


def load_character_data(level_path: Path) -> dict[str, Any]:
    """Load the 1.0 world while decoding only the proven character raw structure.

    Unknown and currently incompatible raw structures remain opaque, which is
    essential for future lossless writes.
    """
    from palworld_save_tools.gvas import GvasFile
    from palworld_save_tools.palsav import decompress_sav_to_gvas
    from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

    data = level_path.expanduser().resolve().read_bytes()
    raw_gvas, save_type = decompress_sav_to_gvas(data)
    custom = {CHARACTER_RAW_PATH: PALWORLD_CUSTOM_PROPERTIES[CHARACTER_RAW_PATH]}
    gvas = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, custom)
    world = gvas.properties["worldSaveData"]["value"]
    characters = world["CharacterSaveParameterMap"]["value"]
    return {
        "save_type": save_type,
        "character_count": len(characters),
        "world_property_count": len(world),
        "characters": characters,
    }

