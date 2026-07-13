from paledit.compat import install_palworld_1_0_property_support


def test_int64_map_values_round_trip() -> None:
    from palworld_save_tools.archive import FArchiveReader, FArchiveWriter

    install_palworld_1_0_property_support()
    expected = 1_725_000_000_123
    writer = FArchiveWriter()
    writer.prop_value("Int64Property", "", expected)

    reader = FArchiveReader(writer.bytes())
    assert reader.prop_value(
        "Int64Property",
        "",
        ".worldSaveData.LevelObjectRecoverPartySaveData.Value.PlayerLastUsedTimes.Value",
    ) == expected
