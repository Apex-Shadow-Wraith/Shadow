"""
Tests for Apex — API Fallback and Active Learning
===================================================
Covers API key loading, cost tracking, call logging, API selection,
teaching cycle, persistence, dry-run gating, and live API dispatch.
"""

import json
import os
import pytest
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

from modules.base import ModuleStatus, ToolResult
from modules.apex.apex import Apex


@pytest.fixture
def apex(tmp_path: Path) -> Apex:
    """Create an Apex instance with a temp log file (dry_run=False by default)."""
    config = {"log_file": str(tmp_path / "apex_log.json")}
    return Apex(config)


@pytest.fixture
def dry_run_apex(tmp_path: Path) -> Apex:
    """Create an Apex instance with dry_run explicitly enabled."""
    config = {"log_file": str(tmp_path / "apex_log.json"), "dry_run": True}
    return Apex(config)


@pytest.fixture
async def online_apex(apex: Apex) -> Apex:
    """Create and initialize Apex (no API keys)."""
    with patch("dotenv.load_dotenv"):
        await apex.initialize()
    return apex


# --- Lifecycle tests ---

class TestApexLifecycle:
    @pytest.mark.asyncio
    async def test_initialize_sets_online(self, apex: Apex):
        with patch("dotenv.load_dotenv"):
            await apex.initialize()
        assert apex.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown_sets_offline(self, apex: Apex):
        with patch("dotenv.load_dotenv"):
            await apex.initialize()
        await apex.shutdown()
        assert apex.status == ModuleStatus.OFFLINE

    def test_get_tools_returns_all(self, apex: Apex):
        tools = apex.get_tools()
        assert len(tools) == 10
        names = [t["name"] for t in tools]
        assert "apex_query" in names
        assert "apex_teach" in names
        assert "apex_log" in names
        assert "apex_cost_report" in names
        assert "apex_clear_history" in names
        assert "escalation_stats" in names
        assert "escalation_frequent" in names
        assert "teaching_review" in names
        assert "training_stats" in names
        assert "training_export" in names

    def test_all_tools_have_required_fields(self, apex: Apex):
        for tool in apex.get_tools():
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "permission_level" in tool


# --- API key tests ---

class TestAPIKeys:
    @pytest.mark.asyncio
    async def test_no_keys_warning(self, apex: Apex):
        with patch.dict(os.environ, {}, clear=True), \
             patch("dotenv.load_dotenv"):
            await apex.initialize()
            assert apex.status == ModuleStatus.ONLINE
            assert apex._anthropic_key is None
            assert apex._openai_key is None

    @pytest.mark.asyncio
    async def test_anthropic_key_loaded(self, apex: Apex):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-123"}), \
             patch("dotenv.load_dotenv"):
            await apex.initialize()
            assert apex._anthropic_key == "sk-test-123"

    @pytest.mark.asyncio
    async def test_openai_key_loaded(self, apex: Apex):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}), \
             patch("dotenv.load_dotenv"):
            await apex.initialize()
            assert apex._openai_key == "sk-openai-test"


# --- API selection ---

class TestAPISelection:
    @pytest.mark.asyncio
    async def test_claude_preferred(self, apex: Apex):
        apex._anthropic_key = "sk-ant"
        apex._openai_key = "sk-oai"
        assert apex._select_api("claude") == "claude"

    @pytest.mark.asyncio
    async def test_openai_when_preferred(self, apex: Apex):
        apex._anthropic_key = "sk-ant"
        apex._openai_key = "sk-oai"
        assert apex._select_api("openai") == "openai"

    @pytest.mark.asyncio
    async def test_claude_fallback_when_no_openai(self, apex: Apex):
        apex._anthropic_key = "sk-ant"
        apex._openai_key = None
        assert apex._select_api("openai") == "claude"

    @pytest.mark.asyncio
    async def test_openai_fallback_when_no_claude(self, apex: Apex):
        apex._anthropic_key = None
        apex._openai_key = "sk-oai"
        assert apex._select_api("claude") == "openai"

    @pytest.mark.asyncio
    async def test_none_when_no_keys(self, apex: Apex):
        apex._anthropic_key = None
        apex._openai_key = None
        assert apex._select_api("claude") == "none"


# --- Query tests ---

