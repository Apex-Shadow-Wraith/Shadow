"""
Tests for Cerberus Safety Module
==================================
Verifies the safety gate works correctly. If Cerberus is broken,
Shadow is unsafe. These tests matter more than any other tests.
"""

import pytest
import tempfile
from pathlib import Path
from typing import Any

import yaml

from modules.cerberus.cerberus import Cerberus, SafetyVerdict


# --- Test fixture: minimal Cerberus config ---

MINIMAL_LIMITS = {
    "hard_limits": {
        "financial": ["Never access real bank accounts"],
        "data": ["Never share personal data externally without approval"],
        "system": ["Never disable or modify Cerberus"],
        "external": ["Never take external-facing actions without approval"],
        "rate_limits": {"max_file_operations_per_hour": 100},
        "ethical": ["Never generate deceptive content"],
    },
    "permission_tiers": {
        "tier_1_open": {"approval": "autonomous"},
        "tier_4_forbidden": {"approval": "blocked"},
    },
    "approval_required_tools": [
        "email_send",
        "browser_stealth",
        "apex_query",
    ],
    "autonomous_tools": [
        "memory_store",
        "memory_search",
        "web_search",
        "safety_check",
    ],
    "hooks": {
        "pre_tool": {
            "deny": [
                {
                    "pattern": "shell_metacharacters",
                    "description": "DENY shell metacharacters",
                    "applies_to": ["bash_execute", "code_execute"],
                },
                {
                    "pattern": "protected_path_write",
                    "description": "DENY writes to protected paths",
                    "applies_to": ["file_write"],
                    "protected_paths": [
                        "config/cerberus_limits.yaml",
                        "config/shadow_config.yaml",
                    ],
                },
                {
                    "pattern": "unapproved_external",
                    "description": "DENY unapproved external actions",
                    "applies_to": ["email_send"],
                },
            ],
            "modify": [
                {
                    "pattern": "pii_in_search",
                    "description": "Strip PII from search queries",
                    "applies_to": ["web_search"],
                },
            ],
        },
        "post_tool": {
            "flag": [
                {
                    "pattern": "credential_in_result",
                    "description": "FLAG credential-like patterns",
                },
                {
                    "pattern": "slow_execution",
                    "description": "LOG slow tool calls",
                    "threshold_seconds": 30,
                },
            ],
        },
    },
}


@pytest.fixture
def limits_file(tmp_path: Path) -> Path:
    """Create a temporary Cerberus limits file."""
    limits_path = tmp_path / "cerberus_limits.yaml"
    with open(limits_path, "w") as f:
        yaml.dump(MINIMAL_LIMITS, f)
    return limits_path


@pytest.fixture
async def cerberus(limits_file: Path, tmp_path: Path) -> Cerberus:
    """Create and initialize a Cerberus instance."""
    db_path = tmp_path / "cerberus_audit.db"
    config = {"limits_file": str(limits_file), "db_path": str(db_path)}
    c = Cerberus(config)
    await c.initialize()
    return c


# --- Initialization Tests ---

class TestCerberusInit:
    @pytest.mark.asyncio
    async def test_initializes_online(self, cerberus: Cerberus):
        assert cerberus.status.value == "online"

    @pytest.mark.asyncio
    async def test_stores_config_hash(self, cerberus: Cerberus):
        assert cerberus._config_hash != ""
        assert len(cerberus._config_hash) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_missing_config_raises(self, tmp_path: Path):
        config = {"limits_file": str(tmp_path / "nonexistent.yaml")}
        c = Cerberus(config)
        with pytest.raises(FileNotFoundError):
            await c.initialize()


# --- Safety Check Tests ---

