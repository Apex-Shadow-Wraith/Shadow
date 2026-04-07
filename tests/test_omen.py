"""
Tests for Omen — Shadow's Code Brain
=======================================
Covers code execution, linting, testing, git operations,
code review, dependency checks, and teaching mode.
"""

import pytest
import sys
from pathlib import Path
from typing import Any

from modules.base import ModuleStatus, ToolResult
from modules.omen.omen import Omen


@pytest.fixture
def omen(tmp_path: Path) -> Omen:
    config = {"project_root": str(tmp_path), "teaching_mode": False}
    return Omen(config)


@pytest.fixture
async def online_omen(omen: Omen) -> Omen:
    await omen.initialize()
    return omen


# --- Lifecycle ---

class TestOmenLifecycle:
    @pytest.mark.asyncio
    async def test_initialize(self, omen: Omen):
        await omen.initialize()
        assert omen.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown(self, omen: Omen):
        await omen.initialize()
        await omen.shutdown()
        assert omen.status == ModuleStatus.OFFLINE

    def test_get_tools(self, omen: Omen):
        tools = omen.get_tools()
        assert len(tools) == 37
        names = [t["name"] for t in tools]
        assert "code_execute" in names
        assert "code_lint" in names
        assert "git_commit" in names

    def test_git_commit_requires_approval(self, omen: Omen):
        tools = omen.get_tools()
        commit_tool = next(t for t in tools if t["name"] == "git_commit")
        assert commit_tool["permission_level"] == "approval_required"


# --- Code execution ---

class TestCodeExecute:
    @pytest.mark.asyncio
    async def test_simple_print(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {
            "code": "print('hello world')",
        })
        assert r.success is True
        assert "hello world" in r.content["stdout"]

    @pytest.mark.asyncio
    async def test_math_expression(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {
            "code": "print(2 + 2)",
        })
        assert r.success is True
        assert "4" in r.content["stdout"]

    @pytest.mark.asyncio
    async def test_syntax_error(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {
            "code": "def broken(",
        })
        assert r.success is False
        assert r.content["exit_code"] != 0

    @pytest.mark.asyncio
    async def test_timeout(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {
            "code": "import time; time.sleep(10)",
            "timeout": 1,
        })
        assert r.success is False
        assert r.error == "" or r.error is None
        assert r.content.get("timed_out") is True

    @pytest.mark.asyncio
    async def test_empty_code_fails(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {"code": ""})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_max_timeout_capped(self, online_omen: Omen):
        # Requesting 999s should be capped to MAX_TIMEOUT
        r = await online_omen.execute("code_execute", {
            "code": "print('fast')", "timeout": 999,
        })
        assert r.success is True


# --- Code lint ---

class TestCodeLint:
    @pytest.mark.asyncio
    async def test_valid_code(self, online_omen: Omen):
        r = await online_omen.execute("code_lint", {
            "code": "x = 1 + 2\nprint(x)\n",
        })
        assert r.success is True
        assert r.content["syntax_valid"] is True

    @pytest.mark.asyncio
    async def test_invalid_code(self, online_omen: Omen):
        r = await online_omen.execute("code_lint", {
            "code": "def broken(\n",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_lint_file(self, online_omen: Omen, tmp_path: Path):
        test_file = tmp_path / "valid.py"
        test_file.write_text("x = 42\n", encoding="utf-8")
        r = await online_omen.execute("code_lint", {
            "file_path": str(test_file),
        })
        assert r.success is True

    @pytest.mark.asyncio
    async def test_lint_missing_file(self, online_omen: Omen):
        r = await online_omen.execute("code_lint", {
            "file_path": "/nonexistent/file.py",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_lint_no_input_fails(self, online_omen: Omen):
        r = await online_omen.execute("code_lint", {})
        assert r.success is False


# --- Code review ---

class TestCodeReview:
    @pytest.mark.asyncio
    async def test_review_code_string(self, online_omen: Omen):
        code = '''
def hello(name: str) -> str:
    """Say hello."""
    try:
        return f"Hello, {name}"
    except Exception as e:
        raise
'''
        r = await online_omen.execute("code_review", {"code": code})
        assert r.success is True
        assert r.content["has_docstrings"] is True
        assert r.content["has_type_hints"] is True
        assert r.content["has_error_handling"] is True
        assert r.content["function_count"] == 1

    @pytest.mark.asyncio
    async def test_review_no_input_fails(self, online_omen: Omen):
        r = await online_omen.execute("code_review", {})
        assert r.success is False


# --- Git status ---

class TestGitStatus:
    @pytest.mark.asyncio
    async def test_git_status_runs(self, tmp_path: Path):
        """Test git status on actual Shadow repo."""
        omen = Omen({"project_root": "."})
        await omen.initialize()
        r = await omen.execute("git_status", {})
        assert r.success is True
        assert "branch" in r.content
        await omen.shutdown()


# --- Git commit ---

class TestGitCommit:
    @pytest.mark.asyncio
    async def test_commit_no_message_fails(self, online_omen: Omen):
        r = await online_omen.execute("git_commit", {"message": ""})
        assert r.success is False
        assert "message is required" in r.error


# --- Dependency check ---

class TestDependencyCheck:
    @pytest.mark.asyncio
    async def test_dependency_check_runs(self, online_omen: Omen):
        r = await online_omen.execute("dependency_check", {})
        assert r.success is True
        assert "outdated_count" in r.content


# --- Teaching mode ---

class TestTeachingMode:
    @pytest.mark.asyncio
    async def test_teaching_mode_on_error(self, tmp_path: Path):
        omen = Omen({"project_root": str(tmp_path), "teaching_mode": True})
        await omen.initialize()
        r = await omen.execute("code_execute", {"code": "raise ValueError('oops')"})
        assert r.success is False
        assert "teaching_note" in r.content
        await omen.shutdown()

    @pytest.mark.asyncio
    async def test_teaching_mode_off_no_note(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {"code": "raise ValueError('oops')"})
        assert r.success is False
        assert "teaching_note" not in r.content


# --- Unknown tool ---

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_fails(self, online_omen: Omen):
        r = await online_omen.execute("nonexistent", {})
        assert r.success is False
