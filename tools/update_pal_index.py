#!/usr/bin/env python3
"""Build the Chinese CharacterID index from PalDB's current Pal table."""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

SOURCE_URL = "https://paldb.cc/cn/Pals_Table"
ROW_PATTERN = re.compile(
    r'<div class="flex-grow-1 mx-2"><a[^>]*>(.*?)</a><div>(.*?)</div>'
)


def contains_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def parse_pals(document: str) -> list[dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for raw_name, raw_id in ROW_PATTERN.findall(document):
        character_id = html.unescape(re.sub(r"<[^>]+>", "", raw_id)).strip()
        name = html.unescape(re.sub(r"<[^>]+>", "", raw_name)).strip()
        if character_id and name:
            result[character_id] = {
                "character_id": character_id,
                "name_zh": name,
                "localized": contains_chinese(name),
            }
    return sorted(result.values(), key=lambda pal: str(pal["character_id"]).casefold())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("src/paledit/data/pals_zh_cn.json"))
    args = parser.parse_args()
    if args.input:
        document = args.input.read_text(encoding="utf-8")
    else:
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "PalEdit pal-index updater"})
        with urllib.request.urlopen(request, timeout=30) as response:
            document = response.read().decode("utf-8")
    pals = parse_pals(document)
    if len(pals) < 500:
        raise RuntimeError(f"只解析到 {len(pals)} 个 CharacterID，拒绝覆盖已有索引")
    payload = {
        "schema_version": 1,
        "source": SOURCE_URL,
        "source_table": "Pal/Content/Pal/DataTable/Character/DT_PalMonsterParameter.uasset",
        "generated_at": datetime.now(UTC).isoformat(),
        "pal_count": len(pals),
        "localized_count": sum(bool(pal["localized"]) for pal in pals),
        "pals": pals,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(pals)} CharacterIDs to {args.output}")


if __name__ == "__main__":
    main()