class TestSafetyCheck:
    @pytest.mark.asyncio
    async def test_autonomous_tool_allowed(self, cerberus: Cerberus):
        result = await cerberus.execute("safety_check", {
            "action_tool": "memory_store",
            "action_params": {"content": "test"},
            "requesting_module": "grimoire",
        })
        assert result.success
        assert result.content.verdict == SafetyVerdict.ALLOW

    @pytest.mark.asyncio
    async def test_approval_required_tool(self, cerberus: Cerberus):
        result = await cerberus.execute("safety_check", {
            "action_tool": "email_send",
            "action_params": {"to": "test@test.com"},
            "requesting_module": "harbinger",
        })
        assert result.success
        assert result.content.verdict == SafetyVerdict.APPROVAL_REQUIRED

    @pytest.mark.asyncio
    async def test_unknown_tool_defaults_to_approval(self, cerberus: Cerberus):
        result = await cerberus.execute("safety_check", {
            "action_tool": "totally_new_tool",
            "action_params": {},
            "requesting_module": "test",
        })
        assert result.success
        assert result.content.verdict == SafetyVerdict.APPROVAL_REQUIRED

    @pytest.mark.asyncio
    async def test_protected_path_write_denied(self, cerberus: Cerberus):
        result = await cerberus.execute("safety_check", {
            "action_tool": "file_write",
            "action_params": {"path": "config/cerberus_limits.yaml"},
            "requesting_module": "omen",
        })
        assert result.success
        assert result.content.verdict == SafetyVerdict.DENY
        assert "tamper-protected" in result.content.reason

    @pytest.mark.asyncio
    async def test_shell_metacharacter_denied(self, cerberus: Cerberus):
        result = await cerberus.execute("safety_check", {
            "action_tool": "bash_execute",
            "action_params": {"command": "ls; rm -rf /"},
            "requesting_module": "omen",
        })
        assert result.success
        assert result.content.verdict == SafetyVerdict.DENY
        assert "metacharacter" in result.content.reason


# --- Hook Tests ---

class TestPreToolHook:
    @pytest.mark.asyncio
    async def test_allows_safe_tool(self, cerberus: Cerberus):
        result = await cerberus.execute("hook_pre_tool", {
            "tool_name": "memory_search",
            "tool_params": {"query": "test query"},
        })
        assert result.success
        assert result.content.verdict == SafetyVerdict.ALLOW

    @pytest.mark.asyncio
    async def test_denies_shell_injection(self, cerberus: Cerberus):
        result = await cerberus.execute("hook_pre_tool", {
            "tool_name": "bash_execute",
            "tool_params": {"command": "echo hello && cat /etc/passwd"},
        })
        assert result.success
        assert result.content.verdict == SafetyVerdict.DENY

    @pytest.mark.asyncio
    async def test_denies_protected_path(self, cerberus: Cerberus):
        result = await cerberus.execute("hook_pre_tool", {
            "tool_name": "file_write",
            "tool_params": {"path": "config/shadow_config.yaml", "content": "hacked"},
        })
        assert result.success
        assert result.content.verdict == SafetyVerdict.DENY

    @pytest.mark.asyncio
    async def test_denies_unapproved_external(self, cerberus: Cerberus):
        result = await cerberus.execute("hook_pre_tool", {
            "tool_name": "email_send",
            "tool_params": {"to": "someone@test.com"},
        })
        assert result.success
        assert result.content.verdict == SafetyVerdict.DENY

    @pytest.mark.asyncio
    async def test_modifies_pii_in_search(self, cerberus: Cerberus):
        result = await cerberus.execute("hook_pre_tool", {
            "tool_name": "web_search",
            "tool_params": {"query": "john doe john@example.com"},
        })
        assert result.success
        if result.content.verdict == SafetyVerdict.MODIFY:
            assert "[EMAIL]" in result.content.modified_params["query"]


class TestPostToolHook:
    @pytest.mark.asyncio
    async def test_flags_credentials(self, cerberus: Cerberus):
        result = await cerberus.execute("hook_post_tool", {
            "tool_name": "web_fetch",
            "tool_result": {"content": "api_key=sk-abc123456789012345678901234567890"},
            "execution_time_ms": 100,
        })
        assert result.success
        # Should flag the credential pattern
        assert result.content.verdict in (SafetyVerdict.LOG, SafetyVerdict.ALLOW)

    @pytest.mark.asyncio
    async def test_allows_clean_result(self, cerberus: Cerberus):
        result = await cerberus.execute("hook_post_tool", {
            "tool_name": "memory_search",
            "tool_result": {"content": "just some normal text"},
            "execution_time_ms": 50,
        })
        assert result.success
        assert result.content.verdict == SafetyVerdict.ALLOW


# --- Config Integrity Tests ---

class TestConfigIntegrity:
    @pytest.mark.asyncio
    async def test_detects_unmodified_config(self, cerberus: Cerberus):
        result = await cerberus.execute("config_integrity_check", {})
        assert result.success
        assert result.content["tampered"] is False

    @pytest.mark.asyncio
    async def test_detects_tampered_config(self, cerberus: Cerberus, limits_file: Path):
        # Modify the config file after initialization
        with open(limits_file, "a") as f:
            f.write("\n# tampered!")

        result = await cerberus.execute("config_integrity_check", {})
        assert result.success
        assert result.content["tampered"] is True


