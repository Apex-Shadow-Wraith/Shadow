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
        """Natural language prompt with no actual code returns success with helpful message."""
        r = await online_omen.execute("code_analyze", {"code": "analyze this code"})
        assert r.success is True
        assert "no code detected" in r.content["message"].lower()

    @pytest.mark.asyncio
    async def test_analyze_natural_language_variants(self, online_omen: Omen):
        """Various natural-language prompts all return success with helpful 'no code' message."""
        prompts = [
            "what does this do",
            "explain the function",
            "review my code please",
            "can you check this",
        ]
        for prompt in prompts:
            r = await online_omen.execute("code_analyze", {"code": prompt})
            assert r.success is True, f"Should succeed for: {prompt!r}"
            assert "no code detected" in r.content["message"].lower(), (
                f"Expected helpful message for: {prompt!r}, got: {r.content}"
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

    # ── Inflection / stem-matching tests ──

    def test_analyzed_past_tense_routes_to_analysis(self):
        """'Analyzed this code' — past tense must still match analysis."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("Analyzed this code")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_analyzing_gerund_routes_to_analysis(self):
        """'analyzing my function' — gerund must still match analysis."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("analyzing my function")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_reviewing_routes_to_analysis(self):
        """'reviewing my function' — gerund must match analysis."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("reviewing my function")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_reviewed_routes_to_analysis(self):
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("reviewed this code base")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_debugging_routes_to_analysis(self):
        """'I was debugging earlier' — must route to omen analysis."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("I was debugging this script earlier")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_explained_routes_to_analysis(self):
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("explained this function to me")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_inspecting_routes_to_analysis(self):
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("inspecting the class hierarchy")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_audited_routes_to_analysis(self):
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("audited the code for security issues")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

    def test_analyzed_your_code_base_routes_to_analysis(self):
        """The original bug report: 'Analyzed your code base' was misclassified."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify("Analyzed your code base")
        assert result is not None
        assert result.target_module == "omen"
        assert result.task_type == TaskType.ANALYSIS

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


# ===================================================================
# code_analyze_file security + code_analyze_self tests
# ===================================================================

class TestCodeAnalyzeFile:
    """Verify code_analyze_file reads real files with security restrictions."""

    @pytest.mark.asyncio
    async def test_analyze_file_reads_real_file(self, tmp_path: Path):
        """code_analyze_file reads a real .py file and returns analysis."""
        test_file = tmp_path / "sample.py"
        test_file.write_text("def greet(name):\n    return f'Hello, {name}'\n")
        config = {"project_root": str(tmp_path), "teaching_mode": False}
        omen = Omen(config)
        await omen.initialize()
        r = await omen.execute("code_analyze_file", {"file_path": str(test_file)})
        assert r.success is True
        assert r.tool_name == "code_analyze_file"
        assert "structure" in r.content
        assert "complexity" in r.content

    @pytest.mark.asyncio
    async def test_analyze_file_rejects_outside_project(self, tmp_path: Path):
        """code_analyze_file denies access outside the project root."""
        config = {"project_root": str(tmp_path / "project"), "teaching_mode": False}
        (tmp_path / "project").mkdir()
        omen = Omen(config)
        await omen.initialize()
        outside_file = tmp_path / "outside.py"
        outside_file.write_text("x = 1\n")
        r = await omen.execute("code_analyze_file", {"file_path": str(outside_file)})
        assert r.success is False
        assert "access denied" in r.error.lower()

    @pytest.mark.asyncio
    async def test_analyze_dir_rejects_outside_project(self, tmp_path: Path):
        """code_analyze_dir denies access outside the project root."""
        config = {"project_root": str(tmp_path / "project"), "teaching_mode": False}
        (tmp_path / "project").mkdir()
        omen = Omen(config)
        await omen.initialize()
        r = await omen.execute("code_analyze_dir", {"dir_path": str(tmp_path)})
        assert r.success is False
        assert "access denied" in r.error.lower()


class TestCodeAnalyzeSelf:
    """Verify code_analyze_self scans the modules/ directory."""

    @pytest.mark.asyncio
    async def test_analyze_self_scans_modules(self, tmp_path: Path):
        """code_analyze_self walks modules/ and returns per-file metrics."""
        modules = tmp_path / "modules" / "example"
        modules.mkdir(parents=True)
        (modules / "__init__.py").write_text("")
        (modules / "core.py").write_text(
            "def run():\n    return True\n\nclass Engine:\n    pass\n"
        )
        config = {"project_root": str(tmp_path), "teaching_mode": False}
        omen = Omen(config)
        await omen.initialize()
        r = await omen.execute("code_analyze_self", {})
        assert r.success is True
        assert r.tool_name == "code_analyze_self"
        sa = r.content["self_analysis"]
        assert sa["scope"] == "modules/"
        assert sa["files_analyzed"] >= 1
        assert sa["total_functions"] >= 1
        assert sa["total_classes"] >= 1
        assert "per_file_summary" in sa

    @pytest.mark.asyncio
    async def test_analyze_self_missing_modules_dir(self, tmp_path: Path):
        """code_analyze_self fails gracefully if modules/ doesn't exist."""
        config = {"project_root": str(tmp_path), "teaching_mode": False}
        omen = Omen(config)
        await omen.initialize()
        r = await omen.execute("code_analyze_self", {})
        assert r.success is False
        assert "modules/" in r.error

    @pytest.mark.asyncio
    async def test_analyze_self_in_tools_list(self):
        """code_analyze_self appears in Omen's tool list."""
        omen = Omen({"project_root": ".", "teaching_mode": False})
        names = [t["name"] for t in omen.get_tools()]
        assert "code_analyze_self" in names


# ===================================================================
# Self-analysis routing tests
# ===================================================================

class TestSelfAnalysisRouting:
    """Verify 'analyze your codebase' routes to code_analyze_self."""

    def _make_orchestrator(self):
        orch = Orchestrator.__new__(Orchestrator)
        orch._smart_brain = "phi4-mini"
        orch._modules = {}
        registry = MagicMock()
        registry.__contains__ = lambda self, key: False
        orch.registry = registry
        orch._config = {}
        orch._langfuse_enabled = False
        orch._last_route = None
        return orch

    @pytest.mark.parametrize("prompt", [
        "analyze your codebase",
        "analyze your code",
        "review your modules",
        "inspect your source code",
        "audit your own codebase",
        "analyze yourself",
    ])
    def test_self_ref_routes_to_omen_analysis(self, prompt):
        """Self-referential analysis phrases must route to omen ANALYSIS."""
        orch = self._make_orchestrator()
        result = orch._fast_path_classify(prompt)
        assert result is not None, f"No classification for: {prompt!r}"
        assert result.target_module == "omen", f"Wrong module for: {prompt!r}"
        assert result.task_type == TaskType.ANALYSIS, f"Wrong task type for: {prompt!r}"

    @pytest.mark.asyncio
    async def test_step4_self_analysis_plans_code_analyze_self(self):
        """Self-referential ANALYSIS must plan code_analyze_self, not code_analyze."""
        orch = self._make_orchestrator()
        classification = TaskClassification(
            task_type=TaskType.ANALYSIS,
            complexity="moderate",
            target_module="omen",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=1,
            confidence=0.90,
        )
        plan = await orch._step4_plan("analyze your codebase", classification, {})
        tool_names = [s["tool"] for s in plan.steps if s.get("tool")]
        assert "code_analyze_self" in tool_names
        assert "code_analyze" not in tool_names

    @pytest.mark.asyncio
    async def test_step4_regular_analysis_still_uses_code_analyze(self):
        """Regular analysis (no self-ref) must still plan code_analyze."""
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
        assert "code_analyze_self" not in tool_names
