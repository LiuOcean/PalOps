from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent / "data" / "items_zh_cn.json"


@lru_cache(maxsize=1)
def load_item_index() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def search_items(query: str = "", limit: int = 50) -> dict[str, object]:
    index = load_item_index()
    normalized = query.strip().casefold()
    matches = []
    for item in index["items"]:
        item_id = str(item["id"])
        name = str(item["name_zh"])
        if normalized and normalized not in item_id.casefold() and normalized not in name.casefold():
            continue
        matches.append(item)
        if len(matches) >= limit:
            break
    return {
        "query": query,
        "total_items": index["item_count"],
        "localized_items": index["localized_count"],
        "source": index["source"],
        "results": matches,
    }


def get_item(item_id: str) -> dict[str, object] | None:
    index = load_item_index()
    return next((item for item in index["items"] if item["id"] == item_id), None)
