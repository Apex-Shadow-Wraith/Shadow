"""
Tests for Cerberus's absorbed security surface (Phase A merge).
=================================================================
These mirror the pre-merge tests/test_sentinel.py but exercise the
24 absorbed security tools through Cerberus.execute() rather than
directly against the old Sentinel module. Behavior must be identical.
"""

import sys
import types
import pytest
import yaml
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from modules.base import ModuleStatus
from modules.cerberus.cerberus import Cerberus


# Minimal Cerberus limits — enough for initialize() to succeed; security
# tools dispatch via the SECURITY_TOOLS branch which doesn't touch limits.
_LIMITS: dict[str, Any] = {
    "hard_limits": {},
    "permission_tiers": {},
    "approval_required_tools": [],
    "autonomous_tools": [],
    "hooks": {
        "pre_tool": {"deny": [], "modify": []},
        "post_tool": {"flag": []},
    },
}


@pytest.fixture(autouse=True)
def fake_psutil(monkeypatch):
    """Inject a fake psutil module so the absorbed network_scan handler works."""
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
async def cerberus(tmp_path: Path) -> Cerberus:
    """Cerberus with a minimal config and a tmp-path-scoped security surface."""
    limits_path = tmp_path / "cerberus_limits.yaml"
    limits_path.write_text(yaml.dump(_LIMITS))
    config = {
        "limits_file": str(limits_path),
        "db_path": str(tmp_path / "audit.db"),
        "snapshot_dir": str(tmp_path / "snapshots"),
        "security": {
            "baseline_file": str(tmp_path / "baseline.json"),
            "quarantine_dir": str(tmp_path / "quarantine"),
        },
    }
    c = Cerberus(config)
    await c.initialize()
    return c


# --- Lifecycle / surface ---


class TestSecuritySurfaceLifecycle:
    @pytest.mark.asyncio
    async def test_initialize(self, cerberus: Cerberus):
        """Cerberus init brings the security surface online."""
        assert cerberus.status == ModuleStatus.ONLINE
        assert cerberus._security is not None

    @pytest.mark.asyncio
    async def test_shutdown_persists_baseline(self, cerberus: Cerberus, tmp_path: Path):
        """Shutdown writes the integrity baseline to disk."""
        # Trigger a baseline insert
        sample = tmp_path / "sample.txt"
        sample.write_text("hello")
        await cerberus.execute("file_integrity_check", {"file_paths": [str(sample)]})
        await cerberus.shutdown()
        # Baseline file should have been persisted
        baseline_path = tmp_path / "baseline.json"
        assert baseline_path.exists()

    @pytest.mark.asyncio
    async def test_get_tools_count(self, cerberus: Cerberus):
        """Cerberus.get_tools() returns 39 tools (15 + 24 absorbed)."""
        tools = cerberus.get_tools()
        assert len(tools) == 39
        names = [t["name"] for t in tools]
        # Spot-check absorbed names
        for name in ("network_scan", "file_integrity_check", "quarantine_file",
                     "firewall_analyze", "threat_assess", "threat_knowledge_store"):
            assert name in names

    @pytest.mark.asyncio
    async def test_all_tools_have_permission_level(self, cerberus: Cerberus):
        """Every tool advertises a valid permission_level."""
        for tool in cerberus.get_tools():
            assert tool["permission_level"] in ("autonomous", "approval_required")


# --- Network scan ---


class TestNetworkScan:
    @pytest.mark.asyncio
    async def test_scan_returns_connections(self, cerberus: Cerberus):
        r = await cerberus.execute("network_scan", {})
        assert r.success is True
        assert r.module == "cerberus"
        assert r.tool_name == "network_scan"
        assert r.content["connection_count"] == 1


# --- File integrity ---


