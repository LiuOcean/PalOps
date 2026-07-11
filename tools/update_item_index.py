#!/usr/bin/env python3
"""Build the Chinese Palworld item index from PalDB's current game-data table."""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

SOURCE_URL = "https://paldb.cc/cn/Items_Table"
ITEM_PATTERN = re.compile(
    r'<div class="flex-grow-1 mx-2"><a[^>]*>(.*?)</a><div>(.*?)</div>'
)


def contains_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "PalEdit item-index updater"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_items(document: str) -> list[dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for raw_name, raw_id in ITEM_PATTERN.findall(document):
        item_id = html.unescape(re.sub(r"<[^>]+>", "", raw_id)).strip()
        display_name = html.unescape(re.sub(r"<[^>]+>", "", raw_name)).strip()
        if not item_id or not display_name:
            continue
        indexed[item_id] = {
            "id": item_id,
            "name_zh": display_name,
            "localized": contains_chinese(display_name),
        }
    return sorted(indexed.values(), key=lambda item: str(item["id"]).casefold())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="使用已下载的 HTML，便于离线复现")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/paledit/data/items_zh_cn.json"),
    )
    args = parser.parse_args()
    document = args.input.read_text(encoding="utf-8") if args.input else download(SOURCE_URL)
    items = parse_items(document)
    if len(items) < 1000:
        raise RuntimeError(f"只解析到 {len(items)} 个道具，拒绝覆盖已有索引")
    payload = {
        "schema_version": 1,
        "source": SOURCE_URL,
        "source_tables": [
            "Pal/Content/Pal/DataTable/Item/DT_ItemDataTable.uasset",
            "Pal/Content/Pal/DataAsset/Item/DA_StaticItemDataAsset.uasset",
        ],
        "generated_at": datetime.now(UTC).isoformat(),
        "item_count": len(items),
        "localized_count": sum(bool(item["localized"]) for item in items),
        "items": items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(items)} items to {args.output}")


if __name__ == "__main__":
    main()
