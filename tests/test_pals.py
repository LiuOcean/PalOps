from paledit.pals import search_pals


def test_pal_index_has_palworld_1_0_character_ids() -> None:
    result = search_pals("", 1)
    assert result["total_pals"] >= 700
    assert result["localized_pals"] >= 680


def test_pal_search_supports_chinese_and_character_id() -> None:
    assert any(pal["character_id"] == "SheepBall" for pal in search_pals("棉悠悠", 10)["results"])
    assert any(pal["name_zh"] == "枯星龙" for pal in search_pals("WorldTreeDragon", 10)["results"])
