"""
Tests for Void — 24/7 Passive Monitoring
==========================================
SQLite-backed metrics, threshold alerts, service checks.
"""

import os
import sys
import types
import pytest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, MagicMock, patch

from modules.base import ModuleStatus, ToolResult
from modules.void.void import Void


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fake_psutil(monkeypatch):
    """Inject a fake psutil module so Void's local imports work."""
    mock_psutil = types.ModuleType("psutil")
    mock_psutil.cpu_percent = Mock(return_value=45.0)
    mock_psutil.virtual_memory = Mock(return_value=Mock(
        percent=62.0, total=32 * 1024**3, used=20 * 1024**3, available=12 * 1024**3,
    ))
    mock_psutil.disk_usage = Mock(return_value=Mock(
        percent=55.0, total=1000 * 1024**3, used=550 * 1024**3, free=450 * 1024**3,
    ))

    # Process mock for process memory
    mock_proc = Mock()
    mock_proc.memory_info.return_value = Mock(rss=200 * 1024**2)  # 200 MB
    mock_psutil.Process = Mock(return_value=mock_proc)

    mock_psutil.NoSuchProcess = type("NoSuchProcess", (Exception,), {})
    mock_psutil.AccessDenied = type("AccessDenied", (Exception,), {})

    monkeypatch.setitem(sys.modules, "psutil", mock_psutil)
    return mock_psutil


@pytest.fixture
def void(tmp_path: Path) -> Void:
    config = {"db_path": str(tmp_path / "void_metrics.db")}
    return Void(config)


@pytest.fixture
async def online_void(void: Void) -> Void:
    await void.initialize()
    return void


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestVoidLifecycle:
    @pytest.mark.asyncio
    async def test_initialize(self, void: Void):
        await void.initialize()
        assert void.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_initialize_creates_db(self, void: Void, tmp_path: Path):
        await void.initialize()
        db_path = tmp_path / "void_metrics.db"
        assert db_path.exists()

    @pytest.mark.asyncio
    async def test_shutdown(self, online_void: Void):
        await online_void.shutdown()
        assert online_void.status == ModuleStatus.OFFLINE
        assert online_void._conn is None

    def test_get_tools(self, void: Void):
        tools = void.get_tools()
        assert len(tools) == 6
        names = {t["name"] for t in tools}
        assert names == {
            "system_snapshot", "health_check", "metric_history",
            "service_check", "set_threshold", "void_report",
        }

    def test_tool_permissions(self, void: Void):
        tools = void.get_tools()
        by_name = {t["name"]: t for t in tools}
        assert by_name["system_snapshot"]["permission_level"] == "autonomous"
        assert by_name["health_check"]["permission_level"] == "autonomous"
        assert by_name["metric_history"]["permission_level"] == "autonomous"
        assert by_name["service_check"]["permission_level"] == "autonomous"
        assert by_name["set_threshold"]["permission_level"] == "approval_required"
        assert by_name["void_report"]["permission_level"] == "autonomous"


# ---------------------------------------------------------------------------
# system_snapshot
# ---------------------------------------------------------------------------

class TestSystemSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_returns_metrics(self, online_void: Void):
        r = await online_void.execute("system_snapshot", {})
        assert r.success is True
        assert r.content["cpu_percent"] == 45.0
        assert r.content["ram_percent"] == 62.0
        assert r.content["disk_percent"] == 55.0
        assert "process_memory_mb" in r.content
        assert "timestamp" in r.content

    @pytest.mark.asyncio
    async def test_snapshot_stores_to_db(self, online_void: Void):
        await online_void.execute("system_snapshot", {})
        # Check that metrics were stored
        rows = online_void._conn.execute(
            "SELECT COUNT(*) as cnt FROM void_metrics"
        ).fetchone()
        assert rows["cnt"] >= 6  # cpu, ram%, ram_gb, disk%, disk_gb, process_mem

    @pytest.mark.asyncio
    async def test_snapshot_gpu_graceful_failure(self, online_void: Void):
        """Snapshot should succeed even when nvidia-smi is missing."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            r = await online_void.execute("system_snapshot", {})
        assert r.success is True
        assert r.content["gpu"]["available"] is False

    @pytest.mark.asyncio
    async def test_snapshot_process_memory(self, online_void: Void):
        r = await online_void.execute("system_snapshot", {})
        assert r.success is True
        assert r.content["process_memory_mb"] == pytest.approx(200.0, rel=0.1)


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy_no_alerts(self, online_void: Void):
        """Default mock values (45/62/55) are below all thresholds."""
        r = await online_void.execute("health_check", {})
        assert r.success is True
        assert r.content["status"] == "healthy"
        assert r.content["alerts"] == []

    @pytest.mark.asyncio
    async def test_warning_alert(self, online_void: Void, fake_psutil):
        """CPU at 85% should trigger warning (threshold 80)."""
        fake_psutil.cpu_percent = Mock(return_value=85.0)
        r = await online_void.execute("health_check", {})
        assert r.success is True
        assert r.content["status"] == "warning"
        assert len(r.content["alerts"]) == 1
        alert = r.content["alerts"][0]
        assert alert["metric"] == "cpu"
        assert alert["severity"] == "warning"
        assert alert["value"] == 85.0

    @pytest.mark.asyncio
    async def test_critical_alert(self, online_void: Void, fake_psutil):
        """CPU at 96% should trigger critical (threshold 95)."""
        fake_psutil.cpu_percent = Mock(return_value=96.0)
        r = await online_void.execute("health_check", {})
        assert r.success is True
        assert r.content["status"] == "critical"
        alert = r.content["alerts"][0]
        assert alert["severity"] == "critical"
        assert alert["threshold"] == 95.0

    @pytest.mark.asyncio
    async def test_multiple_alerts(self, online_void: Void, fake_psutil):
        """Multiple metrics exceeding thresholds."""
        fake_psutil.cpu_percent = Mock(return_value=82.0)
        fake_psutil.virtual_memory = Mock(return_value=Mock(
            percent=90.0, total=32 * 1024**3, used=28 * 1024**3, available=4 * 1024**3,
        ))
        r = await online_void.execute("health_check", {})
        assert r.success is True
        assert len(r.content["alerts"]) == 2
        metrics = {a["metric"] for a in r.content["alerts"]}
        assert "cpu" in metrics
        assert "ram" in metrics

    @pytest.mark.asyncio
    async def test_critical_overrides_warning(self, online_void: Void, fake_psutil):
        """A value at critical should report critical, not warning."""
        fake_psutil.cpu_percent = Mock(return_value=95.0)
        r = await online_void.execute("health_check", {})
        alert = r.content["alerts"][0]
        assert alert["severity"] == "critical"


# ---------------------------------------------------------------------------
# metric_history
# ---------------------------------------------------------------------------

class TestMetricHistory:
    @pytest.mark.asyncio
    async def test_query_stored_metrics(self, online_void: Void):
        """Store a snapshot, then query it back."""
        await online_void.execute("system_snapshot", {})
        r = await online_void.execute("metric_history", {
            "metric_name": "cpu_percent", "hours": 1,
        })
        assert r.success is True
        assert r.content["data_points"] >= 1
        assert r.content["history"][0]["value"] == 45.0

    @pytest.mark.asyncio
    async def test_empty_history(self, online_void: Void):
        """No data for a metric that hasn't been stored."""
        r = await online_void.execute("metric_history", {
            "metric_name": "nonexistent_metric", "hours": 1,
        })
        assert r.success is True
        assert r.content["data_points"] == 0
        assert r.content["history"] == []

    @pytest.mark.asyncio
    async def test_missing_metric_name(self, online_void: Void):
        r = await online_void.execute("metric_history", {})
        assert r.success is False
        assert "metric_name" in r.error

    @pytest.mark.asyncio
    async def test_default_hours(self, online_void: Void):
        """Default hours should be 24."""
        await online_void.execute("system_snapshot", {})
        r = await online_void.execute("metric_history", {
            "metric_name": "cpu_percent",
        })
        assert r.success is True
        assert r.content["hours"] == 24


# ---------------------------------------------------------------------------
# service_check
# ---------------------------------------------------------------------------