class TestApexQuery:
    @pytest.mark.asyncio
    async def test_query_no_keys_fails(self, online_apex: Apex):
        online_apex._anthropic_key = None
        online_apex._openai_key = None
        result = await online_apex.execute("apex_query", {"task": "Test query"})
        assert result.success is False
        assert "No API keys" in result.error

    @pytest.mark.asyncio
    async def test_query_empty_task_fails(self, online_apex: Apex):
        result = await online_apex.execute("apex_query", {"task": ""})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_query_logged(self, online_apex: Apex):
        """With key + dry_run=False, a live call is attempted (mocked)."""
        online_apex._anthropic_key = "sk-test"
        with patch.object(online_apex, "_call_claude", return_value=("Test response", 10, 20, "claude-sonnet-4-20250514")):
            await online_apex.execute("apex_query", {"task": "Test"})
        assert len(online_apex._call_log) == 1
        assert online_apex._call_log[0]["status"] == "completed"


# --- Dry-run gating tests ---

class TestDryRunGating:
    @pytest.mark.asyncio
    async def test_dry_run_true_skips_api_call(self, dry_run_apex: Apex):
        """dry_run=True with a valid key should NOT call the API and returns failure."""
        with patch("dotenv.load_dotenv"):
            await dry_run_apex.initialize()
        dry_run_apex._anthropic_key = "sk-test"
        with patch.object(dry_run_apex, "_call_claude") as mock_call:
            result = await dry_run_apex.execute("apex_query", {"task": "Should be skipped"})
            mock_call.assert_not_called()
        assert result.success is False
        assert result.content["status"] == "dry_run"
        assert result.content["source"] == "dry_run"
        assert "dry-run" in result.error.lower()

    @pytest.mark.asyncio
    async def test_dry_run_false_with_key_calls_api(self, online_apex: Apex):
        """dry_run=False (default) with a valid key should make a real API call."""
        online_apex._anthropic_key = "sk-test"
        with patch.object(online_apex, "_call_claude", return_value=("Live response", 15, 25, "claude-sonnet-4-20250514")) as mock_call:
            result = await online_apex.execute("apex_query", {"task": "What is Python?"})
            mock_call.assert_called_once()
        assert result.success is True
        assert result.content["status"] == "completed"
        assert result.content["source"] == "claude_api"
        assert result.content["response"] == "Live response"
        assert result.content["tokens_in"] == 15
        assert result.content["tokens_out"] == 25

    @pytest.mark.asyncio
    async def test_missing_keys_fallback_to_dry_run(self, online_apex: Apex):
        """No API keys should return failure with dry-run warning, no API call."""
        online_apex._anthropic_key = None
        online_apex._openai_key = None
        result = await online_apex.execute("apex_query", {"task": "No keys"})
        assert result.success is False
        assert "No API keys" in result.error
        assert len(online_apex._call_log) == 1
        assert online_apex._call_log[0]["status"] == "dry_run"

    @pytest.mark.asyncio
    async def test_live_call_openai(self, online_apex: Apex):
        """OpenAI preference with key should call OpenAI API."""
        online_apex._openai_key = "sk-oai-test"
        online_apex._anthropic_key = None
        with patch.object(online_apex, "_call_openai", return_value=("OpenAI response", 12, 18, "gpt-4o")) as mock_call:
            result = await online_apex.execute("apex_query", {
                "task": "Test OpenAI",
                "model_preference": "openai",
            })
            mock_call.assert_called_once()
        assert result.success is True
        assert result.content["response"] == "OpenAI response"
        assert result.content["api"] == "openai"

    @pytest.mark.asyncio
    async def test_live_call_tracks_cost(self, online_apex: Apex):
        """Live API call should accumulate cost."""
        online_apex._anthropic_key = "sk-test"
        with patch.object(online_apex, "_call_claude", return_value=("Response", 1000, 1000, "claude-sonnet-4-20250514")):
            await online_apex.execute("apex_query", {"task": "Cost test"})
        assert online_apex._total_cost > 0

    @pytest.mark.asyncio
    async def test_api_error_returns_failure(self, online_apex: Apex):
        """API errors should propagate as failed ToolResult with source=failed."""
        online_apex._anthropic_key = "sk-test"
        with patch.object(online_apex, "_call_claude", side_effect=RuntimeError("API down")):
            result = await online_apex.execute("apex_query", {"task": "Will fail"})
        assert result.success is False
        assert "API down" in result.error
        assert "NOT validated" in result.error
        assert result.content["source"] == "failed"


# --- Teaching tests ---

class TestApexTeach:
    @pytest.mark.asyncio
    async def test_teach_request(self, online_apex: Apex):
        result = await online_apex.execute("apex_teach", {
            "task": "Parse JSON",
            "failed_approaches": ["regex", "split"],
            "successful_answer": "Use json.loads()",
        })
        assert result.success is True
        assert result.content["failed_approaches_count"] == 2

    @pytest.mark.asyncio
    async def test_teach_empty_task_fails(self, online_apex: Apex):
        result = await online_apex.execute("apex_teach", {"task": ""})
        assert result.success is False


