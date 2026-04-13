"""
Tests for code_analyze tool and routing.
==========================================
Verifies:
- "analyze this code" routes to code_analyze, not code_generate.
- "write a function" routes to code_generate.
- code_analyze returns analysis without generating new code.
- code_analyze handles edge cases (empty input, non-Python).
"""

import pytest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.omen.omen import Omen
from modules.shadow.orchestrator import (
    BrainType,
    Orchestrator,
    TaskClassification,
    TaskType,
)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def omen(tmp_path: Path) -> Omen:
    config = {"project_root": str(tmp_path), "teaching_mode": False}
    return Omen(config)


@pytest.fixture
async def online_omen(omen: Omen) -> Omen:
    await omen.initialize()
    return omen


# ===================================================================
# code_analyze tool tests
# ===================================================================

class TestCodeAnalyzeTool:
    """Verify code_analyze returns analysis without generating code."""

    @pytest.mark.asyncio
    async def test_analyze_returns_structure(self, online_omen: Omen):
        code = '''
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}"

class Greeter:
    def greet(self):
        pass
'''
        r = await online_omen.execute("code_analyze", {"code": code})
        assert r.success is True
        assert r.tool_name == "code_analyze"
        # Must return analysis structure, not generated code
        assert "structure" in r.content
        assert "patterns" in r.content
        assert "complexity" in r.content
        assert "quality_signals" in r.content
        assert "dependencies" in r.content
        # Must NOT contain generated code output
        assert "generated_code" not in r.content

    @pytest.mark.asyncio
    async def test_analyze_detects_functions_and_classes(self, online_omen: Omen):
        code = '''
def foo():
    pass

def bar():
    pass

class Baz:
    def method(self):
        pass
'''
        r = await online_omen.execute("code_analyze", {"code": code})
        assert r.success is True
        structure = r.content["structure"]
        assert len(structure["functions"]) >= 2
        assert len(structure["classes"]) >= 1

    @pytest.mark.asyncio
    async def test_analyze_empty_code_fails(self, online_omen: Omen):
        r = await online_omen.execute("code_analyze", {"code": ""})
        assert r.success is False
        assert "no code" in r.error.lower()

    @pytest.mark.asyncio
    async def test_analyze_no_code_param_fails(self, online_omen: Omen):
        r = await online_omen.execute("code_analyze", {})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_analyze_natural_language_no_code(self, online_omen: Omen):
        """Natural language prompt with no actual code returns helpful error."""
        r = await online_omen.execute("code_analyze", {"code": "analyze this code"})
        assert r.success is False
        assert "no python code" in r.error.lower() or "no code" in r.error.lower()

    @pytest.mark.asyncio
    async def test_analyze_natural_language_variants(self, online_omen: Omen):
        """Various natural-language prompts all return helpful 'no code' errors."""
        prompts = [
            "what does this do",
            "explain the function",
            "review my code please",
            "can you check this",
        ]
        for prompt in prompts:
            r = await online_omen.execute("code_analyze", {"code": prompt})
            assert r.success is False, f"Should fail for: {prompt!r}"
            assert "no python code" in r.error.lower() or "no code" in r.error.lower(), (
                f"Expected helpful error for: {prompt!r}, got: {r.error}"
            )

    @pytest.mark.asyncio
    async def test_analyze_syntax_error(self, online_omen: Omen):
        """Actual code with syntax errors still returns syntax error."""
        r = await online_omen.execute("code_analyze", {"code": "def broken(:"})
        assert r.success is False
        assert "syntax" in r.error.lower()

    @pytest.mark.asyncio
    async def test_analyze_whitespace_only(self, online_omen: Omen):
        """Whitespace-only input treated as no code."""
        r = await online_omen.execute("code_analyze", {"code": "   \n\t  "})
        assert r.success is False
        assert "no code" in r.error.lower()

    @pytest.mark.asyncio
    async def test_analyze_non_python(self, online_omen: Omen):
        code = "function hello() { return 'hi'; }"
        r = await online_omen.execute("code_analyze", {
            "code": code, "language": "javascript",
        })
        assert r.success is True
        assert r.content["language"] == "javascript"
        assert "line_count" in r.content

    @pytest.mark.asyncio
    async def test_analyze_in_tools_list(self, omen: Omen):
        names = [t["name"] for t in omen.get_tools()]
        assert "code_analyze" in names

    @pytest.mark.asyncio
    async def test_analyze_is_autonomous(self, omen: Omen):
        tools = {t["name"]: t for t in omen.get_tools()}
        assert tools["code_analyze"]["permission_level"] == "autonomous"


# ===================================================================
# Routing tests — classifier + _step4_plan
# ===================================================================

class TestCodeAnalyzeRouting:
    """Verify the classifier and planner route correctly."""

    def _make_orchestrator(self):
        """Create a minimal orchestrator for classification testing."""
        orch = Orchestrator.__new__(Orchestrator)
        orch._smart_brain = "phi4-mini"
        orch._modules = {}
        # Registry that reports cerberus as absent
        registry = MagicMock()
        registry.__contains__ = lambda self, key: False
        orch.registry = registry
        orch._config = {}
        orch._langfuse_enabled = False
        orch._last_route = None
        return orch

    def test_analyze_this_code_routes_to_analysis(self):
        """'analyze this code' must classify as ANALYSIS for omen."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("analyze this code")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_review_this_code_routes_to_analysis(self):
        """'review this code' must classify as ANALYSIS for omen."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("review this code")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_explain_this_function_routes_to_analysis(self):
        """'explain this function' must classify as ANALYSIS for omen."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("explain this function")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_inspect_this_code_routes_to_analysis(self):
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("inspect this code")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_whats_wrong_with_routes_to_analysis(self):
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("what's wrong with this code")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_write_function_routes_to_creation(self):
        """'write a function' must classify as CREATION for omen."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("write a python function to sort a list")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.CREATION

    def test_generate_code_routes_to_creation(self):
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("generate code for a web scraper")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.CREATION

    def test_debug_routes_to_omen(self):
        """'debug' is an omen keyword — should route to omen."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("debug this script")
        assert result is not None
        assert result.target_module == "omen"

    @pytest.mark.asyncio
    async def test_step4_analysis_plans_code_analyze(self):
        """ANALYSIS task type for omen must plan code_analyze, not code_generate."""
        orch = self._make_orchestrator()
        classification = TaskClassification(
            task_type=TaskType.ANALYSIS,
            complexity="moderate",
            target_module="omen",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
            confidence=0.85,
        )
        plan = await orch._step4_plan("analyze this code", classification, {})
        tool_names = [s["tool"] for s in plan.steps if s.get("tool")]
        assert "code_analyze" in tool_names
        assert "code_generate" not in tool_names

    @pytest.mark.asyncio
    async def test_step4_creation_plans_code_generate(self):
        """CREATION task type for omen must plan code_generate."""
        orch = self._make_orchestrator()
        classification = TaskClassification(
            task_type=TaskType.CREATION,
            complexity="moderate",
            target_module="omen",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
            confidence=0.85,
        )
        plan = await orch._step4_plan("write a function", classification, {})
        tool_names = [s["tool"] for s in plan.steps if s.get("tool")]
        assert "code_generate" in tool_names
        assert "code_analyze" not in tool_names