class TestServiceCheck:
    @pytest.mark.asyncio
    async def test_ollama_not_found(self, online_void: Void):
        """Ollama not installed should report gracefully."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            r = await online_void.execute("service_check", {})
        assert r.success is True
        assert r.content["services"]["ollama"]["running"] is False
        assert "not installed" in r.content["services"]["ollama"]["detail"]

    @pytest.mark.asyncio
    async def test_ollama_running(self, online_void: Void):
        """Ollama running should report success."""
        mock_result = Mock(returncode=0, stdout="NAME\nmodel:latest")
        with patch("subprocess.run", return_value=mock_result):
            r = await online_void.execute("service_check", {})
        assert r.success is True
        assert r.content["services"]["ollama"]["running"] is True

    @pytest.mark.asyncio
    async def test_ollama_timeout(self, online_void: Void):
        """Ollama timing out should report gracefully."""
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="ollama", timeout=5)):
            r = await online_void.execute("service_check", {})
        assert r.success is True
        assert r.content["services"]["ollama"]["running"] is False
        assert "timed out" in r.content["services"]["ollama"]["detail"]

    @pytest.mark.asyncio
    async def test_shadow_process_healthy(self, online_void: Void):
        r = await online_void.execute("service_check", {})
        assert r.success is True
        assert r.content["services"]["shadow_process"]["running"] is True
        assert r.content["services"]["shadow_process"]["pid"] == os.getpid()


# ---------------------------------------------------------------------------
# set_threshold
# ---------------------------------------------------------------------------

class TestSetThreshold:
    @pytest.mark.asyncio
    async def test_set_valid_threshold(self, online_void: Void):
        r = await online_void.execute("set_threshold", {
            "metric": "cpu_warning", "value": 75.0,
        })
        assert r.success is True
        assert r.content["old_value"] == 80.0
        assert r.content["new_value"] == 75.0
        assert online_void._thresholds["cpu_warning"] == 75.0

    @pytest.mark.asyncio
    async def test_invalid_metric(self, online_void: Void):
        r = await online_void.execute("set_threshold", {
            "metric": "nonexistent", "value": 50.0,
        })
        assert r.success is False
        assert "Unknown threshold" in r.error

    @pytest.mark.asyncio
    async def test_missing_params(self, online_void: Void):
        r = await online_void.execute("set_threshold", {})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_threshold_affects_health_check(self, online_void: Void):
        """Lowering CPU warning to 40 should trigger alert at 45%."""
        await online_void.execute("set_threshold", {
            "metric": "cpu_warning", "value": 40.0,
        })
        r = await online_void.execute("health_check", {})
        assert r.content["status"] == "warning"
        assert any(a["metric"] == "cpu" for a in r.content["alerts"])


# ---------------------------------------------------------------------------
# void_report
# ---------------------------------------------------------------------------

class TestVoidReport:
    @pytest.mark.asyncio
    async def test_report_structure(self, online_void: Void):
        r = await online_void.execute("void_report", {})
        assert r.success is True
        assert "generated_at" in r.content
        assert "system_status" in r.content
        assert "alerts" in r.content
        assert "snapshot" in r.content
        assert "stored_metrics_count" in r.content
        assert "thresholds" in r.content

    @pytest.mark.asyncio
    async def test_report_healthy(self, online_void: Void):
        r = await online_void.execute("void_report", {})
        assert r.content["system_status"] == "healthy"
        assert r.content["alerts"] == []

    @pytest.mark.asyncio
    async def test_report_with_alerts(self, online_void: Void, fake_psutil):
        fake_psutil.cpu_percent = Mock(return_value=96.0)
        r = await online_void.execute("void_report", {})
        assert r.content["system_status"] == "critical"
        assert len(r.content["alerts"]) >= 1

    @pytest.mark.asyncio
    async def test_report_includes_snapshot(self, online_void: Void):
        r = await online_void.execute("void_report", {})
        snapshot = r.content["snapshot"]
        assert "cpu_percent" in snapshot
        assert "ram_percent" in snapshot
        assert "disk_percent" in snapshot

    @pytest.mark.asyncio
    async def test_report_counts_stored_metrics(self, online_void: Void):
        """After snapshots, report should show stored metric count."""
        await online_void.execute("system_snapshot", {})
        r = await online_void.execute("void_report", {})
        assert r.content["stored_metrics_count"] >= 6


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool(self, online_void: Void):
        r = await online_void.execute("nonexistent", {})
        assert r.success is False
        assert "Unknown tool" in r.error
