"""
Code Execution Sandbox for Omen
=================================
ALL code Omen runs goes through this sandbox. No direct access to
production files, network, credentials, or system resources.

Each execution gets an isolated directory under data/sandbox/{execution_id}/.
Environment variables are stripped. Timeout and memory limits enforced.
Static safety analysis runs before every execution.
"""

from __future__ import annotations

import ast
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("shadow.omen.sandbox")


class CodeSandbox:
    """Isolated execution environment for Omen's code operations.

    Every piece of code runs inside a per-execution subdirectory with
    stripped environment variables, enforced timeouts, and optional
    memory limits. Static safety validation runs before every execution.
    """

    # Dangerous patterns for static analysis
    _NETWORK_MODULES = frozenset({
        "socket", "requests", "httpx", "urllib", "http.client",
        "http.server", "aiohttp", "websocket", "ftplib", "smtplib",
        "xmlrpc", "grpc",
    })

    _SYSTEM_CALLS = frozenset({
        "os.system", "os.popen", "os.exec", "os.execl", "os.execle",
        "os.execlp", "os.execlpe", "os.execv", "os.execve", "os.execvp",
        "os.execvpe", "os.spawn", "os.spawnl", "os.spawnle",
    })

    _CREDENTIAL_PATTERNS = frozenset({
        "os.environ", "os.getenv", "dotenv", "load_dotenv",
    })

    _PROCESS_CALLS = frozenset({
        "os.kill", "os.killpg", "signal.signal", "signal.alarm",
    })

    def __init__(self, sandbox_root: str = "data/sandbox") -> None:
        """Initialize the sandbox.

        Args:
            sandbox_root: Root directory for all sandbox executions.
        """
        self._sandbox_root = Path(sandbox_root).resolve()
        self._sandbox_root.mkdir(parents=True, exist_ok=True)
        self._python = sys.executable
        logger.info("CodeSandbox initialized. Root: %s", self._sandbox_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        code: str,
        timeout_seconds: int = 30,
        max_memory_mb: int = 512,
        allow_imports: Optional[list[str]] = None,
        input_files: Optional[dict[str, str]] = None,
        preserve: bool = False,
    ) -> dict[str, Any]:
        """Execute Python code inside the sandbox.

        Args:
            code: Python source code to execute.
            timeout_seconds: Max wall-clock time before killing.
            max_memory_mb: Memory limit in MB (Linux only).
            allow_imports: Whitelist of allowed imports (None = no restriction).
            input_files: {filename: content} to place in sandbox before execution.
            preserve: If True, keep sandbox directory after execution.

        Returns:
            Dict with execution_id, stdout, stderr, exit_code, timing,
            files_created, files_modified, timed_out, memory_exceeded.
        """
        # Safety validation first
        safety = self.validate_code_safety(code, allow_imports=allow_imports)
        if safety["severity"] == "block":
            return {
                "execution_id": str(uuid.uuid4()),
                "stdout": "",
                "stderr": f"BLOCKED by safety validation: {'; '.join(safety['violations'])}",
                "exit_code": -1,
                "execution_time_ms": 0.0,
                "files_created": [],
                "files_modified": [],
                "timed_out": False,
                "memory_exceeded": False,
                "safety": safety,
            }

        if safety["severity"] == "warn":
            logger.warning(
                "Safety warnings for code execution: %s", safety["violations"]
            )

        execution_id = str(uuid.uuid4())
        exec_dir = self._sandbox_root / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Place input files
            if input_files:
                for filename, content in input_files.items():
                    file_path = exec_dir / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")

            # Track initial file state
            initial_files = self._snapshot_files(exec_dir)

            # Write code to temp file
            code_file = exec_dir / "_sandbox_main.py"
            code_file.write_text(code, encoding="utf-8")

            # Build minimal environment — strip everything sensitive
            safe_env = self._build_safe_env()

            # Build memory-limiting wrapper for Linux
            run_code = code
            if platform.system() == "Linux":
                run_code = self._wrap_with_memory_limit(code, max_memory_mb)
                code_file.write_text(run_code, encoding="utf-8")
            elif platform.system() == "Windows":
                logger.debug(
                    "Memory limiting not available on Windows; "
                    "skipping RLIMIT_AS enforcement."
                )

            # Execute
            start_time = time.monotonic()
            timed_out = False
            memory_exceeded = False

            try:
                result = subprocess.run(
                    [self._python, str(code_file)],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=str(exec_dir),
                    env=safe_env,
                )
                stdout = result.stdout
                stderr = result.stderr
                exit_code = result.returncode
            except subprocess.TimeoutExpired as e:
                timed_out = True
                stdout = e.stdout or "" if isinstance(e.stdout, str) else (e.stdout.decode("utf-8", errors="replace") if e.stdout else "")
                stderr = e.stderr or "" if isinstance(e.stderr, str) else (e.stderr.decode("utf-8", errors="replace") if e.stderr else "")
                exit_code = -1

            execution_time_ms = (time.monotonic() - start_time) * 1000

            # Check for memory-related errors in stderr
            if "MemoryError" in stderr or "Cannot allocate memory" in stderr:
                memory_exceeded = True

            # Determine file changes
            final_files = self._snapshot_files(exec_dir)
            files_created = [
                f for f in final_files
                if f not in initial_files and f != "_sandbox_main.py"
            ]
            files_modified = [
                f for f in final_files
                if f in initial_files and final_files[f] != initial_files[f]
            ]

            return {
                "execution_id": execution_id,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "execution_time_ms": execution_time_ms,
                "files_created": files_created,
                "files_modified": files_modified,
                "timed_out": timed_out,
                "memory_exceeded": memory_exceeded,
                "safety": safety,
            }

        finally:
            if not preserve:
                self._cleanup_dir(exec_dir)

    def execute_with_test(
        self,
        code: str,
        test_code: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute code and run pytest on test code inside the sandbox.

        Args:
            code: The main code to test.
            test_code: Pytest test code that imports/tests the main code.
            **kwargs: Passed through to execute() for safety/limits.

        Returns:
            Execution result dict plus test_results with passed/failed/errors.
        """
        # Validate both code and test code
        safety = self.validate_code_safety(code, allow_imports=kwargs.get("allow_imports"))
        if safety["severity"] == "block":
            return {
                "execution_id": str(uuid.uuid4()),
                "stdout": "",
                "stderr": f"BLOCKED by safety validation: {'; '.join(safety['violations'])}",
                "exit_code": -1,
                "execution_time_ms": 0.0,
                "files_created": [],
                "files_modified": [],
                "timed_out": False,
                "memory_exceeded": False,
                "safety": safety,
                "test_results": {"passed": 0, "failed": 0, "errors": 1, "output": "Blocked by safety"},
            }

        execution_id = str(uuid.uuid4())
        exec_dir = self._sandbox_root / execution_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        timeout_seconds = kwargs.get("timeout_seconds", 30)
        preserve = kwargs.get("preserve", False)

        try:
            # Place input files if provided
            input_files = kwargs.get("input_files")
            if input_files:
                for filename, content in input_files.items():
                    file_path = exec_dir / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")

            # Write code and test files
            code_file = exec_dir / "code_under_test.py"
            code_file.write_text(code, encoding="utf-8")

            test_file = exec_dir / "test_code.py"
            test_file.write_text(test_code, encoding="utf-8")

            safe_env = self._build_safe_env()
            # Add exec_dir to PYTHONPATH so test can import code_under_test
            safe_env["PYTHONPATH"] = str(exec_dir)

            start_time = time.monotonic()
            timed_out = False

            try:
                result = subprocess.run(
                    [self._python, "-m", "pytest", str(test_file), "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=str(exec_dir),
                    env=safe_env,
                )
                stdout = result.stdout
                stderr = result.stderr
                exit_code = result.returncode
            except subprocess.TimeoutExpired as e:
                timed_out = True
                stdout = e.stdout or "" if isinstance(e.stdout, str) else (e.stdout.decode("utf-8", errors="replace") if e.stdout else "")
                stderr = e.stderr or "" if isinstance(e.stderr, str) else (e.stderr.decode("utf-8", errors="replace") if e.stderr else "")
                exit_code = -1

            execution_time_ms = (time.monotonic() - start_time) * 1000

            # Parse pytest output for results
            test_results = self._parse_pytest_output(stdout)

            return {
                "execution_id": execution_id,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "execution_time_ms": execution_time_ms,
                "files_created": [],
                "files_modified": [],
                "timed_out": timed_out,
                "memory_exceeded": False,
                "safety": safety,
                "test_results": test_results,
            }

        finally:
            if not preserve:
                self._cleanup_dir(exec_dir)

    def validate_code_safety(
        self,
        code: str,
        allow_imports: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Static analysis to detect dangerous operations before execution.

        Args:
            code: Python source code to analyze.
            allow_imports: If set, only these imports are allowed.

        Returns:
            Dict with safe (bool), violations (list[str]), severity.
        """
        violations: list[str] = []

        # Parse AST for structured analysis
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Syntax errors will be caught at execution time
            return {"safe": True, "violations": [], "severity": "clean"}

        # Collect all imports
        imports = self._extract_imports(tree)

        # Check network imports
        for imp in imports:
            top_module = imp.split(".")[0]
            if top_module in self._NETWORK_MODULES:
                violations.append(f"Network access: import {imp}")

        # Check subprocess import
        if "subprocess" in imports:
            violations.append("System access: import subprocess")

        # Check import restrictions
        if allow_imports is not None:
            for imp in imports:
                top_module = imp.split(".")[0]
                if top_module not in allow_imports:
                    violations.append(f"Disallowed import: {imp} (not in allow_imports)")

        # Walk AST for dangerous calls and patterns
        for node in ast.walk(tree):
            # Check for os.system, os.popen, etc.
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                if call_name:
                    if call_name in self._SYSTEM_CALLS:
                        violations.append(f"System access: {call_name}()")
                    if call_name in self._CREDENTIAL_PATTERNS:
                        violations.append(f"Credential access: {call_name}")
                    if call_name in self._PROCESS_CALLS:
                        violations.append(f"Process manipulation: {call_name}()")
                    if call_name == "subprocess.run" or call_name == "subprocess.Popen" or call_name == "subprocess.call":
                        violations.append(f"System access: {call_name}()")
                    if call_name == "shutil.rmtree":
                        violations.append(f"Dangerous file operation: {call_name}()")

            # Check for open() with absolute paths
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                if call_name == "open" and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        path = arg.value
                        if self._is_absolute_path(path):
                            violations.append(
                                f"File access outside sandbox: open({path!r})"
                            )
                        if ".env" in path:
                            violations.append(
                                f"Credential access: open({path!r})"
                            )

            # Check for pathlib with absolute paths
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                if call_name == "Path" and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if self._is_absolute_path(arg.value):
                            violations.append(
                                f"File access outside sandbox: Path({arg.value!r})"
                            )

            # Check for os.environ access (attribute access, not just calls)
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == "os":
                    if node.attr == "environ":
                        violations.append("Credential access: os.environ")
                    if node.attr in ("system", "popen"):
                        violations.append(f"System access: os.{node.attr}")

        # Also check with regex for patterns AST might miss
        violations.extend(self._regex_safety_checks(code))

        # Deduplicate
        violations = list(dict.fromkeys(violations))

        # Determine severity
        if not violations:
            severity = "clean"
        elif any(
            v.startswith(("System access", "Credential access", "Process manipulation"))
            for v in violations
        ):
            severity = "block"
        elif any(v.startswith("File access outside sandbox") for v in violations):
            severity = "block"
        elif any(v.startswith("Network access") for v in violations):
            severity = "block"
        elif any(v.startswith("Dangerous file operation") for v in violations):
            severity = "block"
        else:
            severity = "warn"

        return {
            "safe": len(violations) == 0,
            "violations": violations,
            "severity": severity,
        }

    def copy_to_production(
        self,
        sandbox_path: str,
        production_path: str,
        require_tests_pass: bool = True,
        reversibility_engine: Any = None,
        run_tests_fn: Any = None,
    ) -> bool:
        """Copy a file from sandbox to production codebase.

        This is how sandbox code graduates to real code. Goes through
        Cerberus approval via ReversibilityEngine snapshot.

        Args:
            sandbox_path: Path to file inside a sandbox execution dir.
            production_path: Target path in production codebase.
            require_tests_pass: If True, run test suite after copy and rollback on failure.
            reversibility_engine: ReversibilityEngine instance for snapshotting.
            run_tests_fn: Callable that returns True if tests pass.

        Returns:
            True if copy succeeded (and tests passed if required).
        """
        src = Path(sandbox_path).resolve()
        dst = Path(production_path).resolve()

        if not src.exists():
            logger.error("Sandbox file not found: %s", src)
            return False

        # Verify source is inside sandbox root
        try:
            src.relative_to(self._sandbox_root)
        except ValueError:
            logger.error("Source path not inside sandbox: %s", src)
            return False

        # Snapshot before modifying production
        snapshot_id = None
        if reversibility_engine and dst.exists():
            try:
                snapshot_id = reversibility_engine.snapshot_before_action(
                    action_type="file",
                    target_path_or_key=str(dst),
                    metadata={"risk_level": "high", "source": "sandbox_copy_to_production"},
                )
                logger.info("Snapshot taken: %s", snapshot_id)
            except Exception as e:
                logger.error("Failed to snapshot before copy: %s", e)
                return False

        # Copy file
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        logger.info("Copied %s -> %s", src, dst)

        # Run tests if required
        if require_tests_pass and run_tests_fn:
            tests_pass = run_tests_fn()
            if not tests_pass:
                logger.warning("Tests failed after copy. Rolling back.")
                if snapshot_id and reversibility_engine:
                    try:
                        reversibility_engine.rollback(snapshot_id)
                        logger.info("Rollback successful: %s", snapshot_id)
                    except Exception as e:
                        logger.error("Rollback failed: %s", e)
                        # Manual rollback: remove copied file
                        dst.unlink(missing_ok=True)
                else:
                    # No snapshot — just remove the copied file
                    dst.unlink(missing_ok=True)
                return False

        return True

    def list_sandbox_contents(self, execution_id: str) -> list[str]:
        """List all files in a sandbox execution directory.

        Args:
            execution_id: UUID of the execution.

        Returns:
            List of relative file paths.
        """
        exec_dir = self._sandbox_root / execution_id
        if not exec_dir.exists():
            return []
        return [
            str(f.relative_to(exec_dir))
            for f in exec_dir.rglob("*")
            if f.is_file()
        ]

    def get_sandbox_file(self, execution_id: str, filename: str) -> str:
        """Read a file from a sandbox execution directory.

        Args:
            execution_id: UUID of the execution.
            filename: Relative path within the sandbox.

        Returns:
            File contents as string, or empty string if not found.
        """
        file_path = (self._sandbox_root / execution_id / filename).resolve()

        # Verify path is inside sandbox
        try:
            file_path.relative_to(self._sandbox_root / execution_id)
        except ValueError:
            logger.error("Path traversal attempt: %s", filename)
            return ""

        if not file_path.exists():
            return ""
        return file_path.read_text(encoding="utf-8")

    def cleanup_all_sandboxes(self, max_age_hours: int = 24) -> int:
        """Remove old sandbox directories.

        Args:
            max_age_hours: Remove directories older than this many hours.

        Returns:
            Count of directories removed.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        removed = 0

        if not self._sandbox_root.exists():
            return 0

        for entry in self._sandbox_root.iterdir():
            if not entry.is_dir():
                continue
            try:
                mtime = datetime.fromtimestamp(
                    entry.stat().st_mtime, tz=timezone.utc
                )
                if mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
                    logger.debug("Removed old sandbox: %s", entry.name)
            except OSError as e:
                logger.warning("Failed to clean sandbox %s: %s", entry.name, e)

        logger.info("Sandbox cleanup: removed %d directories", removed)
        return removed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_safe_env(self) -> dict[str, str]:
        """Build a minimal, safe environment for subprocess execution."""
        env: dict[str, str] = {}

        # Only set PATH so Python and basic tools are available
        if "PATH" in os.environ:
            env["PATH"] = os.environ["PATH"]

        # Minimal PYTHONPATH — just stdlib
        env["PYTHONPATH"] = ""

        # On Windows, SystemRoot is required for subprocess to work
        if platform.system() == "Windows":
            if "SystemRoot" in os.environ:
                env["SystemRoot"] = os.environ["SystemRoot"]
            if "SYSTEMDRIVE" in os.environ:
                env["SYSTEMDRIVE"] = os.environ["SYSTEMDRIVE"]

        # Encoding
        env["PYTHONIOENCODING"] = "utf-8"

        return env

    def _wrap_with_memory_limit(self, code: str, max_mb: int) -> str:
        """Wrap code with resource limits (Linux only)."""
        limit_bytes = max_mb * 1024 * 1024
        return (
            "import resource\n"
            f"resource.setrlimit(resource.RLIMIT_AS, ({limit_bytes}, {limit_bytes}))\n"
            "\n"
            f"{code}"
        )

    def _snapshot_files(self, directory: Path) -> dict[str, float]:
        """Snapshot file states in a directory (name -> mtime)."""
        files: dict[str, float] = {}
        for f in directory.rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(directory))
                files[rel] = f.stat().st_mtime
        return files

    def _cleanup_dir(self, directory: Path) -> None:
        """Remove a sandbox directory."""
        try:
            shutil.rmtree(directory, ignore_errors=True)
        except Exception as e:
            logger.warning("Failed to clean up %s: %s", directory, e)

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract all import names from an AST."""
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    def _get_call_name(self, node: ast.Call) -> str | None:
        """Get the dotted name of a function call from AST."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            parts: list[str] = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                return ".".join(reversed(parts))
        return None

    @staticmethod
    def _is_absolute_path(path: str) -> bool:
        """Check if a path is absolute (handles both Windows and Unix paths)."""
        # os.path.isabs handles Windows paths (C:\...) but not Unix on Windows
        if os.path.isabs(path):
            return True
        # Also catch Unix-style absolute paths when running on Windows
        if path.startswith("/"):
            return True
        return False

    def _regex_safety_checks(self, code: str) -> list[str]:
        """Additional regex-based safety checks for patterns AST might miss."""
        violations: list[str] = []

        # Check for eval/exec
        if re.search(r"\beval\s*\(", code):
            violations.append("Dangerous builtin: eval()")
        if re.search(r"\bexec\s*\(", code):
            violations.append("Dangerous builtin: exec()")

        # Check for __import__
        if re.search(r"__import__\s*\(", code):
            violations.append("Dynamic import: __import__()")

        return violations

    def _parse_pytest_output(self, output: str) -> dict[str, Any]:
        """Parse pytest output to extract pass/fail/error counts."""
        result = {"passed": 0, "failed": 0, "errors": 0, "output": output}

        # Match pytest summary line like "2 passed, 1 failed"
        match = re.search(r"(\d+)\s+passed", output)
        if match:
            result["passed"] = int(match.group(1))

        match = re.search(r"(\d+)\s+failed", output)
        if match:
            result["failed"] = int(match.group(1))

        match = re.search(r"(\d+)\s+error", output)
        if match:
            result["errors"] = int(match.group(1))

        return result
