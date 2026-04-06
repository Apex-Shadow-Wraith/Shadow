"""
Tests for Apex — API Fallback and Active Learning
===================================================
Covers API key loading, cost tracking, call logging, API selection,
teaching cycle, and persistence.
"""

import json
import os
import pytest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.base import ModuleStatus, ToolResult
from modules.apex.apex import Apex


@pytest.fixture
def apex(tmp_path: Path) -> Apex:
    """Create an Apex instance with a temp log file."""
    config = {"log_file": str(tmp_path / "apex_log.json")}
    return Apex(config)


@pytest.fixture
async def online_apex(apex: Apex) -> Apex:
    """Create and initialize Apex (no API keys)."""
    await apex.initialize()
    return apex


# --- Lifecycle tests ---

class TestApexLifecycle:
    @pytest.mark.asyncio
    async def test_initialize_sets_online(self, apex: Apex):
        await apex.initialize()
        assert apex.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown_sets_offline(self, apex: Apex):
        await apex.initialize()
        await apex.shutdown()
        assert apex.status == ModuleStatus.OFFLINE

    def test_get_tools_returns_all(self, apex: Apex):
        tools = apex.get_tools()
        assert len(tools) == 7
        names = [t["name"] for t in tools]
        assert "apex_query" in names
        assert "apex_teach" in names
        assert "apex_log" in names
        assert "apex_cost_report" in names
        assert "escalation_stats" in names
        assert "escalation_frequent" in names
        assert "teaching_review" in names

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
        with patch.dict(os.environ, {}, clear=True):
            await apex.initialize()
            assert apex.status == ModuleStatus.ONLINE
            assert apex._anthropic_key is None
            assert apex._openai_key is None

    @pytest.mark.asyncio
    async def test_anthropic_key_loaded(self, apex: Apex):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-123"}):
            await apex.initialize()
            assert apex._anthropic_key == "sk-test-123"

    @pytest.mark.asyncio
    async def test_openai_key_loaded(self, apex: Apex):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}):
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
    async def test_query_dry_run_with_key(self, online_apex: Apex):
        online_apex._anthropic_key = "sk-test"
        result = await online_apex.execute("apex_query", {"task": "What is Python?"})
        assert result.success is True
        assert result.content["status"] == "logged"

    @pytest.mark.asyncio
    async def test_query_empty_task_fails(self, online_apex: Apex):
        result = await online_apex.execute("apex_query", {"task": ""})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_query_logged(self, online_apex: Apex):
        online_apex._anthropic_key = "sk-test"
        await online_apex.execute("apex_query", {"task": "Test"})
        assert len(online_apex._call_log) == 1


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
        await a1.initialize()
        await a1.execute("apex_log", {"entry": {"cost": 0.05, "api": "claude"}})
        await a1.shutdown()

        a2 = Apex(config)
        await a2.initialize()
        assert a2._total_cost == pytest.approx(0.05)
        await a2.shutdown()


# --- Unknown tool ---

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_fails(self, online_apex: Apex):
        result = await online_apex.execute("nonexistent", {})
        assert result.success is False
        assert "Unknown tool" in result.error
