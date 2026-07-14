from paledit import remote


class _Connection:
    def __enter__(self) -> "_Connection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_measure_server_latency_uses_direct_server_connection(monkeypatch) -> None:
    calls: list[tuple[tuple[str, int], int]] = []
    clock = iter((10.0, 10.0123))

    monkeypatch.setattr(remote, "_remote_hostname", lambda: "192.0.2.10")
    monkeypatch.setattr(remote.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(
        remote.socket,
        "create_connection",
        lambda address, timeout: calls.append((address, timeout)) or _Connection(),
    )

    assert remote.measure_server_latency() == 12.3
    assert calls == [(('192.0.2.10', remote.RCON_PORT), 3)]