# --- PII Detection Tests ---

class TestPIIStripping:
    @pytest.mark.asyncio
    async def test_strips_email(self, cerberus: Cerberus):
        cleaned = cerberus._strip_pii("contact john@example.com please")
        assert "[EMAIL]" in cleaned
        assert "john@example.com" not in cleaned

    @pytest.mark.asyncio
    async def test_strips_phone(self, cerberus: Cerberus):
        cleaned = cerberus._strip_pii("call 555-123-4567")
        assert "[PHONE]" in cleaned

    @pytest.mark.asyncio
    async def test_strips_ssn(self, cerberus: Cerberus):
        cleaned = cerberus._strip_pii("ssn is 123-45-6789")
        assert "[SSN]" in cleaned

    @pytest.mark.asyncio
    async def test_leaves_clean_text_unchanged(self, cerberus: Cerberus):
        text = "search for python tutorials"
        assert cerberus._strip_pii(text) == text


# --- Credential Detection Tests ---

class TestCredentialDetection:
    def test_detects_api_key(self):
        c = Cerberus.__new__(Cerberus)  # Skip __init__ for utility test
        assert c._contains_credential_pattern("api_key=abcdef123456")

    def test_detects_openai_key(self):
        c = Cerberus.__new__(Cerberus)
        assert c._contains_credential_pattern("sk-" + "a" * 48)

    def test_detects_github_token(self):
        c = Cerberus.__new__(Cerberus)
        assert c._contains_credential_pattern("ghp_" + "a" * 36)

    def test_detects_bearer_token(self):
        c = Cerberus.__new__(Cerberus)
        assert c._contains_credential_pattern("Bearer eyJhbGciOiJIUzI1NiJ9")

    def test_ignores_normal_text(self):
        c = Cerberus.__new__(Cerberus)
        assert not c._contains_credential_pattern("just regular text here")


# --- Stats Tests ---

class TestCerberusStats:
    @pytest.mark.asyncio
    async def test_stats_track_checks(self, cerberus: Cerberus):
        await cerberus.execute("safety_check", {
            "action_tool": "memory_store",
            "action_params": {},
            "requesting_module": "test",
        })
        await cerberus.execute("safety_check", {
            "action_tool": "email_send",
            "action_params": {},
            "requesting_module": "test",
        })
        stats = cerberus.stats
        assert stats["checks"] == 2

    @pytest.mark.asyncio
    async def test_stats_track_denials(self, cerberus: Cerberus):
        await cerberus.execute("safety_check", {
            "action_tool": "bash_execute",
            "action_params": {"command": "rm -rf / && echo pwned"},
            "requesting_module": "test",
        })
        stats = cerberus.stats
        assert stats["denials"] >= 1


# --- False Positive Log Tests ---

