from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent / "data" / "items_zh_cn.json"


@lru_cache(maxsize=1)
def load_item_index() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def search_items(
    query: str = "",
    limit: int = 50,
    offset: int = 0,
    categories: list[str] | None = None,
) -> dict[str, object]:
    index = load_item_index()
    normalized = query.strip().casefold()
    selected_categories = {category for category in categories or [] if category}
    category_counts: dict[str, int] = {}
    matches = []
    for item in index["items"]:
        item_id = str(item["id"])
        name = str(item["name_zh"])
        category = str(item["category"])
        category_counts[category] = category_counts.get(category, 0) + 1
        if selected_categories and category not in selected_categories:
            continue
        if normalized and normalized not in item_id.casefold() and normalized not in name.casefold():
            continue
        matches.append(item)
    return {
        "query": query,
        "total_items": index["item_count"],
        "localized_items": index["localized_count"],
        "match_count": len(matches),
        "offset": offset,
        "categories": [
            {"name": category, "count": count}
            for category, count in sorted(
                category_counts.items(), key=lambda entry: (-entry[1], entry[0])
            )
        ],
        "selected_categories": sorted(selected_categories),
        "source": index["source"],
        "results": matches[offset:offset + limit],
    }


def get_item(item_id: str) -> dict[str, object] | None:
    index = load_item_index()
    return next((item for item in index["items"] if item["id"] == item_id), None)
