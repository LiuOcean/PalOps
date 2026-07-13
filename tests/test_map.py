from paledit.map import LANDSCAPE, get_map_config, load_map_points


def test_map_points_are_inside_supported_landscape() -> None:
    points = load_map_points()["fast_travel"]
    assert len(points) == 82
    assert all(LANDSCAPE["min_x"] <= x <= LANDSCAPE["max_x"] for x, _ in points)
    assert all(LANDSCAPE["min_y"] <= y <= LANDSCAPE["max_y"] for _, y in points)


def test_map_config_contains_only_static_geometry() -> None:
    result = get_map_config()

    assert result["fast_travel_count"] == 82
    assert result["landscape"] == LANDSCAPE
    assert result["player_position_source"] == "Palworld REST /v1/api/players"
    assert "players" not in result
