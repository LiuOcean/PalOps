from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent / "data" / "skills_zh_cn.json"


@lru_cache(maxsize=1)
def load_skill_index() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def search_skills(query: str = "", limit: int = 50) -> dict[str, object]:
    index = load_skill_index()
    normalized = query.strip().casefold()
    matches = []
    for skill in index["skills"]:
        searchable = " ".join(
            str(skill.get(key, "")) for key in ("skill_id", "name_zh", "description")
        ).casefold()
        if normalized and normalized not in searchable:
            continue
        matches.append(skill)
        if len(matches) >= limit:
            break
    return {
        "query": query,
        "total_skills": index["skill_count"],
        "source": index["source"],
        "results": matches,
    }
