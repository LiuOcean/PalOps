from pathlib import Path

from paledit.metrics_history import MAX_SAMPLES, calculate_health_score, read_metrics_history, record_server_sample


def _status(online: bool = True) -> dict[str, object]:
    return {"online": online, "health": "healthy" if online else "unhealthy"}


def _metrics(fps: float = 60) -> dict[str, object]:
    return {
        "server_fps": fps,
        "frame_time_ms": 16.6,
        "current_players": 2,
        "max_players": 32,
        "uptime_seconds": 3600,
        "base_camps": 4,
        "world_days": 99,
    }


def test_health_score_marks_offline_as_zero_and_penalizes_degradation() -> None:
    assert calculate_health_score(online=False, health="unhealthy", latency_ms=None, server_fps=None, frame_time_ms=None) == 0
    healthy = calculate_health_score(online=True, health="healthy", latency_ms=50, server_fps=60, frame_time_ms=16)
    degraded = calculate_health_score(online=True, health="healthy", latency_ms=500, server_fps=25, frame_time_ms=40)
    assert healthy == 100
    assert 0 < degraded < healthy


def test_history_persists_samples_and_returns_summary(tmp_path: Path) -> None:
    database = tmp_path / "metrics.sqlite3"
    record_server_sample(database, status_provider=_status, metrics_provider=_metrics, now=1_000_000)
    record_server_sample(database, status_provider=lambda: _status(False), metrics_provider=lambda: _metrics(30), now=1_000_060)

    result = read_metrics_history(database, hours=1, now=1_000_120)

    assert result["sample_count"] == 2
    assert result["summary"]["availability_percent"] == 50.0
    assert result["summary"]["incident_count"] == 1
    assert result["latest"]["current_players"] == 2
    assert result["database_path"] == str(database.resolve())


def test_history_prunes_samples_older_than_seven_days(tmp_path: Path) -> None:
    database = tmp_path / "metrics.sqlite3"
    record_server_sample(database, status_provider=_status, metrics_provider=_metrics, now=1)
    current = 8 * 24 * 60 * 60
    record_server_sample(database, status_provider=_status, metrics_provider=_metrics, now=current)

    result = read_metrics_history(database, hours=168, now=current)

    assert result["sample_count"] == 1
    assert MAX_SAMPLES == 10_080


def test_history_degrades_health_when_rest_metrics_are_unavailable(tmp_path: Path) -> None:
    database = tmp_path / "metrics.sqlite3"

    def unavailable_metrics() -> dict[str, object]:
        raise RuntimeError("REST 不可达")

    sample = record_server_sample(
        database,
        status_provider=_status,
        metrics_provider=unavailable_metrics,
        now=1_000_000,
    )

    assert sample["online"] is True
    assert sample["health_score"] == 55
    assert sample["error"] == "REST 不可达"
