from pathlib import Path

from paledit.map import LANDSCAPE, TILE_CONFIG, get_map_config, load_map_points


TILE_ROOT = Path(__file__).parents[1] / "src/paledit/static/map/tiles"


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
    assert result["tiles"] == TILE_CONFIG
    assert result["tiles"]["native_resolution"] == 16_384
    assert result["player_position_source"] == "Palworld REST /v1/api/players"
    assert "players" not in result


def test_high_resolution_tile_pyramid_is_complete() -> None:
    tiles = list(TILE_ROOT.glob("*/*/*.png"))
    assert len(tiles) == TILE_CONFIG["tile_count"]
    assert {int(path.relative_to(TILE_ROOT).parts[0]) for path in tiles} == set(range(7))
    assert (TILE_ROOT / "6/32/32.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
