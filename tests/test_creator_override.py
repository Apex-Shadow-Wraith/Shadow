"""
Tests for Creator Override System
====================================
Verifies that the creator can override Cerberus blocks with proper
authentication, and that safety invariants hold:
- Tier 4 forbidden actions NEVER overridden
- Internal modules NEVER allowed to call overrides
- One-time exceptions don't change rules
- Authorizations permanently reclassify categories
"""

import os
import tempfile
from pathlib import Path

import pytest

from modules.cerberus.creator_override import (
    EXTERNAL_SOURCES,
    INTERNAL_MODULES,
    TIER_4_FORBIDDEN,
    CreatorOverride,
    OverrideResult,
)


# --- Fixtures ---

TEST_TOKEN = "test-creator-token-12345"


@pytest.fixture
def env_file(tmp_path):
    """Create a temp .env file with a known auth token."""
    env = tmp_path / ".env"
    env.write_text(f"CREATOR_AUTH_TOKEN={TEST_TOKEN}\n", encoding="utf-8")
    return str(env)


@pytest.fixture
def override(env_file):
    """CreatorOverride with a known token."""
    return CreatorOverride(env_path=env_file)


@pytest.fixture
def override_no_token(tmp_path):
    """CreatorOverride with no token configured."""
    env = tmp_path / ".env"
    env.write_text("OTHER_VAR=hello\n", encoding="utf-8")
    return CreatorOverride(env_path=str(env))


# --- creator_exception tests ---


class TestCreatorException:
    """Tests for one-time exception overrides."""

    def test_exception_allows_one_time(self, override):
        """creator_exception grants a one-time pass."""
        result = override.creator_exception(
            blocked_action_id="blocked-abc123",
            auth_token=TEST_TOKEN,
            action_category="shell_metacharacters",
        )
        assert result.success is True
        assert result.override_type == "exception"
        assert "one-time" in result.reason.lower() or "exception" in result.reason.lower()

    def test_exception_does_not_learn(self, override):
        """After exception, the category is NOT permanently authorized."""
        override.creator_exception(
            blocked_action_id="blocked-abc123",
            auth_token=TEST_TOKEN,
            action_category="shell_metacharacters",
        )
        # Category should still be blocked next time
        assert not override.is_category_authorized("shell_metacharacters")

    def test_exception_blocks_next_time(self, override):
        """Calling exception once doesn't prevent future blocks."""
        # First call succeeds
        r1 = override.creator_exception(
            blocked_action_id="blocked-001",
            auth_token=TEST_TOKEN,
            action_category="shell_metacharacters",
        )
        assert r1.success is True

        # Category is NOT learned — Cerberus will block the same action next time
        assert not override.is_category_authorized("shell_metacharacters")

    def test_exception_invalid_token(self, override):
        """Invalid auth token is rejected."""
        result = override.creator_exception(
            blocked_action_id="blocked-abc123",
            auth_token="wrong-token",
            action_category="shell_metacharacters",
        )
        assert result.success is False
        assert "authentication" in result.reason.lower() or "invalid" in result.reason.lower()

    def test_exception_tier4_forbidden(self, override):
        """Tier 4 forbidden actions cannot be overridden by exception."""
        for forbidden in TIER_4_FORBIDDEN:
            result = override.creator_exception(
                blocked_action_id=f"blocked-{forbidden}",
                auth_token=TEST_TOKEN,
                action_category=forbidden,
            )
            assert result.success is False
            assert "tier 4" in result.reason.lower() or "forbidden" in result.reason.lower()

    def test_exception_internal_module_rejected(self, override):
        """Internal modules cannot call creator_exception."""
        for module in INTERNAL_MODULES:
            result = override.creator_exception(
                blocked_action_id="blocked-abc123",
                auth_token=TEST_TOKEN,
                action_category="shell_metacharacters",
                source=module,
            )
            assert result.success is False
            assert "not authorized" in result.reason.lower()

    def test_exception_logged(self, override):
        """Exceptions are logged with timestamp and details."""
        override.creator_exception(
            blocked_action_id="blocked-log-test",
            auth_token=TEST_TOKEN,
            action_category="pii_in_search",
            action_details={"query": "test"},
        )
        assert len(override._exception_log) == 1
        entry = override._exception_log[0]
        assert entry["action_id"] == "blocked-log-test"
        assert entry["action_category"] == "pii_in_search"
        assert "timestamp" in entry


