"""
Tests for Cerberus Heartbeat Writer
======================================
Verifies the heartbeat system works so the external watchdog
can reliably detect when Cerberus goes down.
"""

import json
import time
from pathlib import Path

import pytest

from modules.cerberus.watchdog import HeartbeatWriter


@pytest.fixture
def heartbeat(tmp_path: Path):
    """Create a HeartbeatWriter with fast interval for testing."""
    hb_path = tmp_path / "heartbeat.json"
    writer = HeartbeatWriter(heartbeat_path=hb_path, interval=0.5)
    yield writer
    if writer.is_running:
        writer.stop()


class TestHeartbeatWriter:
    def test_creates_heartbeat_file(self, heartbeat: HeartbeatWriter, tmp_path: Path):
        heartbeat.start()
        time.sleep(0.8)  # Wait for at least one write
        hb_path = tmp_path / "heartbeat.json"
        assert hb_path.exists()

    def test_heartbeat_has_required_fields(self, heartbeat: HeartbeatWriter, tmp_path: Path):
        heartbeat.start()
        time.sleep(0.8)
        hb_path = tmp_path / "heartbeat.json"
        data = json.loads(hb_path.read_text(encoding="utf-8"))
        assert "timestamp" in data
        assert "status" in data
        assert "checks_performed" in data
        assert data["status"] == "alive"

    def test_timestamp_is_recent(self, heartbeat: HeartbeatWriter, tmp_path: Path):
        heartbeat.start()
        time.sleep(0.8)
        hb_path = tmp_path / "heartbeat.json"
        data = json.loads(hb_path.read_text(encoding="utf-8"))
        age = time.time() - data["timestamp"]
        assert age < 2.0  # Should be very recent

    def test_heartbeat_updates_periodically(self, heartbeat: HeartbeatWriter, tmp_path: Path):
        heartbeat.start()
        time.sleep(0.8)
        hb_path = tmp_path / "heartbeat.json"
        first = json.loads(hb_path.read_text(encoding="utf-8"))["timestamp"]
        time.sleep(0.8)
        second = json.loads(hb_path.read_text(encoding="utf-8"))["timestamp"]
        assert second > first

    def test_stop_writes_stopped_status(self, heartbeat: HeartbeatWriter, tmp_path: Path):
        heartbeat.start()
        time.sleep(0.8)
        heartbeat.stop()
        hb_path = tmp_path / "heartbeat.json"
        data = json.loads(hb_path.read_text(encoding="utf-8"))
        assert data["status"] == "stopped"

    def test_increment_checks(self, heartbeat: HeartbeatWriter, tmp_path: Path):
        heartbeat.start()
        heartbeat.increment_checks()
        heartbeat.increment_checks()
        heartbeat.increment_checks()
        time.sleep(0.8)
        hb_path = tmp_path / "heartbeat.json"
        data = json.loads(hb_path.read_text(encoding="utf-8"))
        assert data["checks_performed"] == 3

    def test_is_running_property(self, heartbeat: HeartbeatWriter):
        assert heartbeat.is_running is False
        heartbeat.start()
        assert heartbeat.is_running is True
        heartbeat.stop()
        assert heartbeat.is_running is False

    def test_double_start_is_safe(self, heartbeat: HeartbeatWriter):
        heartbeat.start()
        heartbeat.start()  # Should not crash or create duplicate threads
        assert heartbeat.is_running is True
