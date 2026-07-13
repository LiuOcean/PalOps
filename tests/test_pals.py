from paledit.pals import get_pal, search_pals


def test_pal_index_has_palworld_1_0_character_ids() -> None:
    result = search_pals("", 1)
    assert result["total_pals"] >= 1150
    assert result["localized_pals"] >= 1100


def test_pal_search_supports_chinese_and_character_id() -> None:
    sheep = next(pal for pal in search_pals("棉悠悠", 10)["results"] if pal["character_id"] == "SheepBall")
    assert sheep["icon_url"] == "/assets/catalog/pals/sheepball.png"
    assert any(pal["name_zh"] == "枯星龙" for pal in search_pals("WorldTreeDragon", 10)["results"])


def test_pal_lookup_accepts_save_id_case_variants() -> None:
    pal = get_pal("Sheepball")
    assert pal is not None
    assert pal["name_zh"] == "棉悠悠"
