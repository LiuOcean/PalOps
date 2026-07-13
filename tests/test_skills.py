from paledit.skills import search_skills


def test_skill_index_has_current_passive_skills() -> None:
    result = search_skills("", 1)
    assert result["total_skills"] >= 110


def test_skill_searches_id_name_and_description() -> None:
    by_id = search_skills("WorldTree_ATK", 10)["results"]
    assert by_id[0]["name_zh"] == "双刃圣剑"
    assert "攻击+50%" in by_id[0]["description"]
    assert any(skill["skill_id"] == "WorldTree_ATK" for skill in search_skills("世界树区域", 20)["results"])
