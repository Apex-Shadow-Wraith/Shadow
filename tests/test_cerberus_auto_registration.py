"""
Tests for Cerberus Auto-Registration & Tool Classification
=============================================================
Verifies that new internally-created tools get auto-classified
and registered correctly, and that never_autonomous tools cannot
be overridden.
"""

import pytest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import yaml

from modules.base import BaseModule, ModuleRegistry, ModuleStatus, ToolResult
from modules.cerberus.cerberus import Cerberus, SafetyVerdict


# --- Minimal limits config with never_autonomous ---

LIMITS_WITH_NEVER_AUTONOMOUS = {
    "hard_limits": {
        "financial": ["Never access real bank accounts"],
        "data": ["Never share personal data externally without approval"],
        "system": ["Never disable or modify Cerberus"],
        "external": ["Never take external-facing actions without approval"],
        "rate_limits": {"max_file_operations_per_hour": 100},
    },
    "permission_tiers": {
        "tier_1_open": {"approval": "autonomous"},
    },
    "approval_required_tools": [
        "email_send",
        "browser_stealth",
    ],
    "autonomous_tools": [
        "memory_store",
        "memory_search",
        "safety_check",
    ],
    "never_autonomous": [
        "email_send",
        "notification_send",
        "browser_stealth",
        "file_delete",
        "software_install",
        "system_modify",
        "sandbox_to_production",
        "model_pull",
        "creator_exception",
        "creator_authorize",
    ],
    "hooks": {
        "pre_tool": {"deny": [], "modify": []},
        "post_tool": {"flag": []},
    },
}


@pytest.fixture
def limits_file(tmp_path: Path) -> Path:
    """Create a temporary Cerberus limits file with never_autonomous."""
    limits_path = tmp_path / "cerberus_limits.yaml"
    with open(limits_path, "w") as f:
        yaml.dump(LIMITS_WITH_NEVER_AUTONOMOUS, f)
    return limits_path


@pytest.fixture
async def cerberus(limits_file: Path, tmp_path: Path) -> Cerberus:
    """Create and initialize a Cerberus instance."""
    db_path = tmp_path / "cerberus_audit.db"
    config = {"limits_file": str(limits_file), "db_path": str(db_path)}
    c = Cerberus(config)
    await c.initialize()
    return c


# --- classify_new_tool Tests ---

