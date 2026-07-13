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
ICON_PATTERN = re.compile(
    r'<img[^>]*src="([^"]+)"[^>]*class="size64"[^>]*/></div>'
    r'<div class="flex-grow-1 mx-2"><a[^>]*>.*?</a><div>(.*?)</div>'
)

CATEGORY_LABELS = {
    "Accessory": ("饰品", "装备后提供属性、抗性或特殊效果。"),
    "Ammo": ("弹药", "供对应武器消耗的弹药类道具。"),
    "Armor": ("防具", "可装备的防护类道具。"),
    "Blueprint": ("设计图", "用于解锁或制作指定物品的设计图。"),
    "Consumable": ("消耗品", "使用后产生恢复、强化或其他即时效果。"),
    "Essential": ("重要物品", "用于系统、任务或关键功能的重要道具。"),
    "Food": ("食物", "可食用并恢复饱食度或提供附加效果。"),
    "Material": ("材料", "用于建造、制作或强化的基础材料。"),
    "PalSphere": ("帕鲁球", "用于捕捉帕鲁的球类道具。"),
    "Weapon": ("武器", "玩家可装备并用于战斗的武器。"),
}


def contains_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "PalEdit item-index updater"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def item_category(icon_url: str) -> tuple[str, str]:
    filename = icon_url.rsplit("/", 1)[-1]
    for key, value in CATEGORY_LABELS.items():
        if f"_{key}_" in filename or filename.startswith(f"T_itemicon_{key}_"):
            return value
    return "其他", "Palworld 内部道具；具体用途取决于游戏数据与当前版本。"


def parse_items(document: str) -> list[dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    icons = {
        html.unescape(re.sub(r"<[^>]+>", "", raw_id)).strip(): html.unescape(raw_icon).strip()
        for raw_icon, raw_id in ICON_PATTERN.findall(document)
    }
    for raw_name, raw_id in ITEM_PATTERN.findall(document):
        item_id = html.unescape(re.sub(r"<[^>]+>", "", raw_id)).strip()
        display_name = html.unescape(re.sub(r"<[^>]+>", "", raw_name)).strip()
        icon_url = icons.get(item_id, "")
        if not item_id or not display_name:
            continue
        category, description = item_category(icon_url)
        indexed[item_id] = {
            "id": item_id,
            "name_zh": display_name,
            "localized": contains_chinese(display_name),
            "icon_url": icon_url,
            "category": category,
            "description": description,
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
        "schema_version": 2,
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
