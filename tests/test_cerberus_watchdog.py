"""Tests for the Cerberus Watchdog daemon (`daemons/cerberus_watchdog/`).

Covers the three operational paths:
  * check_heartbeat: fresh / stale / missing / corrupted
  * emergency_response: log + telegram + pkill in order
  * run: consecutive_failures threshold gates emergency
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from daemons.cerberus_watchdog.config import CerberusWatchdogSettings
from daemons.cerberus_watchdog.watchdog import (
    check_heartbeat,
    emergency_response,
    load_env,
    run,
)


# ---------------------------------------------------------------------------
# check_heartbeat
# ---------------------------------------------------------------------------


def _write_heartbeat(path: Path, age_seconds: float = 0.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.time() - age_seconds,
        "status": "alive",
        "cerberus_status": "healthy",
        "active_rules_count": 5,
        "checks_performed": 100,
    }
    path.write_text(json.dumps(payload))


def test_heartbeat_fresh(tmp_path: Path):
    hb = tmp_path / "data" / "cerberus_heartbeat.json"
    _write_heartbeat(hb, age_seconds=2.0)
    assert check_heartbeat(hb, max_age_seconds=30) is True


def test_heartbeat_stale(tmp_path: Path):
    hb = tmp_path / "data" / "cerberus_heartbeat.json"
    _write_heartbeat(hb, age_seconds=60.0)
    assert check_heartbeat(hb, max_age_seconds=30) is False


def test_heartbeat_missing(tmp_path: Path):
    hb = tmp_path / "data" / "cerberus_heartbeat.json"
    # Don't write the file.
    assert check_heartbeat(hb, max_age_seconds=30) is False


def test_heartbeat_corrupted(tmp_path: Path):
    hb = tmp_path / "data" / "cerberus_heartbeat.json"
    hb.parent.mkdir(parents=True, exist_ok=True)
    hb.write_text("{ this is not valid json")
    assert check_heartbeat(hb, max_age_seconds=30) is False


# ---------------------------------------------------------------------------
# emergency_response — order of operations
# ---------------------------------------------------------------------------


def test_emergency_response_calls_telegram_then_kill(monkeypatch, tmp_path):
    """log → telegram → pkill, in that order."""
    calls: list[str] = []

    monkeypatch.setattr(
        "daemons.cerberus_watchdog.watchdog.send_telegram_alert",
        lambda message, env: calls.append("telegram") or True,
    )
    monkeypatch.setattr(
        "daemons.cerberus_watchdog.watchdog.kill_shadow_process",
        lambda: calls.append("kill"),
    )

    emergency_response(env_path=tmp_path / ".env")
    assert calls == ["telegram", "kill"]


def test_load_env_handles_missing_file(tmp_path: Path):
    """Empty dict when .env doesn't exist — no crash."""
    assert load_env(tmp_path / ".no-such-env") == {}


def test_load_env_strips_quotes(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment\n'
        'TELEGRAM_BOT_TOKEN="abc123"\n'
        "TELEGRAM_CHAT_ID='456'\n"
        "PLAIN=value\n"
    )
    env = load_env(env_file)
    assert env["TELEGRAM_BOT_TOKEN"] == "abc123"
    assert env["TELEGRAM_CHAT_ID"] == "456"
    assert env["PLAIN"] == "value"


# ---------------------------------------------------------------------------
# run loop — consecutive failures gate
# ---------------------------------------------------------------------------


def test_run_disabled_exits_immediately(tmp_path: Path):
    settings = CerberusWatchdogSettings(
        enabled=False,
        heartbeat_path=tmp_path / "data" / "cerberus_heartbeat.json",
        env_path=tmp_path / ".env",
    )
    code = run(settings)
    assert code == 0


def test_run_emergency_after_consecutive_failures(monkeypatch, tmp_path: Path):
    """Two consecutive missing heartbeats should trigger emergency once."""
    settings = CerberusWatchdogSettings(
        enabled=True,
        heartbeat_path=tmp_path / "data" / "missing_heartbeat.json",
        env_path=tmp_path / ".env",
        check_interval_seconds=1,
        max_heartbeat_age_seconds=30,
        consecutive_failures_to_emergency=2,
        cooldown_seconds=10,
    )

    fired: list[int] = []

    def fake_emergency(env_path):
        fired.append(1)
        # Bail out after the first emergency by raising.
        raise RuntimeError("stop")

    monkeypatch.setattr(
        "daemons.cerberus_watchdog.watchdog.emergency_response",
        fake_emergency,
    )
    # Fast-forward time.sleep so the test runs in milliseconds.
    monkeypatch.setattr(
        "daemons.cerberus_watchdog.watchdog.time.sleep",
        lambda _: None,
    )

    with pytest.raises(RuntimeError, match="stop"):
        run(settings)
    assert fired == [1], "emergency must fire exactly once before our raise"
