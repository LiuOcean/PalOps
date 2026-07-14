from __future__ import annotations

import math
import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from statistics import fmean

from .remote import get_server_metrics, get_server_status


DEFAULT_METRICS_DB = Path.cwd() / ".paledit-data" / "metrics.sqlite3"
RETENTION_SECONDS = 7 * 24 * 60 * 60
SAMPLE_INTERVAL_SECONDS = 60
MAX_SAMPLES = RETENTION_SECONDS // SAMPLE_INTERVAL_SECONDS
_WRITE_LOCK = threading.Lock()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS server_metrics (
            sampled_at INTEGER PRIMARY KEY,
            online INTEGER NOT NULL,
            health TEXT NOT NULL,
            health_score INTEGER NOT NULL,
            latency_ms REAL,
            server_fps REAL,
            frame_time_ms REAL,
            current_players INTEGER,
            max_players INTEGER,
            uptime_seconds INTEGER,
            base_camps INTEGER,
            world_days INTEGER,
            error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_server_metrics_sampled_at
            ON server_metrics(sampled_at DESC);
        """
    )
    return connection


def calculate_health_score(
    *,
    online: bool,
    health: str,
    latency_ms: float | None,
    server_fps: float | None,
    frame_time_ms: float | None,
) -> int:
    if not online:
        return 0
    score = 100.0
    if health not in {"healthy", "unknown", ""}:
        score -= 35
    if latency_ms is not None:
        score -= min(25, max(0, latency_ms - 150) / 34)
    if server_fps is not None and server_fps < 50:
        score -= min(25, (50 - server_fps) * 1.25)
    if frame_time_ms is not None and frame_time_ms > 20:
        score -= min(25, (frame_time_ms - 20) * 1.25)
    return max(0, min(100, round(score)))


def record_server_sample(
    path: Path = DEFAULT_METRICS_DB,
    *,
    status_provider: Callable[[], dict[str, object]] = get_server_status,
    metrics_provider: Callable[[], dict[str, object]] = get_server_metrics,
    now: int | None = None,
) -> dict[str, object]:
    sampled_at = int(time.time()) if now is None else int(now)
    status: dict[str, object] = {}
    metrics: dict[str, object] = {}
    errors: list[str] = []

    try:
        status = status_provider()
    except RuntimeError as error:
        errors.append(str(error))

    latency_ms: float | None = None
    started = time.perf_counter()
    try:
        metrics = metrics_provider()
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
    except RuntimeError as error:
        errors.append(str(error))

    online = bool(status.get("online"))
    health = str(status.get("health") or "unreachable")
    server_fps = _number(metrics.get("server_fps"))
    frame_time_ms = _number(metrics.get("frame_time_ms"))
    health_score = calculate_health_score(
        online=online,
        health=health,
        latency_ms=latency_ms,
        server_fps=server_fps,
        frame_time_ms=frame_time_ms,
    )
    if online and not metrics:
        health_score = min(health_score, 55)
    row: dict[str, object] = {
        "sampled_at": sampled_at,
        "online": online,
        "health": health,
        "health_score": health_score,
        "latency_ms": latency_ms,
        "server_fps": server_fps,
        "frame_time_ms": frame_time_ms,
        "current_players": _integer(metrics.get("current_players")),
        "max_players": _integer(metrics.get("max_players")),
        "uptime_seconds": _integer(metrics.get("uptime_seconds")),
        "base_camps": _integer(metrics.get("base_camps")),
        "world_days": _integer(metrics.get("world_days")),
        "error": "；".join(errors) or None,
    }
    with _WRITE_LOCK, _connect(path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO server_metrics(
                sampled_at, online, health, health_score, latency_ms, server_fps,
                frame_time_ms, current_players, max_players, uptime_seconds,
                base_camps, world_days, error
            ) VALUES (
                :sampled_at, :online, :health, :health_score, :latency_ms, :server_fps,
                :frame_time_ms, :current_players, :max_players, :uptime_seconds,
                :base_camps, :world_days, :error
            )
            """,
            row,
        )
        connection.execute("DELETE FROM server_metrics WHERE sampled_at < ?", (sampled_at - RETENTION_SECONDS,))
        connection.execute(
            """
            DELETE FROM server_metrics WHERE sampled_at IN (
                SELECT sampled_at FROM server_metrics
                ORDER BY sampled_at DESC LIMIT -1 OFFSET ?
            )
            """,
            (MAX_SAMPLES,),
        )
    return row


def read_metrics_history(
    path: Path = DEFAULT_METRICS_DB,
    *,
    hours: int = 24,
    now: int | None = None,
    max_points: int = 720,
) -> dict[str, object]:
    current_time = int(time.time()) if now is None else int(now)
    since = current_time - hours * 60 * 60
    with _connect(path) as connection:
        rows = [dict(row) for row in connection.execute(
            "SELECT * FROM server_metrics WHERE sampled_at >= ? ORDER BY sampled_at",
            (since,),
        ).fetchall()]

    points = _downsample(rows, max_points)
    latencies = [float(row["latency_ms"]) for row in rows if row["latency_ms"] is not None]
    fps_values = [float(row["server_fps"]) for row in rows if row["server_fps"] is not None]
    availability = (sum(1 for row in rows if row["online"]) / len(rows) * 100) if rows else None
    incidents = sum(
        1 for index, row in enumerate(rows)
        if not row["online"] and (index == 0 or rows[index - 1]["online"])
    )
    latest = rows[-1] if rows else None
    return {
        "hours": hours,
        "retention_days": RETENTION_SECONDS // 86400,
        "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
        "sample_count": len(rows),
        "samples": points,
        "latest": latest,
        "summary": {
            "availability_percent": _rounded(availability),
            "average_latency_ms": _rounded(fmean(latencies) if latencies else None),
            "p95_latency_ms": _rounded(_percentile(latencies, 0.95)),
            "average_fps": _rounded(fmean(fps_values) if fps_values else None),
            "incident_count": incidents,
        },
        "database_path": str(path.resolve()),
    }


def _downsample(rows: list[dict[str, object]], max_points: int) -> list[dict[str, object]]:
    if len(rows) <= max_points:
        return rows
    bucket_size = math.ceil(len(rows) / max_points)
    result: list[dict[str, object]] = []
    numeric_keys = (
        "health_score", "latency_ms", "server_fps", "frame_time_ms",
        "current_players", "max_players", "uptime_seconds", "base_camps", "world_days",
    )
    for offset in range(0, len(rows), bucket_size):
        bucket = rows[offset:offset + bucket_size]
        point: dict[str, object] = {
            "sampled_at": bucket[-1]["sampled_at"],
            "online": any(bool(row["online"]) for row in bucket),
            "health": bucket[-1]["health"],
            "error": bucket[-1]["error"],
        }
        for key in numeric_keys:
            values = [float(row[key]) for row in bucket if row[key] is not None]
            point[key] = _rounded(fmean(values) if values else None)
        result.append(point)
    return result


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: object) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil((len(ordered) - 1) * ratio)]
