"""
Tests for Apex Context Assembly
================================
Verifies that the orchestrator enriches Apex prompts with prior tool
results so that Apex receives actual data (e.g. code_analyze_self output)
instead of just the bare user text.
"""

import json
import pytest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from modules.base import ModuleStatus, ToolResult
from modules.shadow.orchestrator import (
    Orchestrator,
    TaskClassification,
    TaskType,
    BrainType,
)


TEST_CONFIG = {
    "system": {"state_file": ""},
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


@pytest.fixture
def orch(config: dict) -> Orchestrator:
    return Orchestrator(config)


class TestBuildApexContext:
    """Tests for Orchestrator._build_apex_context()."""

    def test_no_prior_results_returns_user_input(self, orch: Orchestrator):
        """When no prior tool results exist, return user input unchanged."""
        result = orch._build_apex_context("analyze the codebase")
        assert result == "analyze the codebase"

    def test_prior_results_included_in_prompt(self, orch: Orchestrator):
        """Prior tool results are appended to the user input."""
        orch._last_tool_results = [
            {
                "tool_name": "code_analyze_self",
                "content": "Found 13 modules, 121 tools, 947 tests.",
                "success": True,
                "error": None,
            }
        ]
        result = orch._build_apex_context("escalate to apex and analyze")
        assert "escalate to apex and analyze" in result
        assert "code_analyze_self" in result
        assert "Found 13 modules, 121 tools, 947 tests." in result
        assert "Prior tool results" in result

    def test_dict_content_serialized_to_json(self, orch: Orchestrator):
        """Dict content from tool results is JSON-serialised."""
        orch._last_tool_results = [
            {
                "tool_name": "code_analyze_self",
                "content": {"modules": 13, "tools": 121, "tests": 947},
                "success": True,
                "error": None,
            }
        ]
        result = orch._build_apex_context("analyze this")
        assert '"modules": 13' in result
        assert '"tools": 121' in result

    def test_multiple_tool_results_all_included(self, orch: Orchestrator):
        """All prior tool results are included."""
        orch._last_tool_results = [
            {
                "tool_name": "code_analyze_self",
                "content": "Module analysis data",
                "success": True,
                "error": None,
            },
            {
                "tool_name": "code_lint",
                "content": "Lint results: 0 errors",
                "success": True,
                "error": None,
            },
        ]
        result = orch._build_apex_context("review the results")
        assert "code_analyze_self" in result
        assert "code_lint" in result
        assert "Module analysis data" in result
        assert "Lint results: 0 errors" in result

    def test_large_results_truncated(self, orch: Orchestrator):
        """Results exceeding 50K tokens (~200K chars) are truncated."""
        large_content = "x" * 250_000  # well over 50K tokens
        orch._last_tool_results = [
            {
                "tool_name": "code_analyze_self",
                "content": large_content,
                "success": True,
                "error": None,
            }
        ]
        result = orch._build_apex_context("analyze this")
        assert "truncated" in result
        assert "50000 token limit" in result
        # Should be under the limit + some overhead for the truncation message
        assert len(result) < 250_000

    def test_empty_last_results_returns_input(self, orch: Orchestrator):
        """Empty list of last results returns user input unchanged."""
        orch._last_tool_results = []
        result = orch._build_apex_context("test input")
        assert result == "test input"


class TestApexPlanWithContext:
    """Tests that Apex plan steps include enriched context."""

    @pytest.mark.asyncio
    async def test_apex_plan_includes_prior_results(self, orch: Orchestrator):
        """When prior tool results exist, apex_query params include them."""
        orch._last_tool_results = [
            {
                "tool_name": "code_analyze_self",
                "content": "Analysis: 13 modules found",
                "success": True,
                "error": None,
            }
        ]
        classification = TaskClassification(
            task_type=TaskType.QUESTION,
            complexity="moderate",
            target_module="apex",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
        )
        plan = await orch._step4_plan(
            "escalate to apex and analyze the codebase",
            classification,
            [],
        )
        tool_steps = [s for s in plan.steps if s.get("tool") == "apex_query"]
        assert len(tool_steps) == 1
        task_param = tool_steps[0]["params"]["task"]
        assert "code_analyze_self" in task_param
        assert "Analysis: 13 modules found" in task_param

    @pytest.mark.asyncio
    async def test_apex_plan_without_prior_results(self, orch: Orchestrator):
        """Without prior results, apex_query params contain just user input."""
        orch._last_tool_results = []
        classification = TaskClassification(
            task_type=TaskType.QUESTION,
            complexity="moderate",
            target_module="apex",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
        )
        plan = await orch._step4_plan(
            "ask apex about Python",
            classification,
            [],
        )
        tool_steps = [s for s in plan.steps if s.get("tool") == "apex_query"]
        assert len(tool_steps) == 1
        task_param = tool_steps[0]["params"]["task"]
        assert task_param == "ask apex about Python"


class TestApexQueryWrapperEnrichment:
    """Tests that the Apex query wrapper enriches tasks with prior context."""

    @pytest.mark.asyncio
    async def test_wrapper_enriches_with_prior_results(self, orch: Orchestrator):
        """The apex_query wrapper passes enriched task to Apex.execute()."""
        orch._last_tool_results = [
            {
                "tool_name": "code_analyze_self",
                "content": "Shadow has 13 modules",
                "success": True,
                "error": None,
            }
        ]

        mock_apex = AsyncMock()
        mock_apex.name = "apex"
        mock_apex.status = ModuleStatus.ONLINE
        mock_apex.execute = AsyncMock(return_value=ToolResult(
            success=True,
            content={"message": "Analysis complete", "model": "test"},
            tool_name="apex_query",
            module="apex",
        ))
        orch.registry._modules["apex"] = mock_apex
        orch.registry._tool_index["apex_query"] = "apex"

        wrapper = orch._apex_query_wrapper()
        await wrapper("analyze the codebase")

        # Verify Apex received enriched task
        mock_apex.execute.assert_called_once()
        call_args = mock_apex.execute.call_args
        enriched_task = call_args[0][1]["task"]
        assert "code_analyze_self" in enriched_task
        assert "Shadow has 13 modules" in enriched_task

    @pytest.mark.asyncio
    async def test_wrapper_without_prior_results(self, orch: Orchestrator):
        """Without prior results, wrapper passes task unchanged."""
        orch._last_tool_results = []

        mock_apex = AsyncMock()
        mock_apex.name = "apex"
        mock_apex.status = ModuleStatus.ONLINE
        mock_apex.execute = AsyncMock(return_value=ToolResult(
            success=True,
            content={"message": "Response", "model": "test"},
            tool_name="apex_query",
            module="apex",
        ))
        orch.registry._modules["apex"] = mock_apex
        orch.registry._tool_index["apex_query"] = "apex"

        wrapper = orch._apex_query_wrapper()
        await wrapper("simple question")

        call_args = mock_apex.execute.call_args
        task_sent = call_args[0][1]["task"]
        assert task_sent == "simple question"


class TestToolResultPersistence:
    """Tests that tool results are stored for cross-interaction access."""

    def test_last_tool_results_initialized_empty(self, orch: Orchestrator):
        """_last_tool_results starts as an empty list."""
        assert orch._last_tool_results == []

    @pytest.mark.asyncio
    async def test_results_stored_after_execution(self, orch: Orchestrator):
        """After step5 execution, successful results are persisted."""
        mock_omen = AsyncMock()
        mock_omen.name = "omen"
        mock_omen.status = ModuleStatus.ONLINE
        mock_omen.execute = AsyncMock(return_value=ToolResult(
            success=True,
            content={"analysis": "13 modules, 121 tools"},
            tool_name="code_analyze_self",
            module="omen",
        ))
        orch.registry._modules["omen"] = mock_omen
        orch.registry._tool_index["code_analyze_self"] = "omen"

        from modules.shadow.orchestrator import ExecutionPlan
        plan = ExecutionPlan(
            steps=[{
                "step": 1,
                "description": "Analyze codebase",
                "tool": "code_analyze_self",
                "params": {},
            }],
            cerberus_approved=True,
            raw_plan="test plan",
        )
        classification = TaskClassification(
            task_type=TaskType.ANALYSIS,
            complexity="moderate",
            target_module="omen",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
        )
        results = await orch._step5_execute(plan, classification)

        # Simulate the persistence that happens in the decision loop
        if results:
            orch._last_tool_results = [
                {
                    "tool_name": r.tool_name,
                    "content": r.content,
                    "success": r.success,
                    "error": r.error,
                }
                for r in results
                if r.success and r.content
            ]

        assert len(orch._last_tool_results) == 1
        assert orch._last_tool_results[0]["tool_name"] == "code_analyze_self"
        assert orch._last_tool_results[0]["content"] == {"analysis": "13 modules, 121 tools"}

    def test_failed_results_not_persisted(self, orch: Orchestrator):
        """Only successful results with content are persisted."""
        results = [
            ToolResult(
                success=False,
                content=None,
                tool_name="code_analyze_self",
                module="omen",
                error="Something broke",
            ),
            ToolResult(
                success=True,
                content="good result",
                tool_name="code_lint",
                module="omen",
            ),
        ]
        orch._last_tool_results = [
            {
                "tool_name": r.tool_name,
                "content": r.content,
                "success": r.success,
                "error": r.error,
            }
            for r in results
            if r.success and r.content
        ]
        assert len(orch._last_tool_results) == 1
        assert orch._last_tool_results[0]["tool_name"] == "code_lint"
