from paledit.skills import describe_skills, get_skill, search_skills


def test_skill_index_has_current_passive_skills() -> None:
    result = search_skills("", 1)
    assert result["total_skills"] >= 110


def test_skill_searches_id_name_and_description() -> None:
    by_id = search_skills("WorldTree_ATK", 10)["results"]
    assert by_id[0]["name_zh"] == "双刃圣剑"
    assert "攻击+50%" in by_id[0]["description"]
    assert any(skill["skill_id"] == "WorldTree_ATK" for skill in search_skills("世界树区域", 20)["results"])


def test_skill_lookup_and_unknown_fallback() -> None:
    assert get_skill("legend")["name_zh"] == "传说"
    assert get_skill("legend")["rank"] == 4
    assert get_skill("WorldTree_ATK")["rank"] == 5
    assert get_skill("PAL_ALLAttack_down2")["rank"] == -3
    described = describe_skills(["Legend", "Future_Unknown_Skill"])
    assert described[0]["description"]
    assert described[1] == {
        "skill_id": "Future_Unknown_Skill",
        "name_zh": "Future_Unknown_Skill",
        "description": "",
        "rank": None,
    }
