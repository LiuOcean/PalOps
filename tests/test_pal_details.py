from paledit.world import array_values, pal_readonly_details


def test_array_values_handles_palworld_array_wrapper() -> None:
    assert array_values({"value": {"values": ["Legend", "Rare"]}}) == [
        "Legend",
        "Rare",
    ]


def test_pal_readonly_details_exposes_talents_rank_and_skills() -> None:
    details = pal_readonly_details(
        {
            "Hp": {
                "type": "StructProperty",
                "struct_type": "FixedPoint64",
                "value": {"Value": {"value": 123000}},
            },
            "Talent_HP": {"value": 91},
            "Talent_Shot": {"value": 87},
            "Talent_Defense": {"value": 76},
            "Rank": {"value": 4},
            "Rank_Attack": {"value": 20},
            "Rank_Defence": {"value": 20},
            "Rank_CraftSpeed": {"value": 20},
            "PassiveSkillList": {"value": {"values": ["Legend"]}},
        }
    )
    assert details["hp"] == 123
    assert details["talents"] == {"hp": 91, "attack": 87, "defense": 76}
    assert details["condensation_rank"] == 4
    assert details["rank_boosts"] == {
        "attack": 20,
        "defense": 20,
        "work_speed": 20,
    }
    assert details["passive_skills"][0]["name_zh"] == "传说"
