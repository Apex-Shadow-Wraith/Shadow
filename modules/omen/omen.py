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

import fnmatch
import logging
import re
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
    MAX_GLOB_RESULTS = 500
    MAX_FILE_SIZE = 100 * 1024  # 100KB
    ALWAYS_EXCLUDE = {"__pycache__", ".git", "node_modules", "shadow_env", "venv"}
    BINARY_EXTENSIONS = {".bin", ".db", ".sqlite3", ".png", ".jpg", ".whl", ".egg", ".pickle"}
    PROTECTED_PATHS = {"config", ".git", ".env"}

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
                "code_glob": self._code_glob,
                "code_grep": self._code_grep,
                "code_edit": self._code_edit,
                "code_read": self._code_read,
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
            {
                "name": "code_glob",
                "description": "Find files matching a glob pattern",
                "parameters": {"pattern": "str", "root_dir": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_grep",
                "description": "Search for text/regex in code files",
                "parameters": {
                    "pattern": "str",
                    "file_glob": "str",
                    "root_dir": "str",
                    "max_results": "int",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "code_edit",
                "description": "Apply a find-and-replace edit to a file",
                "parameters": {"file_path": "str", "old_text": "str", "new_text": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_read",
                "description": "Read a file with line numbers",
                "parameters": {"file_path": "str", "start_line": "int", "end_line": "int"},
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

    # --- Code-aware tools ---

    def _load_gitignore_patterns(self, root: Path) -> list[str]:
        """Load .gitignore patterns from a directory.

        Args:
            root: Directory containing .gitignore.

        Returns:
            List of gitignore patterns.
        """
        gitignore = root / ".gitignore"
        if not gitignore.exists():
            return []
        try:
            lines = gitignore.read_text(encoding="utf-8").splitlines()
            return [
                line.strip().rstrip("/")
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            ]
        except OSError:
            return []

    def _is_excluded(self, path: Path, root: Path, gitignore_patterns: list[str]) -> bool:
        """Check if a path should be excluded from glob/grep results.

        Args:
            path: Path to check.
            root: Root directory for relative path calculation.
            gitignore_patterns: Patterns from .gitignore.

        Returns:
            True if the path should be excluded.
        """
        # Check always-excluded directories
        for part in path.relative_to(root).parts:
            if part in self.ALWAYS_EXCLUDE:
                return True
        # Check .pyc extension
        if path.suffix == ".pyc":
            return True
        # Check gitignore patterns
        rel = str(path.relative_to(root))
        for pattern in gitignore_patterns:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern):
                return True
            # Handle directory patterns
            for part in path.relative_to(root).parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def _code_glob(self, params: dict[str, Any]) -> ToolResult:
        """Find files matching a glob pattern.

        Args:
            params: 'pattern' (str), optional 'root_dir' (str, default ".").
        """
        pattern = params.get("pattern", "")
        if not pattern:
            return ToolResult(
                success=False, content=None, tool_name="code_glob",
                module=self.name, error="Pattern is required",
            )

        root_dir = params.get("root_dir", ".")
        root = Path(root_dir).resolve()

        if not root.exists() or not root.is_dir():
            return ToolResult(
                success=False, content=None, tool_name="code_glob",
                module=self.name, error=f"Directory not found: {root_dir}",
            )

        gitignore_patterns = self._load_gitignore_patterns(root)

        matches = []
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            if self._is_excluded(path, root, gitignore_patterns):
                continue
            matches.append(str(path.relative_to(root)))
            if len(matches) >= self.MAX_GLOB_RESULTS:
                break

        return ToolResult(
            success=True,
            content={
                "files": sorted(matches),
                "count": len(matches),
                "pattern": pattern,
                "root": str(root),
                "capped": len(matches) >= self.MAX_GLOB_RESULTS,
            },
            tool_name="code_glob",
            module=self.name,
        )

    def _code_grep(self, params: dict[str, Any]) -> ToolResult:
        """Search for text/regex in code files.

        Args:
            params: 'pattern' (str), optional 'file_glob' (str, default "**/*.py"),
                    'root_dir' (str, default "."), 'max_results' (int, default 50).
        """
        pattern = params.get("pattern", "")
        if not pattern:
            return ToolResult(
                success=False, content=None, tool_name="code_grep",
                module=self.name, error="Pattern is required",
            )

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(
                success=False, content=None, tool_name="code_grep",
                module=self.name, error=f"Invalid regex: {e}",
            )

        file_glob = params.get("file_glob", "**/*.py")
        root_dir = params.get("root_dir", ".")
        max_results = params.get("max_results", 50)
        root = Path(root_dir).resolve()

        if not root.exists() or not root.is_dir():
            return ToolResult(
                success=False, content=None, tool_name="code_grep",
                module=self.name, error=f"Directory not found: {root_dir}",
            )

        gitignore_patterns = self._load_gitignore_patterns(root)
        results = []

        for path in root.glob(file_glob):
            if not path.is_file():
                continue
            if self._is_excluded(path, root, gitignore_patterns):
                continue
            if path.suffix in self.BINARY_EXTENSIONS:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    results.append({
                        "file": str(path.relative_to(root)),
                        "line_number": i,
                        "line": line,
                    })
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break

        return ToolResult(
            success=True,
            content={
                "matches": results,
                "count": len(results),
                "pattern": pattern,
                "capped": len(results) >= max_results,
            },
            tool_name="code_grep",
            module=self.name,
        )

    def _code_edit(self, params: dict[str, Any]) -> ToolResult:
        """Apply a find-and-replace edit to a file.

        Args:
            params: 'file_path' (str), 'old_text' (str), 'new_text' (str).
        """
        file_path = params.get("file_path", "")
        old_text = params.get("old_text", "")
        new_text = params.get("new_text", "")

        if not file_path or not old_text:
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name, error="file_path and old_text are required",
            )

        path = Path(file_path)

        # Safety: refuse protected paths
        try:
            rel = path.resolve().relative_to(self._project_root)
        except ValueError:
            rel = path

        for protected in self.PROTECTED_PATHS:
            rel_str = str(rel).replace("\\", "/")
            if rel_str == protected or rel_str.startswith(protected + "/"):
                return ToolResult(
                    success=False, content=None, tool_name="code_edit",
                    module=self.name,
                    error=f"Refused: cannot edit protected path '{protected}'",
                )

        if not path.exists():
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name, error=f"File not found: {file_path}",
            )

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name, error=f"Cannot read file: {e}",
            )

        count = content.count(old_text)
        if count == 0:
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name, error="old_text not found in file",
            )
        if count > 1:
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name,
                error=f"old_text found {count} times — must appear exactly once",
            )

        new_content = content.replace(old_text, new_text, 1)
        try:
            path.write_text(new_content, encoding="utf-8")
        except OSError as e:
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name, error=f"Cannot write file: {e}",
            )

        return ToolResult(
            success=True,
            content={"success": True, "file": str(path), "replacements": 1},
            tool_name="code_edit",
            module=self.name,
        )

    def _code_read(self, params: dict[str, Any]) -> ToolResult:
        """Read a file with line numbers.

        Args:
            params: 'file_path' (str), optional 'start_line' (int), 'end_line' (int).
        """
        file_path = params.get("file_path", "")
        if not file_path:
            return ToolResult(
                success=False, content=None, tool_name="code_read",
                module=self.name, error="file_path is required",
            )

        path = Path(file_path)
        if not path.exists():
            return ToolResult(
                success=False, content=None, tool_name="code_read",
                module=self.name, error=f"File not found: {file_path}",
            )

        # Check file size
        try:
            size = path.stat().st_size
        except OSError as e:
            return ToolResult(
                success=False, content=None, tool_name="code_read",
                module=self.name, error=f"Cannot stat file: {e}",
            )

        if size > self.MAX_FILE_SIZE:
            return ToolResult(
                success=False, content=None, tool_name="code_read",
                module=self.name,
                error=f"File too large: {size} bytes (max {self.MAX_FILE_SIZE})",
            )

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return ToolResult(
                success=False, content=None, tool_name="code_read",
                module=self.name, error=f"Cannot read file: {e}",
            )

        lines = content.splitlines()
        start = params.get("start_line")
        end = params.get("end_line")

        if start is not None or end is not None:
            start_idx = (start - 1) if start and start >= 1 else 0
            end_idx = end if end else len(lines)
            selected = lines[start_idx:end_idx]
            offset = start_idx + 1
        else:
            selected = lines
            offset = 1

        numbered = [f"{i + offset}\t{line}" for i, line in enumerate(selected)]

        return ToolResult(
            success=True,
            content={
                "content": "\n".join(numbered),
                "file": str(path),
                "line_count": len(selected),
                "total_lines": len(lines),
            },
            tool_name="code_read",
            module=self.name,
        )
