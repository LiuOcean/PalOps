from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent / "data" / "pals_zh_cn.json"


@lru_cache(maxsize=1)
def load_pal_index() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_pal_lookup() -> dict[str, dict[str, object]]:
    return {
        str(pal["character_id"]).casefold(): pal for pal in load_pal_index()["pals"]
    }


def get_pal(character_id: str) -> dict[str, object] | None:
    return load_pal_lookup().get(character_id.casefold())


def search_pals(query: str = "", limit: int = 50) -> dict[str, object]:
    index = load_pal_index()
    normalized = query.strip().casefold()
    matches = []
    for pal in index["pals"]:
        character_id = str(pal["character_id"])
        name = str(pal["name_zh"])
        if normalized and normalized not in character_id.casefold() and normalized not in name.casefold():
            continue
        matches.append(pal)
        if len(matches) >= limit:
            break
    return {
        "query": query,
        "total_pals": index["pal_count"],
        "localized_pals": index["localized_count"],
        "source": index["source"],
        "results": matches,
    }
