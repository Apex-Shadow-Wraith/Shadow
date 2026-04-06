"""
Tests for Void — 24/7 Passive Monitoring
==========================================
"""

import json
import sys
import types
import pytest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, MagicMock

from modules.base import ModuleStatus, ToolResult
from modules.void.void import Void


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
    mock_psutil.disk_partitions = Mock(return_value=[
        Mock(device="C:\\", mountpoint="C:\\", fstype="NTFS"),
    ])
    # process_iter: return a few fake processes
    fake_procs = []
    for i, (name, cpu, mem) in enumerate([
        ("python.exe", 12.0, 3.5), ("chrome.exe", 8.0, 5.2), ("code.exe", 4.0, 2.1),
    ]):
        p = Mock()
        p.info = {"pid": 100 + i, "name": name, "cpu_percent": cpu, "memory_percent": mem}
        fake_procs.append(p)
    mock_psutil.process_iter = Mock(return_value=fake_procs)
    mock_psutil.NoSuchProcess = type("NoSuchProcess", (Exception,), {})
    mock_psutil.AccessDenied = type("AccessDenied", (Exception,), {})
    monkeypatch.setitem(sys.modules, "psutil", mock_psutil)
    return mock_psutil


@pytest.fixture
def void(tmp_path: Path) -> Void:
    config = {"trends_file": str(tmp_path / "trends.json")}
    return Void(config)


@pytest.fixture
async def online_void(void: Void) -> Void:
    await void.initialize()
    return void


class TestVoidLifecycle:
    @pytest.mark.asyncio
    async def test_initialize(self, void: Void):
        await void.initialize()
        assert void.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown(self, void: Void):
        await void.initialize()
        await void.shutdown()
        assert void.status == ModuleStatus.OFFLINE

    def test_get_tools(self, void: Void):
        tools = void.get_tools()
        assert len(tools) == 7
        names = [t["name"] for t in tools]
        assert "system_health" in names
        assert "gpu_status" in names
        assert "trend_snapshot" in names


class TestSystemHealth:
    @pytest.mark.asyncio
    async def test_health_check(self, online_void: Void):
        r = await online_void.execute("system_health", {})
        assert r.success is True
        assert "cpu_percent" in r.content
        assert r.content["cpu_percent"] == 45.0
        assert "ram_percent" in r.content
        assert "disk_percent" in r.content
        assert isinstance(r.content["alerts"], list)


class TestGPUStatus:
    @pytest.mark.asyncio
    async def test_gpu_status_handles_no_gpu(self, online_void: Void):
        r = await online_void.execute("gpu_status", {})
        assert r.success is True
        # Should succeed even without GPU


class TestProcessList:
    @pytest.mark.asyncio
    async def test_process_list(self, online_void: Void):
        r = await online_void.execute("process_list", {"top_n": 5})
        assert r.success is True
        assert "processes" in r.content
        assert len(r.content["processes"]) <= 5
        assert len(r.content["processes"]) == 3


class TestServiceStatus:
    @pytest.mark.asyncio
    async def test_service_check(self, online_void: Void):
        r = await online_void.execute("service_status", {
            "services": ["python", "nonexistent_service_xyz"],
        })
        assert r.success is True
        assert "services" in r.content
        assert r.content["services"]["python"] is True
        assert r.content["services"]["nonexistent_service_xyz"] is False


class TestDiskUsage:
    @pytest.mark.asyncio
    async def test_disk_usage(self, online_void: Void):
        r = await online_void.execute("disk_usage", {})
        assert r.success is True
        assert "partitions" in r.content
        assert r.content["count"] == 1


class TestBackupStatus:
    @pytest.mark.asyncio
    async def test_no_backup_dir(self, online_void: Void):
        r = await online_void.execute("backup_status", {
            "backup_dir": "/nonexistent/backup",
        })
        assert r.success is True
        assert r.content["exists"] is False

    @pytest.mark.asyncio
    async def test_existing_backup_dir(self, online_void: Void, tmp_path: Path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        (backup_dir / "backup_2024.tar.gz").write_text("fake backup")

        r = await online_void.execute("backup_status", {
            "backup_dir": str(backup_dir),
        })
        assert r.success is True
        assert r.content["exists"] is True
        assert r.content["file_count"] == 1


class TestTrendSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot(self, online_void: Void):
        r = await online_void.execute("trend_snapshot", {})
        assert r.success is True
        assert "snapshot" in r.content
        assert r.content["total_snapshots"] == 1

    @pytest.mark.asyncio
    async def test_multiple_snapshots(self, online_void: Void):
        await online_void.execute("trend_snapshot", {})
        await online_void.execute("trend_snapshot", {})
        r = await online_void.execute("trend_snapshot", {})
        assert r.content["total_snapshots"] == 3

    @pytest.mark.asyncio
    async def test_trends_persist(self, tmp_path: Path):
        config = {"trends_file": str(tmp_path / "trends.json")}

        v1 = Void(config)
        await v1.initialize()
        await v1.execute("trend_snapshot", {})
        await v1.shutdown()

        v2 = Void(config)
        await v2.initialize()
        assert len(v2._trends) == 1
        await v2.shutdown()


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool(self, online_void: Void):
        r = await online_void.execute("nonexistent", {})
        assert r.success is False
