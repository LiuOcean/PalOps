from uuid import UUID

import pytest

from paledit.pal_clone import ZERO_GUID, _add_guild_handles, _clone_pal_records


OWNER = "11111111-1111-1111-1111-111111111111"
SOURCE = "22222222-2222-2222-2222-222222222222"
CONTAINER = "33333333-3333-3333-3333-333333333333"


def prop(value):
    return {"value": value}


def guid(value):
    return {"value": {"value": value}}


def fixture_records(capacity: int = 4):
    entity = {
        "key": {"InstanceId": guid(SOURCE), "PlayerUId": guid(OWNER)},
        "value": {
            "RawData": {
                "value": {
                    "object": {
                        "SaveParameter": {
                            "value": {
                                "OwnerPlayerUId": guid(OWNER),
                                "CharacterID": prop("LegendDeer"),
                                "SlotId": {
                                    "value": {
                                        "ContainerId": {"value": {"ID": guid(CONTAINER)}},
                                        "SlotIndex": prop(0),
                                    }
                                },
                            }
                        }
                    }
                }
            }
        },
    }
    slot = {
        "SlotIndex": prop(0),
        "RawData": {
            "value": {
                "player_uid": OWNER,
                "instance_id": SOURCE,
                "permission_tribe_id": 0,
            }
        }
    }
    container = {
        "key": {"ID": guid(CONTAINER)},
        "value": {
            "SlotNum": prop(capacity),
            "Slots": {"value": {"values": [slot]}},
        }
    }
    return [entity], container


def test_clone_pal_records_assigns_unique_ids_and_empty_slots() -> None:
    entities, container = fixture_records()
    generated = iter([
        UUID("44444444-4444-4444-4444-444444444444"),
        UUID("55555555-5555-5555-5555-555555555555"),
    ])

    created = _clone_pal_records(
        entities,
        container,
        owner_player_uid=OWNER,
        source_instance_id=SOURCE,
        count=2,
        id_factory=lambda: next(generated),
    )

    assert [row["slot_index"] for row in created] == [1, 2]
    assert len(entities) == 3
    assert len(container["value"]["Slots"]["value"]["values"]) == 3
    first_clone = entities[1]["value"]["RawData"]["value"]["object"]["SaveParameter"]["value"]
    assert first_clone["CharacterID"]["value"] == "LegendDeer"
    assert first_clone["SlotId"]["value"]["SlotIndex"]["value"] == 1
    assert container["value"]["Slots"]["value"]["values"][1]["RawData"]["value"]["instance_id"] == created[0]["instance_id"]
    assert entities[1]["key"]["PlayerUId"]["value"]["value"] == ZERO_GUID


def test_clone_pal_records_rejects_insufficient_space() -> None:
    entities, container = fixture_records(capacity=1)
    with pytest.raises(ValueError, match="空槽不足"):
        _clone_pal_records(
            entities,
            container,
            owner_player_uid=OWNER,
            source_instance_id=SOURCE,
            count=1,
        )
