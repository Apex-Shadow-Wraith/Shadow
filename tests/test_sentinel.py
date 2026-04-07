"""
Tests for Sentinel — White Hat Security
==========================================
"""

import json
import sys
import types
import pytest
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from modules.base import ModuleStatus, ToolResult
from modules.sentinel.sentinel import Sentinel


@pytest.fixture(autouse=True)
def fake_psutil(monkeypatch):
    """Inject a fake psutil module so Sentinel's local imports work."""
    mock_psutil = types.ModuleType("psutil")
    mock_conn = Mock()
    mock_conn.fd = 4
    mock_conn.family = 2
    mock_conn.type = 1
    mock_conn.laddr = Mock(ip="127.0.0.1", port=8080)
    mock_conn.raddr = Mock(ip="93.184.216.34", port=443)
    mock_conn.status = "ESTABLISHED"
    mock_conn.pid = 1234
    mock_psutil.net_connections = Mock(return_value=[mock_conn])
    monkeypatch.setitem(sys.modules, "psutil", mock_psutil)
    return mock_psutil


@pytest.fixture
def sentinel(tmp_path: Path) -> Sentinel:
    config = {
        "baseline_file": str(tmp_path / "baseline.json"),
        "quarantine_dir": str(tmp_path / "quarantine"),
    }
    return Sentinel(config)


@pytest.fixture
async def online_sentinel(sentinel: Sentinel) -> Sentinel:
    await sentinel.initialize()
    return sentinel


class TestSentinelLifecycle:
    @pytest.mark.asyncio
    async def test_initialize(self, sentinel: Sentinel):
        await sentinel.initialize()
        assert sentinel.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown(self, sentinel: Sentinel):
        await sentinel.initialize()
        await sentinel.shutdown()
        assert sentinel.status == ModuleStatus.OFFLINE

    def test_get_tools(self, sentinel: Sentinel):
        tools = sentinel.get_tools()
        assert len(tools) == 12
        names = [t["name"] for t in tools]
        assert "network_scan" in names
        assert "file_integrity_check" in names
        assert "quarantine_file" in names

    def test_all_tools_autonomous_or_approved(self, sentinel: Sentinel):
        for tool in sentinel.get_tools():
            assert tool["permission_level"] in ("autonomous", "approval_required")


class TestNetworkScan:
    @pytest.mark.asyncio
    async def test_scan_returns_connections(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("network_scan", {})
        assert r.success is True
        assert "connection_count" in r.content
        assert r.content["connection_count"] == 1


class TestFileIntegrity:
    @pytest.mark.asyncio
    async def test_baseline_new_file(self, online_sentinel: Sentinel, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        r = await online_sentinel.execute("file_integrity_check", {
            "file_paths": [str(test_file)],
        })
        assert r.success is True
        assert r.content["results"][0]["status"] == "baselined"

    @pytest.mark.asyncio
    async def test_integrity_intact(self, online_sentinel: Sentinel, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        await online_sentinel.execute("file_integrity_check", {
            "file_paths": [str(test_file)],
        })
        r = await online_sentinel.execute("file_integrity_check", {
            "file_paths": [str(test_file)],
        })
        assert r.content["results"][0]["status"] == "intact"
        assert r.content["results"][0]["changed"] is False

    @pytest.mark.asyncio
    async def test_integrity_modified(self, online_sentinel: Sentinel, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        await online_sentinel.execute("file_integrity_check", {
            "file_paths": [str(test_file)],
        })
        test_file.write_text("modified!")
        r = await online_sentinel.execute("file_integrity_check", {
            "file_paths": [str(test_file)],
        })
        assert r.content["results"][0]["status"] == "MODIFIED"
        assert r.content["results"][0]["changed"] is True

    @pytest.mark.asyncio
    async def test_missing_file(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("file_integrity_check", {
            "file_paths": ["/nonexistent/file.txt"],
        })
        assert r.content["results"][0]["status"] == "missing"

    @pytest.mark.asyncio
    async def test_empty_paths_fails(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("file_integrity_check", {"file_paths": []})
        assert r.success is False


class TestBreachCheck:
    @pytest.mark.asyncio
    async def test_stub_response(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("breach_check", {"email": "test@example.com"})
        assert r.success is True
        assert r.content["status"] == "stub"

    @pytest.mark.asyncio
    async def test_empty_email_fails(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("breach_check", {"email": ""})
        assert r.success is False


class TestSecurityAlert:
    @pytest.mark.asyncio
    async def test_create_alert(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("security_alert", {
            "message": "Unauthorized access attempt",
            "severity": "high",
        })
        assert r.success is True
        assert r.content["severity"] == "high"

    @pytest.mark.asyncio
    async def test_invalid_severity_fails(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("security_alert", {
            "message": "Test", "severity": "extreme",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_empty_message_fails(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("security_alert", {"message": ""})
        assert r.success is False


class TestThreatAssess:
    @pytest.mark.asyncio
    async def test_high_threat(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("threat_assess", {
            "event": "Ransomware exploit detected — active breach in progress",
        })
        assert r.content["threat_level"] in ("critical", "high")

    @pytest.mark.asyncio
    async def test_low_threat(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("threat_assess", {
            "event": "Routine software update available",
        })
        assert r.content["threat_level"] in ("low", "medium")

    @pytest.mark.asyncio
    async def test_empty_event_fails(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("threat_assess", {"event": ""})
        assert r.success is False


class TestQuarantine:
    @pytest.mark.asyncio
    async def test_quarantine_file(self, online_sentinel: Sentinel, tmp_path: Path):
        suspect = tmp_path / "malware.exe"
        suspect.write_text("suspicious content")
        r = await online_sentinel.execute("quarantine_file", {
            "file_path": str(suspect), "reason": "suspicious binary",
        })
        assert r.success is True
        assert not suspect.exists()  # Original moved

    @pytest.mark.asyncio
    async def test_quarantine_missing_fails(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("quarantine_file", {
            "file_path": "/nonexistent/file.exe", "reason": "test",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_quarantine_no_path_fails(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("quarantine_file", {"file_path": ""})
        assert r.success is False


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool(self, online_sentinel: Sentinel):
        r = await online_sentinel.execute("nonexistent", {})
        assert r.success is False