# --- creator_authorize tests ---


class TestCreatorAuthorize:
    """Tests for permanent authorization overrides."""

    def test_authorize_updates_permanently(self, override):
        """creator_authorize permanently reclassifies a category."""
        result = override.creator_authorize(
            blocked_action_id="blocked-xyz789",
            auth_token=TEST_TOKEN,
            reasoning="This tool is safe for our use case",
            action_category="custom_tool_access",
        )
        assert result.success is True
        assert result.override_type == "authorize"
        # Category is now permanently authorized
        assert override.is_category_authorized("custom_tool_access")

    def test_authorize_requires_reasoning(self, override):
        """creator_authorize rejects empty reasoning."""
        result = override.creator_authorize(
            blocked_action_id="blocked-xyz789",
            auth_token=TEST_TOKEN,
            reasoning="",
            action_category="custom_tool_access",
        )
        assert result.success is False
        assert "reasoning" in result.reason.lower()

    def test_authorize_requires_nonempty_reasoning(self, override):
        """creator_authorize rejects whitespace-only reasoning."""
        result = override.creator_authorize(
            blocked_action_id="blocked-xyz789",
            auth_token=TEST_TOKEN,
            reasoning="   ",
            action_category="custom_tool_access",
        )
        assert result.success is False

    def test_authorize_invalid_token(self, override):
        """Invalid auth token rejected for authorize."""
        result = override.creator_authorize(
            blocked_action_id="blocked-xyz789",
            auth_token="bad-token",
            reasoning="Doesn't matter",
            action_category="custom_tool_access",
        )
        assert result.success is False
        assert "authentication" in result.reason.lower() or "invalid" in result.reason.lower()

    def test_authorize_tier4_forbidden(self, override):
        """Tier 4 forbidden actions cannot be authorized permanently."""
        for forbidden in TIER_4_FORBIDDEN:
            result = override.creator_authorize(
                blocked_action_id=f"blocked-{forbidden}",
                auth_token=TEST_TOKEN,
                reasoning="I really want to",
                action_category=forbidden,
            )
            assert result.success is False
            assert "tier 4" in result.reason.lower() or "forbidden" in result.reason.lower()

    def test_authorize_internal_module_rejected(self, override):
        """Internal modules cannot call creator_authorize."""
        for module in INTERNAL_MODULES:
            result = override.creator_authorize(
                blocked_action_id="blocked-abc123",
                auth_token=TEST_TOKEN,
                reasoning="Some reasoning",
                action_category="custom_tool_access",
                source=module,
            )
            assert result.success is False
            assert "not authorized" in result.reason.lower()

    def test_authorize_logged_with_reasoning(self, override):
        """Authorizations are logged with reasoning stored permanently."""
        override.creator_authorize(
            blocked_action_id="blocked-auth-log",
            auth_token=TEST_TOKEN,
            reasoning="Needed for landscaping billing",
            action_category="billing_access",
        )
        assert len(override._authorize_log) == 1
        entry = override._authorize_log[0]
        assert entry["reasoning"] == "Needed for landscaping billing"
        assert entry["action_category"] == "billing_access"


# --- False positive report tests ---


