from pathlib import Path

from paledit.save import discover_worlds, inspect_save

ROOT = Path(__file__).parents[1]
SAVE_ROOT = ROOT / "Save"


def test_current_level_is_palworld_1_0_oodle() -> None:
    worlds = discover_worlds(SAVE_ROOT)
    assert len(worlds) == 1
    assert worlds[0].level.magic == "PlM"
    assert worlds[0].level.format == "oodle"
    assert worlds[0].player_files == 10


def test_save_header_does_not_require_full_file_read() -> None:
    level = next((SAVE_ROOT / "SaveGames" / "0").glob("*/Level.sav"))
    info = inspect_save(level)
    assert info.size > 0
    assert info.save_type == 0x31

