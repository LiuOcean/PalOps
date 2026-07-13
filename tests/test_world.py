import shutil
from pathlib import Path

from paledit.world import (
    grant_inventory_items, list_storage_containers, list_users, search_world, update_inventory_slot, update_user,
)

ROOT = Path(__file__).parents[1]
WORLD = next(path.parent for path in (ROOT / "Save" / "SaveGames" / "0").glob("*/Level.sav"))
OWNER_PLAYER_UID = "00000000-0000-0000-0000-000000000000"


def test_current_world_lists_real_users_and_owned_pals() -> None:
    result = list_users(WORLD)
    assert result["users"]
    assert any(user["player_uid"] == OWNER_PLAYER_UID for user in result["users"])
    assert all("nickname" in user and "pals" in user for user in result["users"])
    assert sum(user["pal_count"] for user in result["users"]) > 0


def test_current_world_lists_storage_containers() -> None:
    result = list_storage_containers(WORLD)
    assert result["count"] > 0
    assert all(row["container_id"] and "slots" in row for row in result["containers"])


def test_world_search_finds_items_and_pals_with_locations() -> None:
    users = list_users(WORLD)["users"]
    item = next(
        slot
        for user in users
        for slots in user["inventories"].values()
        for slot in slots
        if slot["item_id"] != "None" and slot["count"] > 0
    )
    item_result = search_world(WORLD, item["item_id"])
    assert item_result["item_match_count"] > 0
    assert all(row["location_label"] for row in item_result["results"])
    assert any(row["kind"] == "item" and row["item_id"] == item["item_id"] for row in item_result["results"])

    pal = next(pal for user in users for pal in user["pals"])
    pal_result = search_world(WORLD, pal["character_id"])
    assert pal_result["pal_match_count"] > 0
    assert any(
        row["kind"] == "pal"
        and row["character_id"] == pal["character_id"]
        and row["owner_player_uid"]
        and row["location_label"]
        for row in pal_result["results"]
    )


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


def test_inventory_count_update_round_trips_in_copy(tmp_path: Path) -> None:
    copied = tmp_path / "world"
    shutil.copytree(WORLD, copied, ignore=shutil.ignore_patterns("backup", "PalEdit-Backup"))
    before = list_users(copied)
    user = next(row for row in before["users"] if row["inventories"].get("背包"))
    slot = next(row for row in user["inventories"]["背包"] if row["item_id"] != "None")
    after = update_inventory_slot(
        copied, user["player_uid"], "背包", slot["slot_index"], slot["item_id"], slot["count"] + 1,
        before["level_sha256"],
    )
    changed_user = next(row for row in after["users"] if row["player_uid"] == user["player_uid"])
    changed_slot = next(row for row in changed_user["inventories"]["背包"] if row["slot_index"] == slot["slot_index"])
    assert changed_slot["count"] == slot["count"] + 1


def test_inventory_grant_uses_new_slots_without_replacing_items(tmp_path: Path) -> None:
    copied = tmp_path / "world"
    shutil.copytree(WORLD, copied, ignore=shutil.ignore_patterns("backup", "PalEdit-Backup"))
    before = list_users(copied)
    user = next(row for row in before["users"] if row["inventories"].get("背包"))
    original = {(row["slot_index"], row["item_id"], row["count"]) for row in user["inventories"]["背包"]}
    after = grant_inventory_items(
        copied, user["player_uid"], "背包", {"Potion_Extreme": 99}, before["level_sha256"],
    )
    changed = next(row for row in after["users"] if row["player_uid"] == user["player_uid"])
    current = {(row["slot_index"], row["item_id"], row["count"]) for row in changed["inventories"]["背包"]}
    assert original <= current
    assert any(item_id == "Potion_Extreme" and count == 99 for _, item_id, count in current)


def test_technology_points_can_be_set_to_9999(tmp_path: Path) -> None:
    copied = tmp_path / "world"
    shutil.copytree(WORLD, copied, ignore=shutil.ignore_patterns("backup", "PalEdit-Backup"))
    before = list_users(copied)
    user = before["users"][0]
    after = update_user(copied, user["player_uid"], {"technology_points": 9999}, before["level_sha256"], user["player_file_sha256"])
    changed = next(row for row in after["users"] if row["player_uid"] == user["player_uid"])
    assert changed["technology_points"] == 9999