class TestFileIntegrity:
    @pytest.mark.asyncio
    async def test_baseline_new_file(self, cerberus: Cerberus, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        r = await cerberus.execute("file_integrity_check", {
            "file_paths": [str(test_file)],
        })
        assert r.success is True
        assert r.content["results"][0]["status"] == "baselined"

    @pytest.mark.asyncio
    async def test_integrity_intact(self, cerberus: Cerberus, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        await cerberus.execute("file_integrity_check", {
            "file_paths": [str(test_file)],
        })
        r = await cerberus.execute("file_integrity_check", {
            "file_paths": [str(test_file)],
        })
        assert r.content["results"][0]["status"] == "intact"
        assert r.content["results"][0]["changed"] is False

    @pytest.mark.asyncio
    async def test_integrity_modified(self, cerberus: Cerberus, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        await cerberus.execute("file_integrity_check", {
            "file_paths": [str(test_file)],
        })
        test_file.write_text("modified!")
        r = await cerberus.execute("file_integrity_check", {
            "file_paths": [str(test_file)],
        })
        assert r.content["results"][0]["status"] == "MODIFIED"
        assert r.content["results"][0]["changed"] is True

    @pytest.mark.asyncio
    async def test_missing_file(self, cerberus: Cerberus):
        r = await cerberus.execute("file_integrity_check", {
            "file_paths": ["/nonexistent/file.txt"],
        })
        assert r.content["results"][0]["status"] == "missing"

    @pytest.mark.asyncio
    async def test_empty_paths_fails(self, cerberus: Cerberus):
        r = await cerberus.execute("file_integrity_check", {"file_paths": []})
        assert r.success is False


# --- Breach check ---


class TestBreachCheck:
    @pytest.mark.asyncio
    async def test_stub_response(self, cerberus: Cerberus):
        r = await cerberus.execute("breach_check", {"email": "test@example.com"})
        assert r.success is True
        assert r.content["status"] == "stub"

    @pytest.mark.asyncio
    async def test_empty_email_fails(self, cerberus: Cerberus):
        r = await cerberus.execute("breach_check", {"email": ""})
        assert r.success is False


# --- Security alert ---


class TestSecurityAlert:
    @pytest.mark.asyncio
    async def test_create_alert(self, cerberus: Cerberus):
        r = await cerberus.execute("security_alert", {
            "message": "Unauthorized access attempt",
            "severity": "high",
        })
        assert r.success is True
        assert r.content["severity"] == "high"

    @pytest.mark.asyncio
    async def test_invalid_severity_fails(self, cerberus: Cerberus):
        r = await cerberus.execute("security_alert", {
            "message": "Test", "severity": "extreme",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_empty_message_fails(self, cerberus: Cerberus):
        r = await cerberus.execute("security_alert", {"message": ""})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_default_source_is_cerberus_security(self, cerberus: Cerberus):
        """Default alert source identity post-merge is "cerberus.security"."""
        r = await cerberus.execute("security_alert", {
            "message": "Probe detected", "severity": "medium",
        })
        assert r.content["source"] == "cerberus.security"


# --- Threat assessment ---


class TestThreatAssess:
    @pytest.mark.asyncio
    async def test_high_threat(self, cerberus: Cerberus):
        r = await cerberus.execute("threat_assess", {
            "event": "Ransomware exploit detected — active breach in progress",
        })
        assert r.content["threat_level"] in ("critical", "high")

    @pytest.mark.asyncio
    async def test_low_threat(self, cerberus: Cerberus):
        r = await cerberus.execute("threat_assess", {
            "event": "Routine software update available",
        })
        assert r.content["threat_level"] in ("low", "medium")

    @pytest.mark.asyncio
    async def test_empty_event_fails(self, cerberus: Cerberus):
        r = await cerberus.execute("threat_assess", {"event": ""})
        assert r.success is False


# --- Quarantine ---


class TestQuarantine:
    @pytest.mark.asyncio
    async def test_quarantine_file(self, cerberus: Cerberus, tmp_path: Path):
        suspect = tmp_path / "malware.exe"
        suspect.write_text("suspicious content")
        r = await cerberus.execute("quarantine_file", {
            "file_path": str(suspect), "reason": "suspicious binary",
        })
        assert r.success is True
        assert not suspect.exists()  # Original moved

    @pytest.mark.asyncio
    async def test_quarantine_missing_fails(self, cerberus: Cerberus):
        r = await cerberus.execute("quarantine_file", {
            "file_path": "/nonexistent/file.exe", "reason": "test",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_quarantine_no_path_fails(self, cerberus: Cerberus):
        r = await cerberus.execute("quarantine_file", {"file_path": ""})
        assert r.success is False


# --- Stub tools (operational on Ubuntu only) ---


class TestNotOperationalStubs:
    """Tools registered but not yet operational must return success=True
    with a clear 'not_operational' message — never success=False."""

    @pytest.mark.asyncio
    async def test_firewall_status_stub(self, cerberus: Cerberus):
        r = await cerberus.execute("firewall_status", {})
        assert r.success is True
        assert r.content["status"] == "not_operational"
        assert "iptables" in r.content["message"] or "nftables" in r.content["message"]

    @pytest.mark.asyncio
    async def test_threat_scan_stub(self, cerberus: Cerberus):
        r = await cerberus.execute("threat_scan", {"scan_type": "full"})
        assert r.success is True
        assert r.content["status"] == "not_operational"
        assert "Suricata" in r.content["message"]

    @pytest.mark.asyncio
    async def test_network_monitor_stub(self, cerberus: Cerberus):
        r = await cerberus.execute("network_monitor", {"duration_seconds": 30})
        assert r.success is True
        assert r.content["status"] == "not_operational"
        assert "Zeek" in r.content["message"]

    @pytest.mark.asyncio
    async def test_vulnerability_scan_stub(self, cerberus: Cerberus):
        r = await cerberus.execute("vulnerability_scan", {"target": "localhost"})
        assert r.success is True
        assert r.content["status"] == "not_operational"
        assert "OpenVAS" in r.content["message"] or "GVM" in r.content["message"]

    @pytest.mark.asyncio
    async def test_log_analysis_stub(self, cerberus: Cerberus):
        r = await cerberus.execute("log_analysis", {"log_source": "syslog"})
        assert r.success is True
        assert r.content["status"] == "not_operational"
        assert "auditd" in r.content["message"]


# --- Module identity stamp ---


class TestModuleStamp:
    """Every absorbed-tool ToolResult must report module='cerberus' so the
    registry indexes the surface as part of Cerberus."""

    @pytest.mark.asyncio
    async def test_network_scan_module_stamp(self, cerberus: Cerberus):
        r = await cerberus.execute("network_scan", {})
        assert r.module == "cerberus"

    @pytest.mark.asyncio
    async def test_threat_assess_module_stamp(self, cerberus: Cerberus):
        r = await cerberus.execute("threat_assess", {"event": "test event"})
        assert r.module == "cerberus"

    @pytest.mark.asyncio
    async def test_firewall_status_module_stamp(self, cerberus: Cerberus):
        r = await cerberus.execute("firewall_status", {})
        assert r.module == "cerberus"
