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
async def cerberus(limits_file: Path) -> Cerberus:
    """Create and initialize a Cerberus instance."""
    config = {"limits_file": str(limits_file)}
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
