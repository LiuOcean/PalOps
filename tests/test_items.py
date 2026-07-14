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


def test_item_catalog_supports_browsing_past_the_first_page() -> None:
    first = search_items("", 100)
    second = search_items("", 100, 100)
    assert first["match_count"] == first["total_items"]
    assert second["offset"] == 100
    assert first["results"][-1]["id"] != second["results"][0]["id"]


def test_item_catalog_supports_multiple_category_filters() -> None:
    result = search_items("", 200, categories=["帕鲁球", "弹药"])

    assert result["selected_categories"] == ["帕鲁球", "弹药"]
    assert result["match_count"] == 46
    assert {item["category"] for item in result["results"]} == {"帕鲁球", "弹药"}
    assert {category["name"] for category in result["categories"]} >= {"材料", "武器", "防具"}


def test_item_category_filter_combines_with_search_and_paging() -> None:
    result = search_items("突击步枪", 1, categories=["武器"])

    assert result["match_count"] >= 1
    assert len(result["results"]) == 1
    assert result["results"][0]["category"] == "武器"
    assert search_items("突击步枪", 10, categories=["食物"])["match_count"] == 0