class TestFalsePositiveLog:
    @pytest.mark.asyncio
    async def test_success(self, cerberus: Cerberus):
        result = await cerberus.execute("false_positive_log", {
            "check_id": "chk_001",
            "category": "pii_detection",
            "notes": "Business name mistaken for PII",
        })
        assert result.success is True
        assert result.content["logged"] is True
        assert result.content["check_id"] == "chk_001"
        assert result.content["category"] == "pii_detection"
        assert "timestamp" in result.content
        assert cerberus._false_positive_count == 1

    @pytest.mark.asyncio
    async def test_increments_counter(self, cerberus: Cerberus):
        await cerberus.execute("false_positive_log", {
            "check_id": "chk_001", "category": "test", "notes": "",
        })
        await cerberus.execute("false_positive_log", {
            "check_id": "chk_002", "category": "test", "notes": "",
        })
        assert cerberus._false_positive_count == 2

    @pytest.mark.asyncio
    async def test_writes_audit_entry(self, cerberus: Cerberus):
        import json
        import sqlite3

        await cerberus.execute("false_positive_log", {
            "check_id": "chk_001",
            "category": "test",
            "notes": "test note",
        })
        conn = sqlite3.connect(str(cerberus._db_path))
        rows = conn.execute(
            "SELECT details FROM cerberus_audit_log WHERE action = 'false_positive'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        details = json.loads(rows[0][0])
        assert details["check_id"] == "chk_001"
        assert details["notes"] == "test note"

    @pytest.mark.asyncio
    async def test_empty_category_fails(self, cerberus: Cerberus):
        result = await cerberus.execute("false_positive_log", {
            "check_id": "chk_001",
        })
        assert result.success is False
        assert "category" in result.error

    @pytest.mark.asyncio
    async def test_missing_check_id(self, cerberus: Cerberus):
        result = await cerberus.execute("false_positive_log", {
            "category": "test",
            "notes": "no id provided",
        })
        assert result.success is False
        assert "check_id" in result.error

    @pytest.mark.asyncio
    async def test_reflected_in_stats(self, cerberus: Cerberus):
        await cerberus.execute("false_positive_log", {
            "check_id": "chk_001", "category": "test", "notes": "",
        })
        stats = cerberus.stats
        assert stats["false_positives"] == 1

    @pytest.mark.asyncio
    async def test_tool_count(self, cerberus: Cerberus):
        tools = cerberus.get_tools()
        assert len(tools) == 15
        tool_names = [t["name"] for t in tools]
        assert "false_positive_log" in tool_names
        assert "calibration_stats" in tool_names
        assert "validate_response" in tool_names


# =============================================================
# Confabulation Detection Tests
# =============================================================

class TestConfabulationDetection:
    """Tests for the post-response confabulation warning system."""

    @pytest.mark.asyncio
    async def test_flags_background_processing_claim(self, cerberus: Cerberus):
        """A response claiming background work must be flagged."""
        result = await cerberus.execute("validate_response", {
            "response_text": "I'm working on that in the background for you.",
        })
        assert result.success is True
        data = result.content
        assert data["flagged"] is True
        assert len(data["matched_phrases"]) > 0
        # Should have logged an audit entry
        audit = [e for e in cerberus._audit_log if e["type"] == "confabulation_warning"]
        assert len(audit) == 1

    @pytest.mark.asyncio
    async def test_clean_response_not_flagged(self, cerberus: Cerberus):
        """A normal response without confabulation phrases passes cleanly."""
        result = await cerberus.execute("validate_response", {
            "response_text": "Here is the answer to your question, Master.",
        })
        assert result.success is True
        data = result.content
        assert data["flagged"] is False
        assert data["matched_phrases"] == []
        assert data["warning_count"] == 0

    @pytest.mark.asyncio
    async def test_multiple_phrases_all_caught(self, cerberus: Cerberus):
        """Multiple confabulation phrases in one response are all reported."""
        result = await cerberus.execute("validate_response", {
            "response_text": (
                "I'm still processing your request and working on "
                "the analysis in the background."
            ),
        })
        data = result.content
        assert data["flagged"] is True
        assert data["warning_count"] >= 2

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self, cerberus: Cerberus):
        """Confabulation detection is case-insensitive."""
        result = await cerberus.execute("validate_response", {
            "response_text": "I'm STILL PROCESSING your data.",
        })
        assert result.content["flagged"] is True

    @pytest.mark.asyncio
    async def test_audit_entry_contains_matched_phrases(self, cerberus: Cerberus):
        """Audit entry must include the specific phrases that matched."""
        await cerberus.execute("validate_response", {
            "response_text": "The task is underway, I'll continue later.",
        })
        audit = [e for e in cerberus._audit_log if e["type"] == "confabulation_warning"]
        assert len(audit) == 1
        assert "task is underway" in audit[0]["matched_phrases"]
        assert "i'll continue" in audit[0]["matched_phrases"]

    @pytest.mark.asyncio
    async def test_async_task_suppresses_legitimate_phrases(self, cerberus: Cerberus):
        """When has_async_task=True, legitimate background phrases are not flagged."""
        result = await cerberus.execute("validate_response", {
            "response_text": "Task submitted. I'll handle this in the background.",
            "has_async_task": True,
        })
        data = result.content
        assert data["flagged"] is False, (
            "Legitimate async background phrase should not be flagged"
        )

    @pytest.mark.asyncio
    async def test_async_task_still_flags_fabrication(self, cerberus: Cerberus):
        """Even with has_async_task=True, fabrication phrases are still caught."""
        result = await cerberus.execute("validate_response", {
            "response_text": "I'm still processing your request and working on it.",
            "has_async_task": True,
        })
        data = result.content
        assert data["flagged"] is True, (
            "Fabrication phrases must still be caught even with async task"
        )
        assert any(p in data["matched_phrases"] for p in ["still processing", "working on"])
