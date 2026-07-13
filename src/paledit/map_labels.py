from __future__ import annotations

from typing import Any


def decode_map_objects(reader: Any, type_name: str, size: int, path: str) -> dict[str, Any]:
    """Decode only the stable model raw bytes needed for custom storage labels."""
    from palworld_save_tools.rawdata import map_model

    if type_name != "ArrayProperty":
        raise ValueError(f"Expected ArrayProperty, got {type_name}")
    value = reader.property(type_name, size, path, nested_caller_path=path)
    for map_object in value["value"]["values"]:
        raw = map_object["Model"]["value"]["RawData"]
        raw["value"] = map_model.decode_bytes(reader, raw["value"]["values"])
    return value


def encode_map_objects(writer: Any, property_type: str, properties: dict[str, Any]) -> int:
    """Re-encode model bytes while preserving all other map payloads byte-for-byte."""
    from palworld_save_tools.rawdata import map_model

    if property_type != "ArrayProperty":
        raise ValueError(f"Expected ArrayProperty, got {property_type}")
    properties.pop("custom_type", None)
    for map_object in properties["value"]["values"]:
        raw = map_object["Model"]["value"]["RawData"]
        if "values" not in raw["value"]:
            raw["value"] = {"values": list(map_model.encode_bytes(raw["value"]))}
    return writer.property_inner(property_type, properties)


def map_custom_property() -> tuple[Any, Any]:
    return decode_map_objects, encode_map_objects
