from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import paledit.parser as parser
from paledit.parser import WorldSnapshot, get_world_snapshot, invalidate_world_snapshot
from paledit.world import unreal_ticks_to_iso, world_snapshot_payload


ROOT = Path(__file__).parents[1]
WORLD = next(path.parent for path in (ROOT / "Save" / "SaveGames" / "0").glob("*/Level.sav"))


def test_snapshot_cache_reuses_one_decode_and_rotates_on_hash(monkeypatch, tmp_path: Path) -> None:
    level = tmp_path / "Level.sav"
    level.write_bytes(b"first-generation")
    calls: list[bytes] = []

    def fake_decode(path: Path, data: bytes) -> WorldSnapshot:
        calls.append(data)
        return WorldSnapshot(path, parser.hashlib.sha256(data).hexdigest(), object(), 0x32, data)

    monkeypatch.setattr(parser, "_decode_world_bytes", fake_decode)
    invalidate_world_snapshot()
    first = get_world_snapshot(level)
    assert get_world_snapshot(level) is first
    assert calls == [b"first-generation"]

    level.write_bytes(b"second-generation")
    second = get_world_snapshot(level)
    assert second is not first
    assert calls == [b"first-generation", b"second-generation"]


def test_snapshot_cache_serializes_concurrent_decode(monkeypatch, tmp_path: Path) -> None:
    level = tmp_path / "Level.sav"
    level.write_bytes(b"shared-generation")
    calls = 0

    def fake_decode(path: Path, data: bytes) -> WorldSnapshot:
        nonlocal calls
        calls += 1
        return WorldSnapshot(path, parser.hashlib.sha256(data).hexdigest(), object(), 0x32, data)

    monkeypatch.setattr(parser, "_decode_world_bytes", fake_decode)
    invalidate_world_snapshot()
    with ThreadPoolExecutor(max_workers=8) as executor:
        snapshots = list(executor.map(lambda _: get_world_snapshot(level), range(16)))
    assert calls == 1
    assert all(snapshot is snapshots[0] for snapshot in snapshots)


def test_explicit_invalidation_forces_fresh_decode(monkeypatch, tmp_path: Path) -> None:
    level = tmp_path / "Level.sav"
    level.write_bytes(b"same-bytes")
    calls = 0

    def fake_decode(path: Path, data: bytes) -> WorldSnapshot:
        nonlocal calls
        calls += 1
        return WorldSnapshot(path, parser.hashlib.sha256(data).hexdigest(), object(), 0x32, data)

    monkeypatch.setattr(parser, "_decode_world_bytes", fake_decode)
    invalidate_world_snapshot()
    get_world_snapshot(level)
    invalidate_world_snapshot(tmp_path)
    get_world_snapshot(level)
    assert calls == 2


def test_world_snapshot_combines_safe_read_models_without_mutating_level() -> None:
    level = WORLD / "Level.sav"
    before = level.read_bytes()
    payload = world_snapshot_payload(WORLD)
    assert payload["level_sha256"]
    assert payload["summary"]["user_count"] == len(payload["users"])
    assert payload["summary"]["container_count"] == len(payload["containers"])
    assert payload["summary"]["guild_count"] == len(payload["guilds"])
    assert payload["capabilities"]["raw_map_fallback"] is True
    assert level.read_bytes() == before


def test_unreal_ticks_exposes_iso_without_losing_raw_precision() -> None:
    assert unreal_ticks_to_iso(0) is None
    assert unreal_ticks_to_iso(621_355_968_000_000_000) == "1970-01-01T00:00:00Z"
    assert unreal_ticks_to_iso(90_000_000, 100_000_000, 1_700_000_000) == "2023-11-14T22:13:19Z"
