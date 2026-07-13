import struct

from paledit.parser import _container_id_prefixes, _container_matches


def _guid(seed: int) -> bytes:
    return struct.pack("<IIII", seed, seed + 1, seed + 2, seed + 3)


def test_container_match_scan_finds_unaligned_guid_once() -> None:
    encoded = _guid(10)
    prefixes = _container_id_prefixes({encoded: "container-a"})
    data = b"prefix!" + encoded + b"suffix"

    assert _container_matches(data, 0, len(data), prefixes) == {encoded: "container-a"}


def test_container_match_scan_preserves_ambiguous_match_detection() -> None:
    first = _guid(20)
    second = _guid(30)
    prefixes = _container_id_prefixes({first: "container-a", second: "container-b"})
    data = first + b"middle" + second

    assert _container_matches(data, 0, len(data), prefixes) == {
        first: "container-a",
        second: "container-b",
    }


def test_container_match_scan_respects_window_end() -> None:
    encoded = _guid(40)
    prefixes = _container_id_prefixes({encoded: "container-a"})
    data = b"prefix" + encoded

    assert _container_matches(data, 0, len(data) - 1, prefixes) == {}