# --- Cost tracking ---

class TestCostTracking:
    @pytest.mark.asyncio
    async def test_cost_accumulation(self, online_apex: Apex):
        await online_apex.execute("apex_log", {
            "entry": {"cost": 0.05, "api": "claude"},
        })
        await online_apex.execute("apex_log", {
            "entry": {"cost": 0.03, "api": "openai"},
        })
        assert online_apex._total_cost == pytest.approx(0.08)

    @pytest.mark.asyncio
    async def test_cost_report(self, online_apex: Apex):
        await online_apex.execute("apex_log", {
            "entry": {"cost": 0.10, "api": "claude"},
        })
        result = await online_apex.execute("apex_cost_report", {})
        assert result.success is True
        assert result.content["total_cost"] == pytest.approx(0.10)
        assert result.content["total_calls"] == 1

    @pytest.mark.asyncio
    async def test_log_empty_entry_fails(self, online_apex: Apex):
        result = await online_apex.execute("apex_log", {"entry": {}})
        assert result.success is False


# --- Persistence ---

class TestApexPersistence:
    @pytest.mark.asyncio
    async def test_log_persists(self, tmp_path: Path):
        config = {"log_file": str(tmp_path / "apex_log.json")}

        a1 = Apex(config)
        with patch("dotenv.load_dotenv"):
            await a1.initialize()
        await a1.execute("apex_log", {"entry": {"cost": 0.05, "api": "claude"}})
        await a1.shutdown()

        a2 = Apex(config)
        with patch("dotenv.load_dotenv"):
            await a2.initialize()
        assert a2._total_cost == pytest.approx(0.05)
        await a2.shutdown()


# --- Unknown tool ---

class TestConfabulationPrevention:
    """Tests ensuring Apex NEVER generates fake responses."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_failure(self, dry_run_apex: Apex):
        """When dry_run=True, execute returns success=False with 'dry-run' in message."""
        with patch("dotenv.load_dotenv"):
            await dry_run_apex.initialize()
        dry_run_apex._anthropic_key = "sk-test"
        result = await dry_run_apex.execute("apex_query", {"task": "Test query"})
        assert result.success is False
        assert "dry-run" in result.error.lower()
        assert result.content["source"] == "dry_run"

    @pytest.mark.asyncio
    async def test_failed_api_returns_failure(self, online_apex: Apex):
        """Mock a failed API call, verify success=False and clear error message."""
        online_apex._anthropic_key = "sk-test"
        with patch.object(online_apex, "_call_claude", side_effect=ConnectionError("Connection refused")):
            result = await online_apex.execute("apex_query", {"task": "Test query"})
        assert result.success is False
        assert "Connection refused" in result.error
        assert "NOT validated by a frontier model" in result.error
        assert result.content["source"] == "failed"

    @pytest.mark.asyncio
    async def test_success_includes_source(self, online_apex: Apex):
        """Mock a successful API call, verify content includes 'source' field."""
        online_apex._anthropic_key = "sk-test"
        with patch.object(online_apex, "_call_claude", return_value=("Response text", 10, 20, "claude-sonnet-4-20250514")):
            result = await online_apex.execute("apex_query", {"task": "Test query"})
        assert result.success is True
        assert result.content["source"] == "claude_api"

        # Now test OpenAI source
        online_apex._anthropic_key = None
        online_apex._openai_key = "sk-oai-test"
        with patch.object(online_apex, "_call_openai", return_value=("Response text", 10, 20, "gpt-4o")):
            result = await online_apex.execute("apex_query", {"task": "Test query", "model_preference": "openai"})
        assert result.success is True
        assert result.content["source"] == "openai_api"

    @pytest.mark.asyncio
    async def test_never_generates_local_response(self, online_apex: Apex):
        """Verify Apex NEVER calls Ollama/local model — it either calls the real API or fails."""
        online_apex._anthropic_key = "sk-test"
        # Patch _call_api to fail
        with patch.object(online_apex, "_call_api", side_effect=RuntimeError("API down")):
            result = await online_apex.execute("apex_query", {"task": "Test query"})
        assert result.success is False
        # Verify no local model was called — check that _call_api was the only dispatch
        # and that success is False (no local fallback generated a fake response)
        assert result.content["source"] == "failed"
        assert "NOT validated" in result.error


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_fails(self, online_apex: Apex):
        result = await online_apex.execute("nonexistent", {})
        assert result.success is False
        assert "Unknown tool" in result.error
