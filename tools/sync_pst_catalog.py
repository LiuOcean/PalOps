#!/usr/bin/env python3
"""Merge pinned palworld-server-tool data and icons into PalEdit's catalogs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

UPSTREAM_REPOSITORY = "https://github.com/zaigie/palworld-server-tool"
UPSTREAM_COMMIT = "18df587bd9e62d0f890b8cef1c32985fa6e9ba39"
UPSTREAM_FILES = {
    "items": "web/src/assets/items.json",
    "item_icons": "web/src/assets/items",
    "pals": "web/src/assets/pal.json",
    "pal_icons": "web/src/assets/pals",
    "skills": "web/src/assets/skill.json",
    "license": "LICENSE",
    "notice": "NOTICE",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def contains_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def run_git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"},
    )
    return result.stdout.strip()


def checkout_upstream(destination: Path) -> Path:
    run_git("init", "--quiet", str(destination))
    run_git("remote", "add", "origin", UPSTREAM_REPOSITORY, cwd=destination)
    run_git("fetch", "--quiet", "--depth", "1", "origin", UPSTREAM_COMMIT, cwd=destination)
    run_git("checkout", "--quiet", "--detach", "FETCH_HEAD", cwd=destination)
    return destination


def validate_source(source: Path) -> str:
    revision = run_git("rev-parse", "HEAD", cwd=source)
    if revision != UPSTREAM_COMMIT:
        raise RuntimeError(
            f"上游目录当前提交为 {revision}，预期固定提交 {UPSTREAM_COMMIT}"
        )
    for relative in UPSTREAM_FILES.values():
        if not (source / relative).exists():
            raise RuntimeError(f"上游目录缺少 {relative}")
    return run_git("show", "-s", "--format=%cI", UPSTREAM_COMMIT, cwd=source)


def sync_managed_assets(source: Path, destination: Path, suffix: str) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    source_files = {path.name: path for path in source.iterdir() if path.suffix == suffix}
    for stale in destination.iterdir():
        if stale.is_file() and stale.suffix == suffix and stale.name not in source_files:
            stale.unlink()
    for name, path in source_files.items():
        shutil.copy2(path, destination / name)
    return len(source_files)


def merge_items(repo_root: Path, source: Path, generated_at: str) -> dict[str, Any]:
    target = repo_root / "src/paledit/data/items_zh_cn.json"
    current = read_json(target)
    upstream_rows = read_json(source / UPSTREAM_FILES["items"])["zh"]
    upstream = {str(row["key"]): row for row in upstream_rows}
    local_icon_count = 0
    items: list[dict[str, Any]] = []
    for existing in current["items"]:
        item = dict(existing)
        row = upstream.get(str(item["id"]))
        if row:
            description = str(row.get("description") or "").strip()
            if description:
                item["description"] = description
            item["icon_url"] = f"/assets/catalog/items/{row['id']}.webp"
            item["asset_id"] = row["id"]
            item["enriched"] = True
            local_icon_count += 1
        else:
            item["enriched"] = False
        items.append(item)
    payload = {
        **{key: value for key, value in current.items() if key != "items"},
        "schema_version": 3,
        "generated_at": generated_at,
        "enrichment_source": {
            "repository": UPSTREAM_REPOSITORY,
            "commit": UPSTREAM_COMMIT,
            "data_file": UPSTREAM_FILES["items"],
            "license": "Apache-2.0",
        },
        "item_count": len(items),
        "localized_count": sum(bool(item["localized"]) for item in items),
        "local_icon_count": local_icon_count,
        "items": items,
    }
    write_json(target, payload)
    return payload


def merge_pals(repo_root: Path, source: Path, generated_at: str) -> dict[str, Any]:
    target = repo_root / "src/paledit/data/pals_zh_cn.json"
    current = read_json(target)
    current_rows = {str(row["character_id"]): row for row in current["pals"]}
    upstream_rows: dict[str, str] = read_json(source / UPSTREAM_FILES["pals"])["zh"]
    upstream_icon_names = {
        path.name for path in (source / UPSTREAM_FILES["pal_icons"]).glob("*.png")
    }
    pals: list[dict[str, Any]] = []
    for character_id, upstream_name in upstream_rows.items():
        existing = current_rows.get(character_id, {})
        name = str(existing.get("name_zh") or upstream_name)
        icon_name = f"{character_id.casefold()}.png"
        icon_url = f"/assets/catalog/pals/{icon_name}" if icon_name in upstream_icon_names else ""
        pals.append(
            {
                "character_id": character_id,
                "name_zh": name,
                "localized": contains_chinese(name),
                "icon_url": icon_url,
                "enriched": True,
            }
        )
    for character_id, existing in current_rows.items():
        if character_id not in upstream_rows:
            pals.append({**existing, "enriched": False})
    pals.sort(key=lambda pal: str(pal["character_id"]).casefold())
    payload = {
        **{key: value for key, value in current.items() if key != "pals"},
        "schema_version": 2,
        "generated_at": generated_at,
        "enrichment_source": {
            "repository": UPSTREAM_REPOSITORY,
            "commit": UPSTREAM_COMMIT,
            "data_file": UPSTREAM_FILES["pals"],
            "license": "Apache-2.0",
        },
        "pal_count": len(pals),
        "localized_count": sum(bool(pal["localized"]) for pal in pals),
        "local_icon_count": sum(bool(pal.get("icon_url")) for pal in pals),
        "pals": pals,
    }
    write_json(target, payload)
    return payload


def build_skills(repo_root: Path, source: Path, generated_at: str) -> dict[str, Any]:
    upstream_rows: dict[str, dict[str, str]] = read_json(source / UPSTREAM_FILES["skills"])["zh"]
    skills = [
        {
            "skill_id": skill_id,
            "name_zh": row["name"],
            "description": row.get("desc", ""),
        }
        for skill_id, row in sorted(upstream_rows.items(), key=lambda pair: pair[0].casefold())
    ]
    payload = {
        "schema_version": 1,
        "source": {
            "repository": UPSTREAM_REPOSITORY,
            "commit": UPSTREAM_COMMIT,
            "data_file": UPSTREAM_FILES["skills"],
            "license": "Apache-2.0",
        },
        "generated_at": generated_at,
        "skill_count": len(skills),
        "skills": skills,
    }
    write_json(repo_root / "src/paledit/data/skills_zh_cn.json", payload)
    return payload


def sync(repo_root: Path, source: Path) -> None:
    generated_at = validate_source(source)
    catalog_root = repo_root / "src/paledit/static/catalog"
    shutil.copy2(source / UPSTREAM_FILES["license"], catalog_root / "LICENSE.palworld-server-tool.txt")
    shutil.copy2(source / UPSTREAM_FILES["notice"], catalog_root / "NOTICE.palworld-server-tool.txt")
    item_assets = sync_managed_assets(
        source / UPSTREAM_FILES["item_icons"],
        repo_root / "src/paledit/static/catalog/items",
        ".webp",
    )
    pal_assets = sync_managed_assets(
        source / UPSTREAM_FILES["pal_icons"],
        repo_root / "src/paledit/static/catalog/pals",
        ".png",
    )
    items = merge_items(repo_root, source, generated_at)
    pals = merge_pals(repo_root, source, generated_at)
    skills = build_skills(repo_root, source, generated_at)
    print(
        "synced "
        f"{items['item_count']} items ({items['local_icon_count']} linked, {item_assets} assets), "
        f"{pals['pal_count']} pals ({pal_assets} assets), "
        f"and {skills['skill_count']} passive skills from {UPSTREAM_COMMIT}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        help="已检出的上游仓库；必须正好位于固定提交",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    if args.source:
        sync(repo_root, args.source.expanduser().resolve())
        return
    with tempfile.TemporaryDirectory(prefix="paledit-pst-") as directory:
        sync(repo_root, checkout_upstream(Path(directory)))


if __name__ == "__main__":
    main()
