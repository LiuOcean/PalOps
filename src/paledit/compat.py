from __future__ import annotations

from typing import Any


PALWORLD_1_0_TYPE_HINTS = {
    ".worldSaveData.LevelObjectRecoverPartySaveData.Key": "Guid",
    ".worldSaveData.LevelObjectRecoverPartySaveData.Value": "StructProperty",
    ".worldSaveData.LevelObjectRecoverPartySaveData.Value.PlayerLastUsedTimes.Key": "Guid",
    ".worldSaveData.LockGimmickSaveData.Key": "Guid",
    ".worldSaveData.LockGimmickSaveData.Value": "StructProperty",
    ".worldSaveData.DungeonSaveData.DungeonSaveData.RewardSaveDataMap.Key": "Guid",
    ".worldSaveData.DungeonSaveData.DungeonSaveData.RewardSaveDataMap.Value": "StructProperty",
}


def palworld_1_0_type_hints() -> dict[str, str]:
    from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS

    return {**PALWORLD_TYPE_HINTS, **PALWORLD_1_0_TYPE_HINTS}


def install_palworld_1_0_property_support() -> None:
    """Add map-value support missing from the pinned save-tools revision.

    Palworld 1.0 stores LevelObjectRecoverPartySaveData.PlayerLastUsedTimes as a
    MapProperty whose value type is Int64Property. The dependency understands
    standalone Int64Property values and arrays, but omits Int64 map values from
    FArchiveReader/FArchiveWriter.prop_value.
    """
    from palworld_save_tools.archive import FArchiveReader, FArchiveWriter

    if getattr(FArchiveReader.prop_value, "_paledit_int64_compatible", False):
        return

    original_reader = FArchiveReader.prop_value
    original_writer = FArchiveWriter.prop_value

    def read_prop_value(self: Any, type_name: str, struct_type_name: str, path: str):
        if type_name == "Int64Property":
            return self.i64()
        return original_reader(self, type_name, struct_type_name, path)

    def write_prop_value(self: Any, type_name: str, struct_type_name: str, value: Any):
        if type_name == "Int64Property":
            self.i64(value)
            return None
        return original_writer(self, type_name, struct_type_name, value)

    read_prop_value._paledit_int64_compatible = True  # type: ignore[attr-defined]
    write_prop_value._paledit_int64_compatible = True  # type: ignore[attr-defined]
    FArchiveReader.prop_value = read_prop_value
    FArchiveWriter.prop_value = write_prop_value
