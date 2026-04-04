"""
Tests for Shadow Orchestrator (Decision Loop)
================================================
Tests the 7-step decision loop with mocked LLM and modules.
We can't call Ollama in CI, so we mock the OpenAI client.
"""

import json
import pytest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.shadow.orchestrator import (
    Orchestrator,
    TaskClassification,
    TaskType,
    BrainType,
)


# --- Mock Module ---

class MockSearchModule(BaseModule):
    """Mock module that simulates Reaper's web_search."""

    def __init__(self):
        super().__init__(name="reaper", description="Mock Reaper")

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        if tool_name == "web_search":
            return ToolResult(
                success=True,
                content=[
                    {"title": "Test Result", "body": "This is a test search result."}
                ],
                tool_name=tool_name,
                module=self.name,
            )
        return ToolResult(
            success=False, content=None, tool_name=tool_name,
            module=self.name, error=f"Unknown tool: {tool_name}",
        )

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "web_search",
                "description": "Mock web search",
                "parameters": {},
                "permission_level": "autonomous",
            }
        ]


class MockMemoryModule(BaseModule):
    """Mock module that simulates Grimoire."""

    def __init__(self):
        super().__init__(name="grimoire", description="Mock Grimoire")
        self._memories: list[str] = []

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        if tool_name == "memory_search":
            return ToolResult(
                success=True,
                content={"documents": self._memories[-5:]},
                tool_name=tool_name,
                module=self.name,
            )
        elif tool_name == "memory_store":
            self._memories.append(params.get("content", ""))
            return ToolResult(
                success=True,
                content="Stored",
                tool_name=tool_name,
                module=self.name,
            )
        return ToolResult(
            success=False, content=None, tool_name=tool_name,
            module=self.name, error=f"Unknown tool: {tool_name}",
        )

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "memory_search", "description": "Search memories",
             "parameters": {}, "permission_level": "autonomous"},
            {"name": "memory_store", "description": "Store memory",
             "parameters": {}, "permission_level": "autonomous"},
        ]


# --- Test Config ---

TEST_CONFIG = {
    "system": {"state_file": ""},  # Will be set per test
    "models": {
        "ollama_base_url": "http://localhost:11434",
        "router": {"name": "phi4-mini"},
        "fast_brain": {"name": "phi4-mini"},
        "smart_brain": {"name": "phi4-mini"},
    },
    "decision_loop": {
        "context_memories": 3,
    },
}


@pytest.fixture
def config(tmp_path: Path) -> dict:
    cfg = dict(TEST_CONFIG)
    cfg["system"] = {"state_file": str(tmp_path / "state.json")}
    return cfg


# --- Fallback Classification Tests ---

class TestFallbackClassifier:
    """Test keyword-based fallback classifier (no LLM needed)."""

    def test_memory_query(self, config: dict):
        orch = Orchestrator(config)
        result = orch._fallback_classify("remember that I like coffee")
        assert result.task_type == TaskType.MEMORY
        assert result.target_module == "grimoire"

    def test_research_query(self, config: dict):
        orch = Orchestrator(config)
        result = orch._fallback_classify("search for python tutorials")
        assert result.task_type == TaskType.RESEARCH
        assert result.target_module == "reaper"

    def test_conversation_default(self, config: dict):
        orch = Orchestrator(config)
        result = orch._fallback_classify("hello, how are you?")
        assert result.task_type == TaskType.CONVERSATION
        assert result.target_module == "direct"

    def test_what_is_routes_to_research(self, config: dict):
        orch = Orchestrator(config)
        result = orch._fallback_classify("what is photosynthesis")
        assert result.task_type == TaskType.RESEARCH


class TestFastPathClassifier:
    """Test fast-path classification that skips the LLM."""

    def test_greeting_fast_path(self, config: dict):
        orch = Orchestrator(config)
        result = orch._fast_path_classify("hello")
        assert result is not None
        assert result.task_type == TaskType.CONVERSATION
        assert result.target_module == "direct"

    def test_slash_command_fast_path(self, config: dict):
        orch = Orchestrator(config)
        result = orch._fast_path_classify("/status")
        assert result is not None
        assert result.task_type == TaskType.SYSTEM

    def test_search_command_fast_path(self, config: dict):
        orch = Orchestrator(config)
        result = orch._fast_path_classify("search for RTX 5090")
        assert result is not None
        assert result.task_type == TaskType.RESEARCH
        assert result.target_module == "reaper"

    def test_memory_command_fast_path(self, config: dict):
        orch = Orchestrator(config)
        result = orch._fast_path_classify("remember that I like coffee")
        assert result is not None
        assert result.task_type == TaskType.MEMORY
        assert result.target_module == "grimoire"

    def test_ambiguous_input_returns_none(self, config: dict):
        orch = Orchestrator(config)
        result = orch._fast_path_classify("explain quantum computing")
        assert result is None

    def test_case_insensitive(self, config: dict):
        orch = Orchestrator(config)
        result = orch._fast_path_classify("HELLO")
        assert result is not None
        assert result.task_type == TaskType.CONVERSATION


