import subprocess

import pytest

from paledit import remote
from paledit.settings import AppSettings


def test_measure_server_latency_uses_configured_public_host(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(
        remote,
        "load_settings",
        lambda: AppSettings(public_access_host="play.example.com"),
    )
    monkeypatch.setattr(
        remote.subprocess,
        "run",
        lambda command, **_kwargs: calls.append(command) or subprocess.CompletedProcess(command, 0, "64 bytes time=12.34 ms\n", ""),
    )

    assert remote.measure_server_latency() == 12.3
    assert calls == [["ping", "-n", "-c", "1", "play.example.com"]]


def test_measure_server_latency_requires_public_access_host(monkeypatch) -> None:
    monkeypatch.setattr(remote, "load_settings", AppSettings)

    with pytest.raises(RuntimeError, match="公网访问地址"):
        remote.measure_server_latency()


def test_measure_server_latency_rejects_failed_ping(monkeypatch) -> None:
    monkeypatch.setattr(remote, "load_settings", lambda: AppSettings(public_access_host="play.example.com"))
    monkeypatch.setattr(
        remote.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 1, "", "request timeout"),
    )

    with pytest.raises(RuntimeError, match="无法通过公网地址"):
        remote.measure_server_latency()
