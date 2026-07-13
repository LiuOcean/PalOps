from pathlib import Path

from paledit.items import load_item_index
from paledit.pals import load_pal_index
from paledit.skills import load_skill_index

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src/paledit"
STATIC_ROOT = PACKAGE_ROOT / "static"
PINNED_COMMIT = "7df5ec40c5d3f3ef50200f2048dc116a0b9938bf"


def asset_path(url: str) -> Path:
    assert url.startswith("/assets/")
    return STATIC_ROOT / url.removeprefix("/assets/")


def test_catalogs_record_the_reviewed_upstream_commit() -> None:
    assert load_item_index()["enrichment_source"]["commit"] == PINNED_COMMIT
    assert load_pal_index()["enrichment_source"]["commit"] == PINNED_COMMIT
    assert load_skill_index()["source"]["commit"] == PINNED_COMMIT


def test_every_linked_local_catalog_asset_exists() -> None:
    items = load_item_index()
    local_items = [item for item in items["items"] if str(item.get("icon_url", "")).startswith("/assets/")]
    assert len(local_items) == items["local_icon_count"] >= 2450
    assert all(asset_path(str(item["icon_url"])).is_file() for item in local_items)

    pals = load_pal_index()
    local_pals = [pal for pal in pals["pals"] if pal.get("icon_url")]
    assert len(local_pals) == pals["local_icon_count"] >= 1100
    assert all(asset_path(str(pal["icon_url"])).is_file() for pal in local_pals)


def test_third_party_notice_is_shipped_with_catalog_assets() -> None:
    notice = (STATIC_ROOT / "catalog/THIRD_PARTY_NOTICE.txt").read_text(encoding="utf-8")
    assert "zaigie/palworld-server-tool" in notice
    assert PINNED_COMMIT in notice
    assert "Apache License 2.0" in notice
    assert (STATIC_ROOT / "catalog/LICENSE.palworld-server-tool.txt").is_file()
    assert (STATIC_ROOT / "catalog/NOTICE.palworld-server-tool.txt").is_file()
