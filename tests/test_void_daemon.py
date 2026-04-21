"""Tests for the Void daemon (`daemons/void/`).

Covers the four subsystems the daemon depends on plus the monitor
loop's most important invariants:

  * metrics.collect_snapshot / snapshot_to_metric_rows
  * storage.MetricStore (open, insert, prune, WAL)
  * storage.write_latest_snapshot (atomic replace)
  * thresholds.evaluate (healthy / warning / critical)
  * monitor.run (two ticks produce DB rows + latest.json)
  * monitor.run with settings.enabled=False exits immediately
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import types
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from daemons.void.config import VoidDaemonSettings, VoidThresholds
from daemons.void.metrics import collect_snapshot, snapshot_to_metric_rows
from daemons.void.monitor import _tick, run
from daemons.void.storage import MetricStore, write_latest_snapshot
from daemons.void.thresholds import evaluate


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------


def _fake_psutil(monkeypatch, *, cpu: float = 40.0, ram: float = 50.0, disk: float = 60.0):
    """Install a stub `psutil` module with deterministic values."""
    import sys

    fake = types.SimpleNamespace()
    fake.cpu_percent = lambda interval=0.1: cpu

    class _VM:
        percent = ram
        total = 128 * 1024 ** 3
        used = int(ram / 100 * 128) * 1024 ** 3

    fake.virtual_memory = lambda: _VM()

    class _DU:
        percent = disk
        total = 2 * 1024 ** 4
        used = int(disk / 100 * 2) * 1024 ** 4

    fake.disk_usage = lambda path: _DU()

    class _Proc:
        def __init__(self, pid): self.pid = pid
        def memory_info(self):
            return types.SimpleNamespace(rss=256 * 1024 ** 2)

    fake.Process = _Proc
    monkeypatch.setitem(sys.modules, "psutil", fake)


def test_metrics_collector_snapshot_shape(monkeypatch):
    _fake_psutil(monkeypatch, cpu=25.0, ram=30.0, disk=40.0)
    # GPU query shells out to nvidia-smi; stub to "unavailable" for determinism.
    monkeypatch.setattr(
        "daemons.void.metrics.query_gpu",
        lambda: {"available": False, "reason": "stubbed"},
    )

    snap = collect_snapshot()

    assert snap["cpu_percent"] == 25.0
    assert snap["ram_percent"] == 30.0
    assert snap["disk_percent"] == 40.0
    assert "timestamp" in snap
    assert snap["gpu"] == {"available": False, "reason": "stubbed"}

    rows = snapshot_to_metric_rows(snap)
    names = {r[0] for r in rows}
    # Core six metrics are always present.
    assert names.issuperset({
        "cpu_percent", "ram_percent", "ram_used_gb",
        "disk_percent", "disk_used_gb", "process_memory_mb",
    })
    # Each row is (name, value, unit, iso_timestamp)
    for name, value, unit, ts in rows:
        assert isinstance(name, str)
        assert isinstance(value, (int, float))
        assert isinstance(unit, str)
        assert ts == snap["timestamp"]


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------


def test_storage_writes_and_schema(tmp_path: Path):
    store = MetricStore(tmp_path / "t.db")
    store.open()
    try:
        ts = datetime.now().isoformat()
        store.insert_metrics([("cpu_percent", 42.0, "percent", ts)])
        assert store.row_count() == 1

        # WAL mode is enabled
        with sqlite3.connect(str(tmp_path / "t.db")) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode.lower() == "wal"
    finally:
        store.close()


def test_storage_retention_prunes_old_rows(tmp_path: Path):
    store = MetricStore(tmp_path / "t.db")
    store.open()
    try:
        now = datetime.now()
        old_ts = (now - timedelta(days=40)).isoformat()
        fresh_ts = now.isoformat()
        store.insert_metrics([
            ("cpu_percent", 10.0, "percent", old_ts),
            ("cpu_percent", 20.0, "percent", fresh_ts),
        ])
        assert store.row_count() == 2

        pruned = store.prune_older_than(retention_days=30)
        assert pruned == 1
        assert store.row_count() == 1
    finally:
        store.close()


def test_latest_snapshot_atomic_write(tmp_path: Path):
    target = tmp_path / "latest.json"
    write_latest_snapshot(target, {"cpu_percent": 42.0, "timestamp": "t"})

    assert target.exists()
    data = json.loads(target.read_text())
    assert data["cpu_percent"] == 42.0

    # No tempfile is left behind on success.
    leftovers = [p for p in tmp_path.iterdir() if p.name != "latest.json"]
    assert leftovers == []


# ---------------------------------------------------------------------------
# thresholds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cpu,ram,disk,expected_status",
    [
        (40.0, 40.0, 40.0, "healthy"),
        (85.0, 50.0, 50.0, "warning"),   # cpu crosses warning
        (97.0, 50.0, 50.0, "critical"),  # cpu crosses critical
        (50.0, 96.0, 50.0, "critical"),  # ram critical overrides ram-warning rules
    ],
)
def test_thresholds_warning_and_critical(cpu, ram, disk, expected_status):
    snap = {
        "cpu_percent": cpu,
        "ram_percent": ram,
        "disk_percent": disk,
    }
    thresholds = VoidThresholds()
    verdict = evaluate(snap, thresholds)
    assert verdict["status"] == expected_status


# ---------------------------------------------------------------------------
# monitor (integration; uses asyncio + tight tick interval)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monitor_loop_two_ticks(tmp_path: Path, monkeypatch):
    _fake_psutil(monkeypatch)
    monkeypatch.setattr(
        "daemons.void.metrics.query_gpu",
        lambda: {"available": False, "reason": "stubbed"},
    )

    settings = VoidDaemonSettings(
        enabled=True,
        poll_interval_seconds=5,   # clamped-minimum; loop exits via stop signal instead
        db_path=tmp_path / "metrics.db",
        latest_snapshot_path=tmp_path / "latest.json",
        retention_days=30,
    )

    store = MetricStore(settings.db_path)
    store.open()
    try:
        # Two ticks, then inspect DB + latest.json.
        await _tick(settings, store)
        await _tick(settings, store)
        assert store.row_count() >= 2 * 6  # 6 core metrics per tick
    finally:
        store.close()

    assert settings.latest_snapshot_path.exists()
    data = json.loads(settings.latest_snapshot_path.read_text())
    assert data["cpu_percent"] == 40.0  # from _fake_psutil default


@pytest.mark.asyncio
async def test_disabled_exits_immediately(tmp_path: Path):
    settings = VoidDaemonSettings(
        enabled=False,
        poll_interval_seconds=5,
        db_path=tmp_path / "metrics.db",
        latest_snapshot_path=tmp_path / "latest.json",
    )
    code = await asyncio.wait_for(run(settings), timeout=2.0)
    assert code == 0
    # No DB was touched.
    assert not settings.db_path.exists()
