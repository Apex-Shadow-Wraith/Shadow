"""
Tests for Cerberus Emergency Shutdown Protocol.

Covers all trigger types, Telegram notification, fallback logging,
state file management, and restart recovery.

IMPORTANT: sys.exit is ALWAYS mocked — no test actually halts.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.cerberus.emergency_shutdown import EmergencyShutdown, PROTECTED_FILES


@pytest.fixture
def tmp_data(tmp_path):
    """Provide temp paths for state/log files."""
    return {
        "shutdown_state_file": str(tmp_path / "shutdown_state.json"),
        "shutdown_history_dir": str(tmp_path / "shutdown_history"),
        "emergency_log_file": str(tmp_path / "emergency_shutdown.log"),
        "shutdown": {
            "cpu_threshold": 95,
            "memory_threshold": 90,
            "cascade_failure_window_seconds": 60,
            "cascade_failure_count": 3,
            "injection_score_threshold": 0.9,
            "blocked_attempts_window_seconds": 60,
            "blocked_attempts_count": 5,
        },
    }


@pytest.fixture
def mock_telegram():
    """Mock TelegramDelivery that succeeds."""
    tg = MagicMock()
    tg.send_alert.return_value = True
    return tg


@pytest.fixture
def mock_telegram_fail():
    """Mock TelegramDelivery that fails."""
    tg = MagicMock()
    tg.send_alert.return_value = False
    return tg


@pytest.fixture
def shutdown(tmp_data, mock_telegram):
    """EmergencyShutdown with working Telegram."""
    return EmergencyShutdown(config=tmp_data, telegram=mock_telegram)


@pytest.fixture
def shutdown_no_telegram(tmp_data):
    """EmergencyShutdown with no Telegram configured."""
    return EmergencyShutdown(config=tmp_data, telegram=None)


# ------------------------------------------------------------------
# initiate_shutdown
# ------------------------------------------------------------------


class TestInitiateShutdown:
    """Tests for the shutdown initiation flow."""

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_sys_exit_called_after_message(self, mock_exit, shutdown, mock_telegram):
        """sys.exit(1) is called, and Telegram message sent first."""
        shutdown.initiate_shutdown(
            trigger_reason="Test trigger",
            trigger_source="test_module",
            context={"current_task": "running tests"},
        )

        mock_telegram.send_alert.assert_called_once()
        mock_exit.assert_called_once_with(1)

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_telegram_called_before_exit(self, mock_exit, shutdown, mock_telegram):
        """Telegram notification happens before sys.exit."""
        call_order = []
        mock_telegram.send_alert.side_effect = lambda **kw: call_order.append("telegram") or True
        mock_exit.side_effect = lambda code: call_order.append("exit")

        shutdown.initiate_shutdown(
            trigger_reason="Order test",
            trigger_source="test",
            context={},
        )

        assert call_order == ["telegram", "exit"]

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_telegram_message_contains_trigger_info(self, mock_exit, shutdown, mock_telegram):
        """Emergency message includes trigger reason, source, and task."""
        shutdown.initiate_shutdown(
            trigger_reason="CPU at 99%",
            trigger_source="void",
            context={"current_task": "web scraping", "risk_assessment": "high"},
        )

        call_args = mock_telegram.send_alert.call_args
        message = call_args.kwargs.get("message") or call_args[1].get("message", call_args[0][0] if call_args[0] else "")
        assert "CPU at 99%" in message
        assert "void" in message
        assert "web scraping" in message

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_telegram_failure_writes_local_log(self, mock_exit, tmp_data, mock_telegram_fail):
        """When Telegram fails, emergency log file is written."""
        es = EmergencyShutdown(config=tmp_data, telegram=mock_telegram_fail)
        es.initiate_shutdown(
            trigger_reason="Security breach",
            trigger_source="cerberus",
            context={"current_task": "idle"},
        )

        log_path = Path(tmp_data["emergency_log_file"])
        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "Security breach" in content
        assert "EMERGENCY SHUTDOWN" in content

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_no_telegram_writes_local_log(self, mock_exit, shutdown_no_telegram, tmp_data):
        """With no Telegram configured, local log is written."""
        shutdown_no_telegram.initiate_shutdown(
            trigger_reason="No telegram test",
            trigger_source="test",
            context={},
        )

        log_path = Path(tmp_data["emergency_log_file"])
        assert log_path.exists()

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_state_file_written(self, mock_exit, shutdown, tmp_data):
        """Shutdown state file is written with full context."""
        context = {
            "current_task": "processing query",
            "module_states": {"wraith": "online", "reaper": "error"},
            "risk_assessment": "critical",
        }
        shutdown.initiate_shutdown(
            trigger_reason="Cascade failure",
            trigger_source="shadow_orchestrator",
            context=context,
        )

        state_path = Path(tmp_data["shutdown_state_file"])
        assert state_path.exists()

        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["trigger_reason"] == "Cascade failure"
        assert state["trigger_source"] == "shadow_orchestrator"
        assert state["context"]["current_task"] == "processing query"
        assert state["context"]["module_states"]["reaper"] == "error"
        assert "timestamp" in state
        assert "telegram_notified" in state

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_telegram_exception_falls_back_to_log(self, mock_exit, tmp_data):
        """If Telegram raises an exception, fall back to local log."""
        bad_telegram = MagicMock()
        bad_telegram.send_alert.side_effect = Exception("Connection refused")

        es = EmergencyShutdown(config=tmp_data, telegram=bad_telegram)
        es.initiate_shutdown(
            trigger_reason="Exception test",
            trigger_source="test",
            context={},
        )

        log_path = Path(tmp_data["emergency_log_file"])
        assert log_path.exists()
        mock_exit.assert_called_once_with(1)


# ------------------------------------------------------------------
# check_shutdown_triggers
# ------------------------------------------------------------------


class TestCheckShutdownTriggers:
    """Tests for trigger evaluation logic."""

    def test_safe_state_returns_none(self, shutdown):
        """Normal system state returns None (no shutdown)."""
        state = {"cpu_percent": 50, "memory_percent": 60}
        assert shutdown.check_shutdown_triggers(state) is None

    def test_cpu_threshold_triggers(self, shutdown):
        """CPU exceeding threshold triggers shutdown."""
        state = {"cpu_percent": 98}
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "CPU" in result
        assert "98" in result

    def test_memory_threshold_triggers(self, shutdown):
        """Memory exceeding threshold triggers shutdown."""
        state = {"memory_percent": 95}
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "Memory" in result
        assert "95" in result

    def test_injection_score_triggers(self, shutdown):
        """High injection score triggers shutdown."""
        state = {
            "injection_results": [{"score": 0.95, "description": "SQL injection"}],
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "Injection score" in result

    def test_injection_below_threshold_safe(self, shutdown):
        """Injection score below threshold is safe."""
        state = {
            "injection_results": [{"score": 0.5}],
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_blocked_attempts_triggers(self, shutdown):
        """Multiple blocked attempts in window triggers shutdown."""
        now = time.time()
        state = {
            "blocked_attempts": [
                {"timestamp": now - 10, "type": "injection"},
                {"timestamp": now - 8, "type": "injection"},
                {"timestamp": now - 5, "type": "shell_metachar"},
                {"timestamp": now - 3, "type": "protected_path"},
                {"timestamp": now - 1, "type": "injection"},
            ],
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "blocked attempts" in result

    def test_blocked_attempts_outside_window_safe(self, shutdown):
        """Old blocked attempts outside window are safe."""
        now = time.time()
        state = {
            "blocked_attempts": [
                {"timestamp": now - 120, "type": "injection"},
                {"timestamp": now - 130, "type": "injection"},
                {"timestamp": now - 140, "type": "injection"},
                {"timestamp": now - 150, "type": "injection"},
                {"timestamp": now - 160, "type": "injection"},
            ],
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_cascading_failures_triggers(self, shutdown):
        """3+ modules erroring within window triggers shutdown."""
        now = time.time()
        state = {
            "module_errors": [
                {"module": "wraith", "error": "timeout", "timestamp": now - 5},
                {"module": "reaper", "error": "crash", "timestamp": now - 3},
                {"module": "cipher", "error": "OOM", "timestamp": now - 1},
            ],
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "Cascading failures" in result
        assert "3" in result

    def test_two_module_errors_safe(self, shutdown):
        """Only 2 modules erroring is below threshold."""
        now = time.time()
        state = {
            "module_errors": [
                {"module": "wraith", "error": "timeout", "timestamp": now - 5},
                {"module": "reaper", "error": "crash", "timestamp": now - 3},
            ],
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_self_modification_cerberus_config(self, shutdown):
        """Module modifying cerberus_limits.yaml triggers shutdown."""
        state = {
            "file_modifications": [
                {"path": "config/cerberus_limits.yaml", "source": "omen"},
            ],
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "Self-modification" in result
        assert "omen" in result

    def test_self_modification_cerberus_code(self, shutdown):
        """Module modifying cerberus.py triggers shutdown."""
        state = {
            "file_modifications": [
                {"path": "modules/cerberus/cerberus.py", "source": "morpheus"},
            ],
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "Self-modification" in result

    def test_self_modification_windows_paths(self, shutdown):
        """Windows-style backslash paths still detected."""
        state = {
            "file_modifications": [
                {"path": "modules\\cerberus\\watchdog.py", "source": "wraith"},
            ],
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "Self-modification" in result

    def test_non_protected_file_safe(self, shutdown):
        """Modifying non-protected files is fine."""
        state = {
            "file_modifications": [
                {"path": "modules/wraith/wraith.py", "source": "omen"},
            ],
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_executed_injection_triggers(self, shutdown):
        """Injection that already executed triggers shutdown."""
        state = {
            "executed_injections": [
                {"description": "Prompt injection bypassed safety check"},
            ],
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "injection executed" in result.lower()

    def test_empty_state_safe(self, shutdown):
        """Empty system state is safe."""
        assert shutdown.check_shutdown_triggers({}) is None


# ------------------------------------------------------------------
# get_shutdown_state / clear_shutdown_state
# ------------------------------------------------------------------


class TestShutdownState:
    """Tests for state file read/write/clear."""

    def test_no_state_returns_none(self, shutdown):
        """No previous shutdown returns None."""
        assert shutdown.get_shutdown_state() is None

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_get_state_after_shutdown(self, mock_exit, shutdown, tmp_data):
        """State file readable after shutdown."""
        shutdown.initiate_shutdown(
            trigger_reason="Test state",
            trigger_source="test",
            context={"current_task": "testing"},
        )

        state = shutdown.get_shutdown_state()
        assert state is not None
        assert state["trigger_reason"] == "Test state"
        assert state["context"]["current_task"] == "testing"

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_clear_moves_to_history(self, mock_exit, shutdown, tmp_data):
        """clear_shutdown_state moves file to history dir."""
        shutdown.initiate_shutdown(
            trigger_reason="History test",
            trigger_source="test",
            context={},
        )

        state_path = Path(tmp_data["shutdown_state_file"])
        assert state_path.exists()

        shutdown.clear_shutdown_state()

        assert not state_path.exists()
        history_dir = Path(tmp_data["shutdown_history_dir"])
        assert history_dir.exists()
        history_files = list(history_dir.glob("shutdown_*.json"))
        assert len(history_files) == 1

        # Verify content preserved
        archived = json.loads(history_files[0].read_text(encoding="utf-8"))
        assert archived["trigger_reason"] == "History test"

    def test_clear_no_state_noop(self, shutdown):
        """Clearing when no state file exists is a no-op."""
        shutdown.clear_shutdown_state()  # Should not raise

    def test_corrupted_state_returns_none(self, tmp_data):
        """Corrupted state file returns None."""
        state_path = Path(tmp_data["shutdown_state_file"])
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("NOT VALID JSON {{{{", encoding="utf-8")

        es = EmergencyShutdown(config=tmp_data)
        assert es.get_shutdown_state() is None


# ------------------------------------------------------------------
# Default thresholds
# ------------------------------------------------------------------


class TestDefaults:
    """Tests for default configuration handling."""

    def test_default_thresholds_applied(self):
        """EmergencyShutdown works with no config."""
        es = EmergencyShutdown()
        state = {"cpu_percent": 50}
        assert es.check_shutdown_triggers(state) is None

    def test_custom_thresholds_override(self, tmp_data):
        """Custom thresholds from config override defaults."""
        tmp_data["shutdown"]["cpu_threshold"] = 50
        es = EmergencyShutdown(config=tmp_data)
        state = {"cpu_percent": 55}
        result = es.check_shutdown_triggers(state)
        assert result is not None
        assert "CPU" in result