class TestQueryExtraction:
    """Test search query extraction from user input."""

    def test_strips_search_for(self):
        assert Orchestrator._extract_search_query("search for RTX 5090") == "RTX 5090"

    def test_strips_look_up(self):
        assert Orchestrator._extract_search_query("look up Python tutorials") == "Python tutorials"

    def test_strips_what_is(self):
        assert Orchestrator._extract_search_query("what is the price of DDR5") == "price of DDR5"

    def test_preserves_case(self):
        assert Orchestrator._extract_search_query("search for NVIDIA RTX") == "NVIDIA RTX"

    def test_no_prefix_passthrough(self):
        assert Orchestrator._extract_search_query("quantum computing") == "quantum computing"

    def test_empty_after_prefix_returns_original(self):
        assert Orchestrator._extract_search_query("search for ") == "search for"

    def test_strips_please_prefix(self):
        assert Orchestrator._extract_search_query("please search for AI news") == "AI news"


# --- State Persistence Tests ---

class TestStatePersistence:
    def test_save_and_load_state(self, config: dict, tmp_path: Path):
        orch = Orchestrator(config)
        orch._state.interaction_count = 42
        orch._state.last_interaction = "2026-04-03T12:00:00"
        orch._save_state()

        # Create new orchestrator, load state
        orch2 = Orchestrator(config)
        orch2._load_state()
        assert orch2._state.interaction_count == 42
        assert orch2._state.last_interaction == "2026-04-03T12:00:00"

    def test_load_missing_state_starts_fresh(self, config: dict):
        orch = Orchestrator(config)
        orch._load_state()  # No state file exists
        assert orch._state.interaction_count == 0


# --- Context Loading Tests ---

class TestContextLoading:
    @pytest.mark.asyncio
    async def test_loads_memories(self, config: dict):
        orch = Orchestrator(config)
        grimoire = MockMemoryModule()
        grimoire._memories = ["Patrick runs a landscaping business"]
        await grimoire.initialize()
        orch.registry.register(grimoire)

        classification = TaskClassification(
            task_type=TaskType.QUESTION,
            complexity="simple",
            target_module="direct",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
        )

        context = await orch._step3_load_context("tell me about my business", classification)
        # Should have memories + history + tools
        types = [c["type"] for c in context]
        assert "memories" in types
        assert "available_tools" in types


# --- Planning Tests ---

class TestPlanning:
    @pytest.mark.asyncio
    async def test_direct_conversation_plan(self, config: dict):
        orch = Orchestrator(config)

        classification = TaskClassification(
            task_type=TaskType.CONVERSATION,
            complexity="simple",
            target_module="direct",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
        )

        plan = await orch._step4_plan("hello", classification, [])
        assert plan.cerberus_approved is True
        assert plan.steps[0]["tool"] is None

    @pytest.mark.asyncio
    async def test_research_plan_has_search_step(self, config: dict):
        orch = Orchestrator(config)

        classification = TaskClassification(
            task_type=TaskType.RESEARCH,
            complexity="moderate",
            target_module="reaper",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
        )

        plan = await orch._step4_plan("search for AI news", classification, [])
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "web_search" in tool_names


# --- Execution Tests ---

class TestExecution:
    @pytest.mark.asyncio
    async def test_executes_search_tool(self, config: dict):
        orch = Orchestrator(config)
        reaper = MockSearchModule()
        await reaper.initialize()
        orch.registry.register(reaper)

        from modules.shadow.orchestrator import ExecutionPlan
        plan = ExecutionPlan(
            steps=[{
                "step": 1,
                "description": "Search",
                "tool": "web_search",
                "params": {"query": "test"},
            }],
            cerberus_approved=True,
        )

        classification = TaskClassification(
            task_type=TaskType.RESEARCH,
            complexity="simple",
            target_module="reaper",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
        )

        results = await orch._step5_execute(plan, classification)
        assert len(results) == 1
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_denied_plan_returns_error(self, config: dict):
        orch = Orchestrator(config)

        from modules.shadow.orchestrator import ExecutionPlan
        plan = ExecutionPlan(
            steps=[{"step": 1, "tool": "email_send", "params": {}}],
            cerberus_approved=False,
        )

        classification = TaskClassification(
            task_type=TaskType.ACTION,
            complexity="simple",
            target_module="harbinger",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
        )

        results = await orch._step5_execute(plan, classification)
        assert len(results) == 1
        assert results[0].success is False
        assert "denied by Cerberus" in results[0].error


# --- System Prompt Tests ---

class TestSystemPrompt:
    def test_includes_shadow_identity(self, config: dict):
        orch = Orchestrator(config)
        prompt = orch._build_system_prompt([])
        assert "Shadow" in prompt
        assert "Patrick" in prompt
        assert "anti-sycophantic" in prompt

    def test_includes_memories_when_available(self, config: dict):
        orch = Orchestrator(config)
        context = [{
            "type": "memories",
            "content": {"documents": ["Patrick has a landscaping business"]},
        }]
        prompt = orch._build_system_prompt(context)
        assert "landscaping" in prompt
