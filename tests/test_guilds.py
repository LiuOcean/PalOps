from palworld_save_tools.archive import FArchiveWriter, instance_id_writer, uuid_writer
from uuid import UUID

from paledit.world import decode_base_camp_raw, decode_guild_raw


GUILD_ID = str(UUID(int=1))
ADMIN_UID = str(UUID(int=2))
MEMBER_UID = str(UUID(int=3))
BASE_ID = str(UUID(int=4))


def guild_payload(name: str = "测试公会") -> bytes:
    writer = FArchiveWriter()
    writer.guid(GUILD_ID)
    writer.fstring(ADMIN_UID.replace("-", "").upper())
    writer.tarray(instance_id_writer, [])
    writer.byte(0)
    writer.write(b"\x00" * 4)
    writer.tarray(uuid_writer, [BASE_ID])
    writer.i32(0)
    writer.i32(24)
    writer.tarray(uuid_writer, [])
    writer.fstring(name)
    writer.guid(ADMIN_UID)
    writer.write(b"\x00" * 4)
    writer.write(b"\x02\x00\x00\x00\x02\x03\x00\x00\x00\x00")
    writer.guid(ADMIN_UID)
    writer.i32(2)
    for uid, nickname, flag in (
        (ADMIN_UID, "测试会长", 1),
        (MEMBER_UID, "测试成员", 2),
    ):
        writer.guid(uid)
        writer.i64(123456789)
        writer.fstring(nickname)
        writer.byte(flag)
    writer.write(b"future-tail")
    return writer.bytes()


def base_camp_payload() -> bytes:
    writer = FArchiveWriter()
    transform = {
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        "translation": {"x": -345757.7, "y": 263384.5, "z": 4067.9},
        "scale3d": {"x": 1.0, "y": 1.0, "z": 1.0},
    }
    writer.guid(BASE_ID)
    writer.fstring("新規生成拠点テンプレート名7(仮)")
    writer.byte(1)
    writer.ftransform(transform)
    writer.float(3500.0)
    writer.guid(GUILD_ID)
    writer.ftransform(transform)
    writer.guid(str(UUID(int=5)))
    writer.write(b"\x00\x00\x00\x00")
    return writer.bytes()


def test_decode_guild_raw_exposes_members_leader_and_base_ids() -> None:
    guild = decode_guild_raw(guild_payload(), "EPalGroupType::Guild")

    assert guild is not None
    assert guild["guild_id"] == GUILD_ID
    assert guild["display_name"] == "测试公会"
    assert guild["base_camp_level"] == 24
    assert guild["admin_player_uid"] == ADMIN_UID
    assert guild["member_count"] == 2
    assert guild["players"][1]["player_uid"] == MEMBER_UID
    assert guild["players"][1]["last_online_ticks"] == 123456789
    assert guild["players"][1]["last_online"].endswith("Z")
    assert guild["base_ids"] == [BASE_ID]
    assert guild["members_decoded"] is True


def test_decode_guild_raw_localizes_unnamed_guild() -> None:
    guild = decode_guild_raw(guild_payload("Unnamed Guild"), "EPalGroupType::Guild")

    assert guild is not None
    assert guild["is_unnamed"] is True
    assert guild["display_name"] == "无名公会 · 测试会长"
    assert decode_guild_raw(guild_payload(), "EPalGroupType::Organization") is None


def test_decode_base_camp_raw_exposes_owner_and_world_position() -> None:
    base = decode_base_camp_raw(base_camp_payload())

    assert base["base_id"] == BASE_ID
    assert base["group_id"] == GUILD_ID
    assert base["state"] == 1
    assert base["area_range"] == 3500.0
    assert round(base["location"]["x"], 1) == -345757.7
    assert round(base["location"]["y"], 1) == 263384.5
