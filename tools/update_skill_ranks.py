#!/usr/bin/env python3
"""Enrich PalEdit's passive-skill catalog with the game's displayed rank."""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

SOURCE_URL = "https://paldb.cc/cn/Passive_Skills"
PRIMARY_SECTION = '<div id="帕鲁被动技能"'
SECONDARY_SECTION = '<div id="Pal被动技能"'
END_SECTION = '<div id="PassiveSkills"'
RANK_PATTERN = re.compile(
    r'<div class="passive-rank(-?\d+) ps-2 py-1">(.*?)</div>', re.DOTALL
)


def download(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "PalEdit passive-skill-rank updater"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_section(
    document: str, start: str, end: str, *, reject_conflicts: bool = True
) -> dict[str, int]:
    start_index = document.index(start)
    end_index = document.index(end, start_index)
    ranks: dict[str, int] = {}
    ambiguous: set[str] = set()
    for raw_rank, raw_name in RANK_PATTERN.findall(document[start_index:end_index]):
        name = html.unescape(re.sub(r"<[^>]+>", "", raw_name)).strip()
        rank = int(raw_rank)
        if name in ambiguous:
            continue
        previous = ranks.get(name)
        if previous is not None and previous != rank:
            if reject_conflicts:
                raise RuntimeError(f"被动技能 {name} 同时出现品级 {previous} 和 {rank}")
            ranks.pop(name)
            ambiguous.add(name)
            continue
        ranks[name] = rank
    return ranks


def parse_skill_ranks(document: str) -> dict[str, int]:
    primary = parse_section(document, PRIMARY_SECTION, SECONDARY_SECTION)
    secondary = parse_section(
        document, SECONDARY_SECTION, END_SECTION, reject_conflicts=False
    )
    return {**secondary, **primary}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="使用已下载的 HTML，便于离线复现")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/paledit/data/skills_zh_cn.json"),
    )
    args = parser.parse_args()
    document = args.input.read_text(encoding="utf-8") if args.input else download(SOURCE_URL)
    ranks = parse_skill_ranks(document)
    payload = json.loads(args.output.read_text(encoding="utf-8"))
    missing = []
    for skill in payload["skills"]:
        rank = ranks.get(str(skill["name_zh"]))
        if rank is None:
            missing.append(f"{skill['skill_id']} ({skill['name_zh']})")
            continue
        skill["rank"] = rank
    if missing:
        raise RuntimeError("品级页缺少当前技能：" + ", ".join(missing))
    payload["schema_version"] = max(2, int(payload.get("schema_version", 1)))
    payload["rank_source"] = {
        "url": SOURCE_URL,
        "retrieved_at": datetime.now(UTC).isoformat(),
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote ranks for {len(payload['skills'])} passive skills to {args.output}")


if __name__ == "__main__":
    main()
