from paledit.map import LANDSCAPE, get_map_config, load_map_points


def test_map_points_are_inside_supported_landscape() -> None:
    points = load_map_points()
    assert len(points["fast_travel"]) == 82
    assert len(points["boss_tower"]) == 7
    for layer in points.values():
        assert all(LANDSCAPE["min_x"] <= x <= LANDSCAPE["max_x"] for x, _ in layer)
        assert all(LANDSCAPE["min_y"] <= y <= LANDSCAPE["max_y"] for _, y in layer)


def test_map_config_contains_only_static_geometry() -> None:
    result = get_map_config()

    assert result["fast_travel_count"] == 82
    assert result["boss_tower_count"] == 7
    assert result["boss_tower"] == load_map_points()["boss_tower"]
    assert result["landscape"] == LANDSCAPE
    assert result["player_position_source"] == "Palworld REST /v1/api/players"
    assert "players" not in result
