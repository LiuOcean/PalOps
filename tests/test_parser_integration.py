from pathlib import Path

from paledit.parser import load_character_data

ROOT = Path(__file__).parents[1]


def test_current_palworld_1_0_world_can_be_parsed() -> None:
    level = next((ROOT / "Save" / "SaveGames" / "0").glob("*/Level.sav"))
    parsed = load_character_data(level)
    assert parsed["character_count"] > 10
    assert parsed["world_property_count"] >= 20