class TestClassifyNewTool:
    @pytest.mark.asyncio
    async def test_internal_readonly_tool_autonomous(self, cerberus: Cerberus):
        """Internal read-only tool auto-classifies as autonomous."""
        result = cerberus.classify_new_tool(
            "pattern_analyze",
            {"description": "Analyze code patterns in the repository", "module": "omen"},
        )
        assert result == "autonomous"

    @pytest.mark.asyncio
    async def test_email_send_approval_required(self, cerberus: Cerberus):
        """Tool that sends email auto-classifies as approval_required."""
        result = cerberus.classify_new_tool(
            "report_email",
            {"description": "Send daily report via email", "module": "harbinger"},
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_delete_files_approval_required(self, cerberus: Cerberus):
        """Tool that deletes files auto-classifies as approval_required."""
        result = cerberus.classify_new_tool(
            "cleanup_old_logs",
            {"description": "Delete old log files from system", "module": "void"},
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_data_directory_write_autonomous(self, cerberus: Cerberus):
        """Tool that only writes to data/ auto-classifies as autonomous."""
        result = cerberus.classify_new_tool(
            "cache_store",
            {"description": "Store cached results in data/ directory", "module": "grimoire"},
        )
        assert result == "autonomous"

    @pytest.mark.asyncio
    async def test_external_module_approval_required(self, cerberus: Cerberus):
        """Tool from a non-internal module classifies as approval_required."""
        result = cerberus.classify_new_tool(
            "external_sync",
            {"description": "Sync data with remote", "module": "custom_plugin"},
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_credential_access_approval_required(self, cerberus: Cerberus):
        """Tool that accesses credentials classifies as approval_required."""
        result = cerberus.classify_new_tool(
            "key_rotate",
            {"description": "Rotate API key and update credential store", "module": "sentinel"},
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_financial_tool_approval_required(self, cerberus: Cerberus):
        """Tool that makes purchases classifies as approval_required."""
        result = cerberus.classify_new_tool(
            "process_payment",
            {"description": "Process a purchase transaction", "module": "nova"},
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_notification_tool_approval_required(self, cerberus: Cerberus):
        """Tool that sends notifications classifies as approval_required."""
        result = cerberus.classify_new_tool(
            "alert_push",
            {"description": "Send push notification to user", "module": "harbinger"},
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_ambiguous_metadata_defaults_approval(self, cerberus: Cerberus):
        """Tool with no description and no module defaults to approval_required."""
        result = cerberus.classify_new_tool(
            "mystery_tool",
            {"description": "", "module": ""},
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_security_read_tool_autonomous(self, cerberus: Cerberus):
        """Security tool that only reads/analyzes stays autonomous."""
        result = cerberus.classify_new_tool(
            "security_audit_check",
            {"description": "Check and analyze security configuration status", "module": "sentinel"},
        )
        assert result == "autonomous"

    @pytest.mark.asyncio
    async def test_data_delete_scoped_autonomous(self, cerberus: Cerberus):
        """Delete tool scoped to data/ directory is autonomous."""
        result = cerberus.classify_new_tool(
            "cache_purge",
            {"description": "Purge expired cache entries from data/ directory", "module": "grimoire"},
        )
        assert result == "autonomous"


# --- never_autonomous Tests ---

class TestNeverAutonomous:
    @pytest.mark.asyncio
    async def test_never_autonomous_blocks_classification(self, cerberus: Cerberus):
        """Never-autonomous tools cannot be classified as autonomous."""
        result = cerberus.classify_new_tool(
            "email_send",
            {"description": "Internal logging tool", "module": "wraith"},
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_never_autonomous_blocks_explicit_override(self, cerberus: Cerberus):
        """Never-autonomous tools cannot be overridden via auto_register_tool."""
        result = cerberus.auto_register_tool(
            tool_name="notification_send",
            module_name="harbinger",
            description="Send user notification",
            classification="autonomous",  # Explicitly trying to set autonomous
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_never_autonomous_file_delete(self, cerberus: Cerberus):
        """file_delete is always approval_required."""
        result = cerberus.auto_register_tool(
            tool_name="file_delete",
            module_name="omen",
            description="Delete a file from disk",
            classification="autonomous",
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_never_autonomous_creator_exception(self, cerberus: Cerberus):
        """creator_exception cannot be set autonomous."""
        result = cerberus.auto_register_tool(
            tool_name="creator_exception",
            module_name="cerberus",
            description="One-time override",
            classification="autonomous",
        )
        assert result == "approval_required"


# --- auto_register_tool Tests ---

class TestAutoRegisterTool:
    @pytest.mark.asyncio
    async def test_registers_autonomous_tool(self, cerberus: Cerberus):
        """Autonomous tool gets added to autonomous_tools list."""
        result = cerberus.auto_register_tool(
            tool_name="code_analyze",
            module_name="omen",
            description="Analyze code structure and complexity",
        )
        assert result == "autonomous"
        assert "code_analyze" in cerberus._limits["autonomous_tools"]

    @pytest.mark.asyncio
    async def test_registers_approval_tool(self, cerberus: Cerberus):
        """Approval-required tool gets added to approval_required_tools list."""
        result = cerberus.auto_register_tool(
            tool_name="webhook_post",
            module_name="harbinger",
            description="Send webhook notification to external service",
        )
        assert result == "approval_required"
        assert "webhook_post" in cerberus._limits["approval_required_tools"]

    @pytest.mark.asyncio
    async def test_explicit_classification_used(self, cerberus: Cerberus):
        """Explicit classification is used when provided."""
        result = cerberus.auto_register_tool(
            tool_name="custom_tool",
            module_name="wraith",
            description="Custom internal tool",
            classification="approval_required",
        )
        assert result == "approval_required"

    @pytest.mark.asyncio
    async def test_tracks_registration(self, cerberus: Cerberus):
        """Auto-registrations are tracked for daily report."""
        cerberus.auto_register_tool(
            tool_name="test_tool_1",
            module_name="omen",
            description="Test tool one",
        )
        cerberus.auto_register_tool(
            tool_name="test_tool_2",
            module_name="wraith",
            description="Test tool two",
        )
        regs = cerberus.get_auto_registrations()
        assert len(regs) == 2
        assert regs[0]["tool_name"] == "test_tool_1"
        assert regs[1]["tool_name"] == "test_tool_2"

    @pytest.mark.asyncio
    async def test_audit_log_entry(self, cerberus: Cerberus):
        """Auto-registration creates an audit log entry."""
        cerberus.auto_register_tool(
            tool_name="audit_test_tool",
            module_name="cipher",
            description="Math computation tool",
        )
        audit_entries = [
            e for e in cerberus._audit_log
            if e.get("type") == "auto_registration"
            and e.get("tool") == "audit_test_tool"
        ]
        assert len(audit_entries) == 1
        assert "autonomous" in audit_entries[0]["reason"]

    @pytest.mark.asyncio
    async def test_no_duplicate_registration(self, cerberus: Cerberus):
        """Registering the same tool twice doesn't create duplicates in lists."""
        cerberus.auto_register_tool(
            tool_name="dedup_tool",
            module_name="omen",
            description="Internal analysis tool",
        )
        cerberus.auto_register_tool(
            tool_name="dedup_tool",
            module_name="omen",
            description="Internal analysis tool",
        )
        count = cerberus._limits["autonomous_tools"].count("dedup_tool")
        assert count == 1


# --- Unknown tool at runtime auto-classification ---

class TestUnknownToolAutoClassification:
    @pytest.mark.asyncio
    async def test_unknown_tool_gets_auto_classified(self, cerberus: Cerberus):
        """Unknown tool at runtime gets auto-classified instead of blanket APPROVAL_REQUIRED."""
        # Verify the tool is NOT in any list before the check
        assert "code_metrics" not in cerberus._limits.get("autonomous_tools", [])
        assert "code_metrics" not in cerberus._limits.get("approval_required_tools", [])

        result = cerberus._safety_check(
            action_tool="code_metrics",
            action_params={
                "_tool_description": "Calculate code complexity metrics",
                "_requesting_module": "omen",
            },
            requesting_module="omen",
        )
        # Should be ALLOWED (not blanket APPROVAL_REQUIRED)
        assert result.verdict == SafetyVerdict.ALLOW
        # Should now be registered in autonomous_tools for future checks
        assert "code_metrics" in cerberus._limits["autonomous_tools"]

    @pytest.mark.asyncio
    async def test_unknown_external_tool_requires_approval(self, cerberus: Cerberus):
        """Unknown tool with external indicators still requires approval."""
        result = cerberus._safety_check(
            action_tool="slack_notify",
            action_params={
                "_tool_description": "Send notification to Slack channel",
                "_requesting_module": "harbinger",
            },
            requesting_module="harbinger",
        )
        assert result.verdict == SafetyVerdict.APPROVAL_REQUIRED

    @pytest.mark.asyncio
    async def test_unknown_tool_no_metadata_requires_approval(self, cerberus: Cerberus):
        """Unknown tool with no metadata defaults to approval_required."""
        result = cerberus._safety_check(
            action_tool="totally_unknown",
            action_params={},
            requesting_module="unknown",
        )
        assert result.verdict == SafetyVerdict.APPROVAL_REQUIRED


# --- BaseModule + ModuleRegistry integration ---

class _DummyModule(BaseModule):
    """Minimal module for testing registry integration."""

    def __init__(self, name: str, tools: list[dict[str, Any]]):
        super().__init__(name=name, description=f"Test module {name}")
        self._tools = tools

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, content="ok", tool_name=tool_name, module=self.name)

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return self._tools


class TestModuleRegistryAutoRegistration:
    @pytest.mark.asyncio
    async def test_registry_triggers_auto_register(self, cerberus: Cerberus):
        """ModuleRegistry.register triggers Cerberus auto_register_tool."""
        registry = ModuleRegistry()
        registry.set_cerberus(cerberus)

        module = _DummyModule("test_mod", [
            {
                "name": "test_internal_read",
                "description": "Read internal data structures",
                "parameters": {},
                "permission_level": "autonomous",
            },
        ])
        registry.register(module)

        assert "test_internal_read" in cerberus._limits["autonomous_tools"]
        regs = cerberus.get_auto_registrations()
        assert any(r["tool_name"] == "test_internal_read" for r in regs)

    @pytest.mark.asyncio
    async def test_registry_respects_never_autonomous(self, cerberus: Cerberus):
        """Registry registration respects never_autonomous even with autonomous permission_level."""
        registry = ModuleRegistry()
        registry.set_cerberus(cerberus)

        module = _DummyModule("test_mod2", [
            {
                "name": "email_send",
                "description": "Send email",
                "parameters": {},
                "permission_level": "autonomous",
            },
        ])
        registry.register(module)

        # email_send should be in approval list, not autonomous
        assert "email_send" in cerberus._limits["approval_required_tools"]

    @pytest.mark.asyncio
    async def test_registry_without_cerberus_works(self):
        """Registry works normally without Cerberus wired in."""
        registry = ModuleRegistry()
        module = _DummyModule("test_mod3", [
            {
                "name": "some_tool",
                "description": "A tool",
                "parameters": {},
                "permission_level": "autonomous",
            },
        ])
        # Should not raise
        registry.register(module)
        assert "test_mod3" in registry


# --- Daily Safety Report integration ---

class TestSafetyReportAutoRegistrations:
    @pytest.mark.asyncio
    async def test_stats_include_auto_registrations(self, cerberus: Cerberus):
        """Cerberus stats include auto-registration count and details."""
        cerberus.auto_register_tool(
            tool_name="stats_test_tool",
            module_name="omen",
            description="Internal stats tool",
        )
        stats = cerberus.stats
        assert stats["auto_registrations"] == 1
        assert len(stats["auto_registrations_detail"]) == 1
        assert stats["auto_registrations_detail"][0]["tool_name"] == "stats_test_tool"

    def test_safety_report_collects_auto_registrations(self):
        """DailySafetyReport collects auto_registration entries from audit log."""
        from modules.harbinger.safety_report import DailySafetyReport

        entries = [
            {
                "type": "auto_registration",
                "tool": "new_analyze_tool",
                "module": "omen",
                "reason": "Auto-registered as autonomous",
                "timestamp": "2026-04-07T10:00:00",
            },
            {
                "type": "auto_registration",
                "tool": "ext_webhook",
                "module": "harbinger",
                "reason": "Auto-registered as approval_required",
                "timestamp": "2026-04-07T10:01:00",
            },
            {
                "type": "denial",
                "tool": "email_send",
                "module": "wraith",
                "reason": "Blocked",
                "timestamp": "2026-04-07T10:02:00",
            },
        ]
        regs = DailySafetyReport._collect_auto_registrations(entries)
        assert len(regs) == 2
        assert regs[0]["tool"] == "new_analyze_tool"
        assert regs[0]["classification"] == "autonomous"
        assert regs[1]["tool"] == "ext_webhook"
        assert regs[1]["classification"] == "approval_required"

    def test_format_includes_auto_registrations(self):
        """format_for_harbinger includes auto-registration section."""
        from modules.harbinger.safety_report import DailySafetyReport

        report = {
            "date": "2026-04-07",
            "summary": {"total_actions": 5, "approved_autonomous": 3,
                        "approved_with_logging": 0, "deferred_to_queue": 1,
                        "blocked": 1, "modified": 0, "creator_exceptions": 0,
                        "creator_authorizations": 0},
            "blocks": [],
            "anomalies": [],
            "false_positive_rate": {"overall": 0.0, "total_blocks": 0,
                                     "total_resolved": 0, "by_category": {}},
            "calibration_alerts": [],
            "auto_registrations": [
                {"tool": "new_tool", "module": "omen",
                 "classification": "autonomous", "timestamp": "2026-04-07T10:00:00"},
            ],
        }
        formatted = DailySafetyReport.format_for_harbinger(report)
        assert "AUTO-REGISTERED TOOLS (1)" in formatted
        assert "new_tool" in formatted
        assert "omen" in formatted
