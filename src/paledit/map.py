from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parent / "data" / "map_points.json"
LANDSCAPE = {
    "max_x": 447900.0,
    "max_y": 708920.0,
    "min_x": -999940.0,
    "min_y": -738920.0,
}


@lru_cache(maxsize=1)
def load_map_points() -> dict[str, list[list[float]]]:
    with DATA_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return {
        "fast_travel": [[float(x), float(y)] for x, y in payload["fast_travel"]],
        "boss_tower": [[float(x), float(y)] for x, y in payload.get("boss_tower", [])],
    }


def get_map_config() -> dict[str, object]:
    """Return static map geometry; player positions come from /api/server/players."""
    points = load_map_points()
    return {
        "landscape": LANDSCAPE,
        "fast_travel": points["fast_travel"],
        "fast_travel_count": len(points["fast_travel"]),
        "boss_tower": points["boss_tower"],
        "boss_tower_count": len(points["boss_tower"]),
        "player_position_source": "Palworld REST /v1/api/players",
    }
