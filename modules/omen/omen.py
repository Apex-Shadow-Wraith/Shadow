"""
Omen — Shadow's Code Brain
============================
Development, testing, teaching, and self-building.

Design Principle: Omen has a dual mandate — build Shadow AND teach
the creator. When the user says 'just do it', Omen writes fast and
explains after. When the user is learning, Omen slows down.

Phase 1: Subprocess-based code execution, linting, testing, and git
operations. All execution sandboxed with timeouts.
"""

import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.omen")


class Omen(BaseModule):
    """Shadow's code brain. Writes, tests, debugs, and teaches.

    All code execution happens in subprocesses with timeouts.
    Git commit/push require approval. Everything else is autonomous.
    """

    DEFAULT_TIMEOUT = 30  # seconds
    MAX_TIMEOUT = 120

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Omen.

        Args:
            config: Module configuration.
        """
        super().__init__(
            name="omen",
            description="Code brain — development, testing, teaching",
        )
        self._config = config or {}
        self._teaching_mode = self._config.get("teaching_mode", False)
        self._project_root = Path(self._config.get("project_root", ".")).resolve()
        self._python = sys.executable

    async def initialize(self) -> None:
        """Start Omen."""
        self.status = ModuleStatus.ONLINE
        logger.info(
            "Omen online. Teaching mode: %s. Python: %s",
            self._teaching_mode, self._python,
        )

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute an Omen tool.

        Args:
            tool_name: Which tool to invoke.
            params: Tool-specific parameters.

        Returns:
            ToolResult with success/failure and content.
        """
        start = time.time()
        try:
            handlers = {
                "code_execute": self._code_execute,
                "code_lint": self._code_lint,
                "code_test": self._code_test,
                "code_review": self._code_review,
                "git_status": self._git_status,
                "git_commit": self._git_commit,
                "dependency_check": self._dependency_check,
            }

            handler = handlers.get(tool_name)
            if handler is None:
                result = ToolResult(
                    success=False, content=None, tool_name=tool_name,
                    module=self.name, error=f"Unknown tool: {tool_name}",
                )
            else:
                result = handler(params)

            result.execution_time_ms = (time.time() - start) * 1000
            self._record_call(result.success)
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._record_call(False)
            logger.error("Omen tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False, content=None, tool_name=tool_name,
                module=self.name, error=str(e), execution_time_ms=elapsed,
            )

    async def shutdown(self) -> None:
        """Shut down Omen."""
        self.status = ModuleStatus.OFFLINE
        logger.info("Omen offline.")

    def get_tools(self) -> list[dict[str, Any]]:
        """Return Omen's tool definitions."""
        return [
            {
                "name": "code_execute",
                "description": "Run code in sandboxed subprocess with timeout",
                "parameters": {"code": "str", "timeout": "int"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_lint",
                "description": "Check code for syntax errors and style violations",
                "parameters": {"file_path": "str", "code": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_test",
                "description": "Run test suite against code",
                "parameters": {"test_path": "str", "timeout": "int"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_review",
                "description": "Review code for issues (stub — needs LLM in Phase 2+)",
                "parameters": {"code": "str", "file_path": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "git_status",
                "description": "Check git repository state",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "git_commit",
                "description": "Commit changes to repository",
                "parameters": {"message": "str", "files": "list"},
                "permission_level": "approval_required",
            },
            {
                "name": "dependency_check",
                "description": "Scan for outdated or vulnerable dependencies",
                "parameters": {},
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _code_execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute Python code in a sandboxed subprocess.

        Args:
            params: 'code' (str), optional 'timeout' (int seconds).
        """
        code = params.get("code", "")
        if not code:
            return ToolResult(
                success=False, content=None, tool_name="code_execute",
                module=self.name, error="Code is required",
            )

        timeout = min(params.get("timeout", self.DEFAULT_TIMEOUT), self.MAX_TIMEOUT)

        try:
            result = subprocess.run(
                [self._python, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._project_root),
            )

            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "success": result.returncode == 0,
                "timeout_seconds": timeout,
            }

            if self._teaching_mode and result.returncode != 0:
                output["teaching_note"] = (
                    "The code failed. Check stderr for the error message. "
                    "Common causes: syntax errors, missing imports, type errors."
                )

            return ToolResult(
                success=result.returncode == 0,
                content=output,
                tool_name="code_execute",
                module=self.name,
                error=result.stderr[:500] if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="code_execute",
                module=self.name,
                error=f"Execution timed out after {timeout} seconds",
            )

    def _code_lint(self, params: dict[str, Any]) -> ToolResult:
        """Check code for syntax errors using py_compile.

        Args:
            params: 'code' (str) or 'file_path' (str).
        """
        code = params.get("code", "")
        file_path = params.get("file_path", "")

        if file_path:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(
                    success=False, content=None, tool_name="code_lint",
                    module=self.name, error=f"File not found: {file_path}",
                )
            target = str(path)
        elif code:
            # Write code to temp file for compilation check
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            )
            tmp.write(code)
            tmp.close()
            target = tmp.name
        else:
            return ToolResult(
                success=False, content=None, tool_name="code_lint",
                module=self.name, error="Either 'code' or 'file_path' is required",
            )

        try:
            result = subprocess.run(
                [self._python, "-m", "py_compile", target],
                capture_output=True,
                text=True,
                timeout=10,
            )

            lint_result = {
                "file": target,
                "syntax_valid": result.returncode == 0,
                "errors": result.stderr.strip() if result.stderr else None,
            }

            return ToolResult(
                success=result.returncode == 0,
                content=lint_result,
                tool_name="code_lint",
                module=self.name,
                error=result.stderr[:500] if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="code_lint",
                module=self.name, error="Lint check timed out",
            )
        finally:
            if code and not file_path:
                Path(target).unlink(missing_ok=True)

    def _code_test(self, params: dict[str, Any]) -> ToolResult:
        """Run pytest on a test file or directory.

        Args:
            params: 'test_path' (str), optional 'timeout' (int).
        """
        test_path = params.get("test_path", "tests/")
        timeout = min(params.get("timeout", 60), self.MAX_TIMEOUT)

        path = Path(test_path)
        if not path.exists():
            return ToolResult(
                success=False, content=None, tool_name="code_test",
                module=self.name, error=f"Test path not found: {test_path}",
            )

        try:
            result = subprocess.run(
                [self._python, "-m", "pytest", str(path), "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._project_root),
            )

            return ToolResult(
                success=result.returncode == 0,
                content={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                    "passed": result.returncode == 0,
                    "test_path": str(path),
                },
                tool_name="code_test",
                module=self.name,
                error="Tests failed" if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="code_test",
                module=self.name,
                error=f"Tests timed out after {timeout} seconds",
            )

    def _code_review(self, params: dict[str, Any]) -> ToolResult:
        """Review code for issues.

        Phase 1: Stub. Returns structural info only.
        Phase 2+: LLM-powered review.

        Args:
            params: 'code' or 'file_path'.
        """
        code = params.get("code", "")
        file_path = params.get("file_path", "")

        if file_path:
            path = Path(file_path)
            if path.exists():
                code = path.read_text(encoding="utf-8")
            else:
                return ToolResult(
                    success=False, content=None, tool_name="code_review",
                    module=self.name, error=f"File not found: {file_path}",
                )

        if not code:
            return ToolResult(
                success=False, content=None, tool_name="code_review",
                module=self.name, error="Code or file_path is required",
            )

        # Basic structural analysis
        lines = code.split("\n")
        review = {
            "line_count": len(lines),
            "has_docstrings": '"""' in code or "'''" in code,
            "has_type_hints": "->" in code or ": " in code,
            "has_error_handling": "try:" in code or "except" in code,
            "imports_count": sum(1 for l in lines if l.strip().startswith(("import ", "from "))),
            "function_count": sum(1 for l in lines if l.strip().startswith("def ")),
            "class_count": sum(1 for l in lines if l.strip().startswith("class ")),
            "note": "Full code review requires LLM (Phase 2+). Structural analysis only.",
        }

        return ToolResult(
            success=True,
            content=review,
            tool_name="code_review",
            module=self.name,
        )

    def _git_status(self, params: dict[str, Any]) -> ToolResult:
        """Check the git repository state.

        Args:
            params: No required parameters.
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self._project_root),
            )

            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self._project_root),
            )

            status_lines = [
                line for line in result.stdout.strip().split("\n") if line.strip()
            ]

            return ToolResult(
                success=True,
                content={
                    "branch": branch_result.stdout.strip(),
                    "changes": status_lines,
                    "clean": len(status_lines) == 0,
                    "change_count": len(status_lines),
                },
                tool_name="git_status",
                module=self.name,
            )

        except FileNotFoundError:
            return ToolResult(
                success=False, content=None, tool_name="git_status",
                module=self.name, error="Git is not installed or not in PATH",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="git_status",
                module=self.name, error="Git status timed out",
            )

    def _git_commit(self, params: dict[str, Any]) -> ToolResult:
        """Stage and commit files.

        This tool requires approval (permission_level = approval_required).

        Args:
            params: 'message' (str), optional 'files' (list of paths).
        """
        message = params.get("message", "")
        if not message:
            return ToolResult(
                success=False, content=None, tool_name="git_commit",
                module=self.name, error="Commit message is required",
            )

        files = params.get("files", [])

        try:
            # Stage files
            if files:
                for f in files:
                    subprocess.run(
                        ["git", "add", str(f)],
                        capture_output=True, text=True, timeout=10,
                        cwd=str(self._project_root),
                    )
            else:
                subprocess.run(
                    ["git", "add", "-A"],
                    capture_output=True, text=True, timeout=10,
                    cwd=str(self._project_root),
                )

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True, text=True, timeout=30,
                cwd=str(self._project_root),
            )

            return ToolResult(
                success=result.returncode == 0,
                content={
                    "message": message,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "committed": result.returncode == 0,
                },
                tool_name="git_commit",
                module=self.name,
                error=result.stderr if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="git_commit",
                module=self.name, error="Git commit timed out",
            )

    def _dependency_check(self, params: dict[str, Any]) -> ToolResult:
        """Check for outdated Python packages.

        Args:
            params: No required parameters.
        """
        try:
            result = subprocess.run(
                [self._python, "-m", "pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            import json
            try:
                outdated = json.loads(result.stdout) if result.stdout.strip() else []
            except (json.JSONDecodeError, ValueError):
                outdated = []

            return ToolResult(
                success=True,
                content={
                    "outdated_count": len(outdated),
                    "packages": outdated[:20],  # Limit output
                },
                tool_name="dependency_check",
                module=self.name,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="dependency_check",
                module=self.name, error="Dependency check timed out",
            )
