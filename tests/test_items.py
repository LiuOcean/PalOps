from paledit.items import get_item, search_items


def test_item_index_has_current_large_dataset() -> None:
    result = search_items("", 1)
    assert result["total_items"] >= 2400
    assert result["localized_items"] >= 2200


def test_item_search_supports_chinese_and_internal_id() -> None:
    chinese = search_items("突击步枪", 10)
    assert any(item["id"] == "AssaultRifle_Default1" for item in chinese["results"])
    by_id = get_item("Money")
    assert by_id is not None
    assert by_id["name_zh"] == "金币"
    assert by_id["icon_url"] == "/assets/catalog/items/money.webp"
    assert by_id["category"]
    assert "帕洛斯群岛" in str(by_id["description"])
    assert by_id["enriched"] is True
