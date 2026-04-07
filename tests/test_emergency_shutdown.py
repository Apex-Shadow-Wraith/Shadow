"""
Tests for Cerberus Emergency Shutdown Protocol.

Covers:
  - Safe operations that must NEVER trigger shutdown
  - Real threats that MUST trigger shutdown
  - Telegram notification flow and fallback
  - State file management and history archival

IMPORTANT: sys.exit is ALWAYS mocked — no test actually halts.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.cerberus.emergency_shutdown import (
    EmergencyShutdown,
    SAFE_TOOL_NAMES,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def tmp_config(tmp_path):
    """Provide temp paths and thresholds for EmergencyShutdown."""
    return {
        "shutdown_state_file": str(tmp_path / "shutdown_state.json"),
        "shutdown_history_dir": str(tmp_path / "shutdown_history"),
        "emergency_log_file": str(tmp_path / "emergency_shutdown.log"),
        "shutdown": {
            "injection_execute_threshold": 0.9,
            "cerberus_protected_paths": [
                "modules/cerberus/",
                "config/cerberus_limits.yaml",
            ],
            "infinite_loop_threshold": 50,
            "infinite_loop_window_seconds": 60,
            "disk_min_mb": 500,
            "unauthorized_external_burst_count": 10,
            "unauthorized_external_burst_window_seconds": 60,
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
def shutdown(tmp_config, mock_telegram):
    """EmergencyShutdown with working Telegram."""
    return EmergencyShutdown(config=tmp_config, telegram=mock_telegram)


@pytest.fixture
def shutdown_no_telegram(tmp_config):
    """EmergencyShutdown with no Telegram configured."""
    return EmergencyShutdown(config=tmp_config, telegram=None)


# ==================================================================
# CRITICAL TESTS: Safe operations must NEVER trigger shutdown
# ==================================================================


class TestSafeOperationsNoShutdown:
    """Normal Shadow operations must return None (no shutdown)."""

    def test_omen_editing_source_files(self, shutdown):
        """Omen editing source files is its entire job — no shutdown."""
        state = {
            "active_tool": "code_edit",
            "active_module": "omen",
            "target_path": "modules/wraith/wraith.py",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_omen_editing_any_non_cerberus_module(self, shutdown):
        """Omen editing ANY module file (except cerberus) is safe."""
        for path in [
            "modules/reaper/reaper.py",
            "modules/shadow/shadow.py",
            "modules/nova/nova.py",
            "main.py",
            "scripts/esv_processor.py",
        ]:
            state = {
                "active_tool": "code_edit",
                "active_module": "omen",
                "target_path": path,
            }
            assert shutdown.check_shutdown_triggers(state) is None, (
                f"Omen editing {path} should NOT trigger shutdown"
            )

    def test_grimoire_batch_memory_store(self, shutdown):
        """Grimoire storing 100 memories in 10 seconds is normal batch work."""
        state = {
            "active_tool": "memory_store",
            "active_module": "grimoire",
            "target_path": "data/memory/shadow_memory.db",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_grimoire_embedding_ingestion(self, shutdown):
        """Grimoire running embedding ingestion is safe."""
        state = {
            "active_tool": "embedding_store",
            "active_module": "grimoire",
            "operation_type": "embedding_ingestion",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_reaper_many_web_requests(self, shutdown):
        """Reaper making 50 web requests during research is normal."""
        state = {
            "active_tool": "web_search",
            "active_module": "reaper",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_reaper_scraping(self, shutdown):
        """Reaper scraping websites is expected behavior."""
        state = {
            "active_tool": "web_scrape",
            "active_module": "reaper",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_high_cpu_during_model_inference(self, shutdown):
        """95% CPU during model inference is expected — not a trigger."""
        state = {
            "cpu_percent": 95,
            "operation_type": "model_inference",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_high_cpu_during_model_loading(self, shutdown):
        """High CPU during model loading is expected."""
        state = {
            "cpu_percent": 99,
            "operation_type": "model_loading",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_high_memory_during_batch_processing(self, shutdown):
        """High memory during batch processing is expected."""
        state = {
            "memory_percent": 90,
            "operation_type": "batch_processing",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_multiple_module_errors_during_tests(self, shutdown):
        """Module errors during test runs are expected — not cascading failure."""
        state = {
            "context": "test_run",
            "module_errors": ["wraith timeout", "reaper crash", "cipher OOM"],
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_multiple_modules_active_simultaneously(self, shutdown):
        """Multiple modules active at once is normal parallel work."""
        state = {
            "parallel_modules_active": True,
            "active_modules": ["wraith", "reaper", "grimoire", "omen"],
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_growth_engine_running(self, shutdown):
        """Growth Engine autonomous tasks are safe."""
        state = {
            "growth_engine_active": True,
            "active_module": "shadow",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_wraith_setting_reminders(self, shutdown):
        """Wraith setting reminders is daily task work."""
        state = {"active_tool": "reminder_set", "active_module": "wraith"}
        assert shutdown.check_shutdown_triggers(state) is None

    def test_nova_generating_content(self, shutdown):
        """Nova generating documents is expected."""
        state = {"active_tool": "document_generate", "active_module": "nova"}
        assert shutdown.check_shutdown_triggers(state) is None

    def test_cipher_running_calculations(self, shutdown):
        """Cipher running calculations is safe."""
        state = {"active_tool": "math_calculate", "active_module": "cipher"}
        assert shutdown.check_shutdown_triggers(state) is None

    def test_module_writing_to_data_directory(self, shutdown):
        """Any module writing to data/ directories is normal."""
        state = {
            "active_module": "harbinger",
            "target_path": "data/reports/safety/2026-04-06.yaml",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_all_safe_tools_whitelisted(self, shutdown):
        """Every tool in SAFE_TOOL_NAMES returns None."""
        for tool in SAFE_TOOL_NAMES:
            state = {"active_tool": tool}
            assert shutdown.check_shutdown_triggers(state) is None, (
                f"Safe tool '{tool}' should NOT trigger shutdown"
            )

    def test_vector_indexing_safe(self, shutdown):
        """Vector indexing operation type is safe."""
        state = {"operation_type": "vector_indexing"}
        assert shutdown.check_shutdown_triggers(state) is None

    def test_empty_state_is_safe(self, shutdown):
        """Empty system state should not trigger shutdown."""
        assert shutdown.check_shutdown_triggers({}) is None


# ==================================================================
# CRITICAL TESTS: Real threats MUST trigger shutdown
# ==================================================================


class TestRealThreatsTriggerShutdown:
    """Genuinely dangerous situations must return a trigger reason."""

    def test_injection_executed_triggers_shutdown(self, shutdown):
        """Injection score > 0.9 with executed action triggers shutdown."""
        state = {
            "injection_score": 0.95,
            "injection_executed": True,
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "SECURITY BREACH" in result
        assert "0.95" in result
        assert "EXECUTED" in result

    def test_injection_detected_but_blocked_is_safe(self, shutdown):
        """Injection detected but blocked (not executed) is NOT an emergency."""
        state = {
            "injection_score": 0.95,
            "injection_executed": False,
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_injection_below_threshold_is_safe(self, shutdown):
        """Injection score below 0.9 even if executed is safe."""
        state = {
            "injection_score": 0.85,
            "injection_executed": True,
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_cerberus_self_modification_cerberus_py(self, shutdown):
        """Module writing to modules/cerberus/cerberus.py triggers shutdown."""
        state = {
            "target_path": "modules/cerberus/cerberus.py",
            "active_module": "omen",
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "CERBERUS SELF-MODIFICATION" in result

    def test_cerberus_self_modification_any_cerberus_file(self, shutdown):
        """Any write to modules/cerberus/ triggers shutdown."""
        for path in [
            "modules/cerberus/injection_detector.py",
            "modules/cerberus/watchdog.py",
            "modules/cerberus/reversibility.py",
            "modules/cerberus/emergency_shutdown.py",
        ]:
            state = {"target_path": path, "active_module": "morpheus"}
            result = shutdown.check_shutdown_triggers(state)
            assert result is not None, (
                f"Modifying {path} should trigger shutdown"
            )
            assert "CERBERUS SELF-MODIFICATION" in result

    def test_cerberus_config_modification(self, shutdown):
        """Writing to config/cerberus_limits.yaml triggers shutdown."""
        state = {
            "target_path": "config/cerberus_limits.yaml",
            "active_module": "wraith",
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "CERBERUS SELF-MODIFICATION" in result

    def test_cerberus_self_modification_windows_paths(self, shutdown):
        """Windows-style backslash paths still detected."""
        state = {
            "target_path": "modules\\cerberus\\watchdog.py",
            "active_module": "wraith",
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "CERBERUS SELF-MODIFICATION" in result

    def test_omen_editing_non_cerberus_is_safe(self, shutdown):
        """Omen editing other module files is fine and expected."""
        state = {
            "active_tool": "code_edit",
            "active_module": "omen",
            "target_path": "modules/wraith/wraith.py",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_infinite_loop_50_retries_in_60s(self, shutdown):
        """50+ identical tool retries in 60s triggers shutdown."""
        state = {
            "tool_retry_count": 55,
            "tool_retry_window_seconds": 45.0,
            "tool_name": "web_fetch",
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "INFINITE LOOP" in result
        assert "web_fetch" in result
        assert "55" in result

    def test_normal_12_retry_cycle_is_safe(self, shutdown):
        """The normal 12-attempt retry cycle is NOT an infinite loop."""
        state = {
            "tool_retry_count": 12,
            "tool_retry_window_seconds": 30.0,
            "tool_name": "web_fetch",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_49_retries_below_threshold_safe(self, shutdown):
        """49 retries is below the 50 threshold — safe."""
        state = {
            "tool_retry_count": 49,
            "tool_retry_window_seconds": 55.0,
            "tool_name": "web_fetch",
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_disk_below_500mb(self, shutdown):
        """Disk below 500MB triggers shutdown."""
        state = {"disk_free_mb": 350.0}
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "DISK FULL" in result
        assert "350" in result

    def test_disk_above_500mb_safe(self, shutdown):
        """Disk above 500MB is fine."""
        state = {"disk_free_mb": 600.0}
        assert shutdown.check_shutdown_triggers(state) is None

    def test_unauthorized_external_burst(self, shutdown):
        """10+ unapproved external actions in 60s triggers shutdown."""
        state = {
            "unauthorized_external_count": 15,
            "unauthorized_external_window_seconds": 30.0,
        }
        result = shutdown.check_shutdown_triggers(state)
        assert result is not None
        assert "UNCONTROLLED EXTERNAL ACTIONS" in result
        assert "15" in result

    def test_fewer_external_actions_safe(self, shutdown):
        """9 unapproved external actions is below threshold — safe."""
        state = {
            "unauthorized_external_count": 9,
            "unauthorized_external_window_seconds": 30.0,
        }
        assert shutdown.check_shutdown_triggers(state) is None

    def test_external_actions_outside_window_safe(self, shutdown):
        """10 external actions spread over 90s (outside 60s window) is safe."""
        state = {
            "unauthorized_external_count": 10,
            "unauthorized_external_window_seconds": 90.0,
        }
        assert shutdown.check_shutdown_triggers(state) is None


# ==================================================================
# initiate_shutdown — notification flow
# ==================================================================


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
        mock_telegram.send_alert.side_effect = (
            lambda **kw: call_order.append("telegram") or True
        )
        mock_exit.side_effect = lambda code: call_order.append("exit")

        shutdown.initiate_shutdown(
            trigger_reason="Order test",
            trigger_source="test",
            context={},
        )
        assert call_order == ["telegram", "exit"]

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_telegram_message_contains_trigger_info(
        self, mock_exit, shutdown, mock_telegram
    ):
        """Emergency message includes trigger reason, source, and task."""
        shutdown.initiate_shutdown(
            trigger_reason="Injection executed",
            trigger_source="cerberus",
            context={
                "current_task": "processing query",
                "risk_assessment": "critical",
            },
        )
        call_args = mock_telegram.send_alert.call_args
        message = (
            call_args.kwargs.get("message")
            or call_args[1].get("message", call_args[0][0] if call_args[0] else "")
        )
        assert "Injection executed" in message
        assert "cerberus" in message
        assert "processing query" in message

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_telegram_failure_writes_local_log(
        self, mock_exit, tmp_config, mock_telegram_fail
    ):
        """When Telegram fails, emergency log file is written."""
        es = EmergencyShutdown(config=tmp_config, telegram=mock_telegram_fail)
        es.initiate_shutdown(
            trigger_reason="Security breach",
            trigger_source="cerberus",
            context={"current_task": "idle"},
        )
        log_path = Path(tmp_config["emergency_log_file"])
        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "Security breach" in content
        assert "EMERGENCY SHUTDOWN" in content

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_no_telegram_writes_local_log(
        self, mock_exit, shutdown_no_telegram, tmp_config
    ):
        """With no Telegram configured, local log is written."""
        shutdown_no_telegram.initiate_shutdown(
            trigger_reason="No telegram test",
            trigger_source="test",
            context={},
        )
        log_path = Path(tmp_config["emergency_log_file"])
        assert log_path.exists()

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_telegram_exception_falls_back_to_log(self, mock_exit, tmp_config):
        """If Telegram raises an exception, fall back to local log."""
        bad_telegram = MagicMock()
        bad_telegram.send_alert.side_effect = Exception("Connection refused")

        es = EmergencyShutdown(config=tmp_config, telegram=bad_telegram)
        es.initiate_shutdown(
            trigger_reason="Exception test",
            trigger_source="test",
            context={},
        )
        log_path = Path(tmp_config["emergency_log_file"])
        assert log_path.exists()
        mock_exit.assert_called_once_with(1)

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_state_file_written_with_context(self, mock_exit, shutdown, tmp_config):
        """Shutdown state file written with full context."""
        context = {
            "current_task": "processing query",
            "module_states": {"wraith": "online", "reaper": "error"},
            "risk_assessment": "critical",
        }
        shutdown.initiate_shutdown(
            trigger_reason="Disk full",
            trigger_source="void",
            context=context,
        )
        state_path = Path(tmp_config["shutdown_state_file"])
        assert state_path.exists()

        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["trigger_reason"] == "Disk full"
        assert state["trigger_source"] == "void"
        assert state["context"]["current_task"] == "processing query"
        assert state["context"]["module_states"]["reaper"] == "error"
        assert "timestamp" in state
        assert "telegram_notified" in state


# ==================================================================
# State management — get / clear
# ==================================================================


class TestShutdownState:
    """Tests for state file read/write/clear."""

    def test_no_state_returns_none(self, shutdown):
        """No previous shutdown returns None."""
        assert shutdown.get_shutdown_state() is None

    @patch("modules.cerberus.emergency_shutdown.sys.exit")
    def test_get_state_after_shutdown(self, mock_exit, shutdown, tmp_config):
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
    def test_clear_moves_to_history(self, mock_exit, shutdown, tmp_config):
        """clear_shutdown_state moves file to history dir."""
        shutdown.initiate_shutdown(
            trigger_reason="History test",
            trigger_source="test",
            context={},
        )
        state_path = Path(tmp_config["shutdown_state_file"])
        assert state_path.exists()

        shutdown.clear_shutdown_state()

        assert not state_path.exists()
        history_dir = Path(tmp_config["shutdown_history_dir"])
        assert history_dir.exists()
        history_files = list(history_dir.glob("shutdown_*.json"))
        assert len(history_files) == 1

        archived = json.loads(history_files[0].read_text(encoding="utf-8"))
        assert archived["trigger_reason"] == "History test"

    def test_clear_no_state_noop(self, shutdown):
        """Clearing when no state file exists is a no-op."""
        shutdown.clear_shutdown_state()  # Should not raise

    def test_corrupted_state_returns_none(self, tmp_config):
        """Corrupted state file returns None."""
        state_path = Path(tmp_config["shutdown_state_file"])
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("NOT VALID JSON {{{{", encoding="utf-8")

        es = EmergencyShutdown(config=tmp_config)
        assert es.get_shutdown_state() is None


# ==================================================================
# Default thresholds
# ==================================================================


class TestDefaults:
    """Tests for default configuration handling."""

    def test_default_thresholds_applied(self):
        """EmergencyShutdown works with no config."""
        es = EmergencyShutdown()
        state = {"disk_free_mb": 1000.0}
        assert es.check_shutdown_triggers(state) is None

    def test_custom_thresholds_override(self, tmp_config):
        """Custom thresholds from config override defaults."""
        tmp_config["shutdown"]["disk_min_mb"] = 1000
        es = EmergencyShutdown(config=tmp_config)
        state = {"disk_free_mb": 800.0}
        result = es.check_shutdown_triggers(state)
        assert result is not None
        assert "DISK FULL" in result
