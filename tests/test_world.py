import shutil
from pathlib import Path

from paledit.world import list_users, update_user

ROOT = Path(__file__).parents[1]
WORLD = next((ROOT / "Save" / "SaveGames" / "0").glob("*"))


def test_current_world_lists_real_users_and_owned_pals() -> None:
    result = list_users(WORLD)
    assert len(result["users"]) == 10
    assert all("nickname" in user and "pals" in user for user in result["users"])
    assert sum(user["pal_count"] for user in result["users"]) > 0


def test_user_update_round_trips_in_copy(tmp_path: Path) -> None:
    copied = tmp_path / "world"
    shutil.copytree(WORLD, copied, ignore=shutil.ignore_patterns("backup", "PalEdit-Backup"))
    before = list_users(copied)
    user = before["users"][0]
    new_name = f"{user['nickname']}-PalEdit测试"
    after = update_user(copied, user["player_uid"], {"nickname": new_name}, before["level_sha256"])
    changed = next(row for row in after["users"] if row["player_uid"] == user["player_uid"])
    assert changed["nickname"] == new_name
    assert Path(after["backup_path"]).is_dir()