class TestFalsePositiveReport:
    """Tests for false positive tracking and reporting."""

    def test_empty_report(self, override):
        """No exceptions = empty report."""
        report = override.get_false_positive_report()
        assert report["total_exceptions"] == 0
        assert report["categories"] == {}
        assert report["flagged_for_calibration"] == []

    def test_counts_exceptions_per_category(self, override):
        """Tracks exception counts per category."""
        for _ in range(5):
            override.creator_exception(
                blocked_action_id="blocked-x",
                auth_token=TEST_TOKEN,
                action_category="shell_metacharacters",
            )
        for _ in range(2):
            override.creator_exception(
                blocked_action_id="blocked-y",
                auth_token=TEST_TOKEN,
                action_category="pii_in_search",
            )

        report = override.get_false_positive_report()
        assert report["total_exceptions"] == 7
        assert report["categories"]["shell_metacharacters"] == 5
        assert report["categories"]["pii_in_search"] == 2

    def test_flags_frequent_categories(self, override):
        """Categories with >= 3 exceptions are flagged for calibration."""
        for _ in range(3):
            override.creator_exception(
                blocked_action_id="blocked-cal",
                auth_token=TEST_TOKEN,
                action_category="overly_strict_rule",
            )

        report = override.get_false_positive_report()
        flagged = report["flagged_for_calibration"]
        assert len(flagged) == 1
        assert flagged[0]["category"] == "overly_strict_rule"
        assert flagged[0]["recommendation"] == "calibration_needed"

    def test_unflagged_low_count(self, override):
        """Categories with < 3 exceptions are not flagged."""
        for _ in range(2):
            override.creator_exception(
                blocked_action_id="blocked-ok",
                auth_token=TEST_TOKEN,
                action_category="minor_issue",
            )

        report = override.get_false_positive_report()
        assert report["flagged_for_calibration"] == []

    def test_report_includes_authorized_categories(self, override):
        """Report includes list of permanently authorized categories."""
        override.creator_authorize(
            blocked_action_id="blocked-auth",
            auth_token=TEST_TOKEN,
            reasoning="Safe for use",
            action_category="approved_tool",
        )
        report = override.get_false_positive_report()
        assert "approved_tool" in report["authorized_categories"]


# --- Authentication tests ---


class TestAuthentication:
    """Tests for auth token verification."""

    def test_no_token_configured_rejects_all(self, override_no_token):
        """With no token configured, all overrides are rejected."""
        result = override_no_token.creator_exception(
            blocked_action_id="blocked-no-auth",
            auth_token="anything",
            action_category="test",
        )
        assert result.success is False

    def test_verify_hardware_auth_valid(self, override):
        """Valid token passes verification."""
        assert override.verify_hardware_auth(TEST_TOKEN) is True

    def test_verify_hardware_auth_invalid(self, override):
        """Invalid token fails verification."""
        assert override.verify_hardware_auth("wrong") is False

    def test_env_var_fallback(self, tmp_path):
        """Token can be loaded from environment variable."""
        env = tmp_path / ".env"
        env.write_text("OTHER=value\n", encoding="utf-8")
        os.environ["CREATOR_AUTH_TOKEN"] = "env-var-token"
        try:
            co = CreatorOverride(env_path=str(env))
            assert co.verify_hardware_auth("env-var-token") is True
        finally:
            del os.environ["CREATOR_AUTH_TOKEN"]


# --- Source validation tests ---


class TestSourceValidation:
    """Tests that only external sources can invoke overrides."""

    def test_external_sources_accepted(self, override):
        """All defined external sources are accepted."""
        for source in EXTERNAL_SOURCES:
            result = override.creator_exception(
                blocked_action_id="blocked-src",
                auth_token=TEST_TOKEN,
                action_category="test_cat",
                source=source,
            )
            assert result.success is True, f"Source '{source}' should be accepted"

    def test_unknown_source_rejected(self, override):
        """Unknown sources are rejected."""
        result = override.creator_exception(
            blocked_action_id="blocked-unk",
            auth_token=TEST_TOKEN,
            action_category="test_cat",
            source="random_script",
        )
        assert result.success is False


# --- Blocked action ID generation ---


class TestBlockedActionId:
    """Tests for blocked action ID generation."""

    def test_generates_unique_ids(self, override):
        """Each call generates a unique blocked action ID."""
        ids = {override.generate_blocked_action_id() for _ in range(100)}
        assert len(ids) == 100

    def test_id_format(self, override):
        """IDs follow the blocked-{hex} format."""
        action_id = override.generate_blocked_action_id()
        assert action_id.startswith("blocked-")
        assert len(action_id) == 20  # "blocked-" (8) + 12 hex chars
