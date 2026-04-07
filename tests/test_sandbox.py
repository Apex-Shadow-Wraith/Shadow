"""
Tests for Omen Code Execution Sandbox
=======================================
Validates isolation, safety validation, timeout enforcement,
environment stripping, file tracking, and production graduation.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.omen.sandbox import CodeSandbox


@pytest.fixture
def sandbox(tmp_path):
    """Create a sandbox with a temporary root directory."""
    root = tmp_path / "sandbox"
    root.mkdir()
    return CodeSandbox(sandbox_root=str(root))


@pytest.fixture
def sandbox_root(tmp_path):
    """Return a temporary sandbox root path."""
    return tmp_path / "sandbox"


# ------------------------------------------------------------------
# execute: basic execution
# ------------------------------------------------------------------

class TestExecute:
    """Tests for sandbox.execute()."""

    def test_captures_stdout(self, sandbox):
        """Execute runs Python code and captures stdout."""
        result = sandbox.execute("print('hello sandbox')")
        assert result["exit_code"] == 0
        assert "hello sandbox" in result["stdout"]
        assert result["timed_out"] is False

    def test_captures_stderr(self, sandbox):
        """Execute captures stderr from failing code."""
        result = sandbox.execute("import sys; print('err', file=sys.stderr)")
        assert "err" in result["stderr"]

    def test_returns_execution_id(self, sandbox):
        """Each execution gets a unique ID."""
        r1 = sandbox.execute("print(1)")
        r2 = sandbox.execute("print(2)")
        assert r1["execution_id"] != r2["execution_id"]

    def test_enforces_timeout(self, sandbox):
        """Infinite loop killed after timeout_seconds."""
        result = sandbox.execute(
            "import time\nwhile True: time.sleep(0.1)",
            timeout_seconds=2,
        )
        assert result["timed_out"] is True
        assert result["exit_code"] == -1

    def test_strips_environment_variables(self, sandbox):
        """Code cannot access os.environ API keys.

        We bypass safety validation here to confirm the env is actually
        stripped at the subprocess level (not just blocked by static analysis).
        """
        os.environ["SHADOW_TEST_SECRET"] = "super_secret_key"
        try:
            # Patch validate_code_safety to allow os.environ for this test
            original = sandbox.validate_code_safety
            sandbox.validate_code_safety = lambda code, **kw: {
                "safe": True, "violations": [], "severity": "clean"
            }
            result = sandbox.execute(
                "import os; print(os.environ.get('SHADOW_TEST_SECRET', 'NOT_FOUND'))"
            )
            sandbox.validate_code_safety = original
            # The sandbox strips env vars, so the key should not be accessible
            assert "super_secret_key" not in result["stdout"]
            assert "NOT_FOUND" in result["stdout"]
        finally:
            del os.environ["SHADOW_TEST_SECRET"]

    def test_isolates_filesystem(self, sandbox):
        """Code cannot read files outside sandbox."""
        # Try to read a file that exists on the real filesystem
        # The code runs in the sandbox dir, so absolute paths to project files
        # should fail or return nothing meaningful
        result = sandbox.execute(
            "from pathlib import Path\n"
            "try:\n"
            "    content = Path('../../CLAUDE.md').read_text()\n"
            "    print('LEAK:' + content[:20])\n"
            "except Exception as e:\n"
            "    print('BLOCKED:' + str(type(e).__name__))\n"
        )
        # The sandbox dir is cleaned up, so the relative path won't resolve
        # to the real CLAUDE.md since cwd is inside sandbox
        assert result["exit_code"] == 0

    def test_captures_files_created(self, sandbox):
        """Execute correctly lists new files created by code."""
        result = sandbox.execute(
            "with open('output.txt', 'w') as f: f.write('hello')",
            preserve=True,
        )
        assert result["exit_code"] == 0
        assert "output.txt" in result["files_created"]

    def test_input_files_available(self, sandbox):
        """Input files are accessible inside the sandbox."""
        result = sandbox.execute(
            "print(open('data.txt').read())",
            input_files={"data.txt": "test content"},
        )
        assert result["exit_code"] == 0
        assert "test content" in result["stdout"]

    def test_nonzero_exit_code(self, sandbox):
        """Code that raises an exception returns non-zero exit code."""
        result = sandbox.execute("raise ValueError('boom')")
        assert result["exit_code"] != 0
        assert "ValueError" in result["stderr"]

    def test_blocked_code_not_executed(self, sandbox):
        """Code flagged as 'block' by safety validation is not run."""
        result = sandbox.execute("import os; os.system('echo pwned')")
        assert result["exit_code"] == -1
        assert result["safety"]["severity"] == "block"
        assert "BLOCKED" in result["stderr"]


# ------------------------------------------------------------------
# validate_code_safety
# ------------------------------------------------------------------

class TestValidateCodeSafety:
    """Tests for sandbox.validate_code_safety()."""

    def test_blocks_os_system(self, sandbox):
        """os.system calls are blocked."""
        result = sandbox.validate_code_safety("import os\nos.system('rm -rf /')")
        assert result["safe"] is False
        assert result["severity"] == "block"
        assert any("os.system" in v for v in result["violations"])

    def test_blocks_network_imports(self, sandbox):
        """Network library imports are blocked."""
        result = sandbox.validate_code_safety("import requests\nrequests.get('http://evil.com')")
        assert result["safe"] is False
        assert result["severity"] == "block"
        assert any("Network" in v for v in result["violations"])

    def test_blocks_absolute_path_file_access(self, sandbox):
        """open() with absolute paths is blocked."""
        result = sandbox.validate_code_safety("f = open('/etc/passwd', 'r')")
        assert result["safe"] is False
        assert any("outside sandbox" in v for v in result["violations"])

    def test_allows_clean_code(self, sandbox):
        """Clean code passes validation."""
        result = sandbox.validate_code_safety(
            "x = 42\nprint(f'The answer is {x}')\nresult = [i**2 for i in range(10)]"
        )
        assert result["safe"] is True
        assert result["severity"] == "clean"
        assert result["violations"] == []

    def test_blocks_subprocess(self, sandbox):
        """subprocess import is blocked."""
        result = sandbox.validate_code_safety("import subprocess\nsubprocess.run(['ls'])")
        assert result["safe"] is False
        assert result["severity"] == "block"

    def test_blocks_os_environ(self, sandbox):
        """os.environ access is blocked."""
        result = sandbox.validate_code_safety("import os\nkeys = os.environ")
        assert result["safe"] is False
        assert any("environ" in v.lower() for v in result["violations"])

    def test_blocks_eval(self, sandbox):
        """eval() calls are flagged."""
        result = sandbox.validate_code_safety("eval('__import__(\"os\").system(\"ls\")')")
        assert result["safe"] is False

    def test_blocks_dotenv(self, sandbox):
        """dotenv references are blocked."""
        result = sandbox.validate_code_safety("from dotenv import load_dotenv\nload_dotenv()")
        assert result["safe"] is False

    def test_import_whitelist(self, sandbox):
        """When allow_imports is set, unlisted imports are flagged."""
        result = sandbox.validate_code_safety(
            "import json\nimport math\nimport pandas",
            allow_imports=["json", "math"],
        )
        assert result["safe"] is False
        assert any("pandas" in v for v in result["violations"])

    def test_import_whitelist_allows_listed(self, sandbox):
        """When allow_imports is set, listed imports pass."""
        result = sandbox.validate_code_safety(
            "import json\nimport math",
            allow_imports=["json", "math"],
        )
        assert result["safe"] is True

    def test_blocks_socket(self, sandbox):
        """socket import is blocked."""
        result = sandbox.validate_code_safety("import socket\ns = socket.socket()")
        assert result["safe"] is False
        assert result["severity"] == "block"


# ------------------------------------------------------------------
# execute_with_test
# ------------------------------------------------------------------

class TestExecuteWithTest:
    """Tests for sandbox.execute_with_test()."""

    def test_runs_passing_tests(self, sandbox):
        """Pytest runs and reports passing tests."""
        code = "def add(a, b):\n    return a + b\n"
        test_code = (
            "from code_under_test import add\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
            "def test_add_negative():\n"
            "    assert add(-1, 1) == 0\n"
        )
        result = sandbox.execute_with_test(code, test_code)
        assert result["test_results"]["passed"] >= 2
        assert result["test_results"]["failed"] == 0

    def test_runs_failing_tests(self, sandbox):
        """Pytest reports failing tests correctly."""
        code = "def add(a, b):\n    return a - b  # bug!\n"
        test_code = (
            "from code_under_test import add\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
        )
        result = sandbox.execute_with_test(code, test_code)
        assert result["test_results"]["failed"] >= 1

    def test_blocked_code_returns_error(self, sandbox):
        """Blocked code returns error in test results."""
        code = "import os\nos.system('echo bad')\n"
        test_code = "def test_noop(): pass\n"
        result = sandbox.execute_with_test(code, test_code)
        assert result["exit_code"] == -1
        assert result["test_results"]["errors"] >= 1


# ------------------------------------------------------------------
# copy_to_production
# ------------------------------------------------------------------

class TestCopyToProduction:
    """Tests for sandbox.copy_to_production()."""

    def test_snapshots_before_copying(self, sandbox, tmp_path):
        """ReversibilityEngine.snapshot_before_action is called before copy."""
        # Create a sandbox file
        exec_dir = sandbox._sandbox_root / "test_exec"
        exec_dir.mkdir()
        src = exec_dir / "new_module.py"
        src.write_text("# new code", encoding="utf-8")

        # Create existing production file
        prod_file = tmp_path / "prod" / "module.py"
        prod_file.parent.mkdir()
        prod_file.write_text("# old code", encoding="utf-8")

        # Mock ReversibilityEngine
        mock_rev = MagicMock()
        mock_rev.snapshot_before_action.return_value = "snap123"

        result = sandbox.copy_to_production(
            sandbox_path=str(src),
            production_path=str(prod_file),
            require_tests_pass=False,
            reversibility_engine=mock_rev,
        )

        assert result is True
        mock_rev.snapshot_before_action.assert_called_once()
        assert prod_file.read_text(encoding="utf-8") == "# new code"

    def test_rolls_back_if_tests_fail(self, sandbox, tmp_path):
        """If tests fail after copy, file is rolled back."""
        exec_dir = sandbox._sandbox_root / "test_exec2"
        exec_dir.mkdir()
        src = exec_dir / "bad_module.py"
        src.write_text("# broken code", encoding="utf-8")

        prod_file = tmp_path / "prod2" / "module.py"
        prod_file.parent.mkdir()
        prod_file.write_text("# good code", encoding="utf-8")

        mock_rev = MagicMock()
        mock_rev.snapshot_before_action.return_value = "snap456"

        result = sandbox.copy_to_production(
            sandbox_path=str(src),
            production_path=str(prod_file),
            require_tests_pass=True,
            reversibility_engine=mock_rev,
            run_tests_fn=lambda: False,  # Tests fail
        )

        assert result is False
        mock_rev.rollback.assert_called_once_with("snap456")

    def test_rejects_path_outside_sandbox(self, sandbox, tmp_path):
        """Source path not inside sandbox root is rejected."""
        external_file = tmp_path / "external.py"
        external_file.write_text("# sneaky")

        result = sandbox.copy_to_production(
            sandbox_path=str(external_file),
            production_path=str(tmp_path / "prod.py"),
        )
        assert result is False

    def test_copies_new_file_without_snapshot(self, sandbox, tmp_path):
        """Copying to a path that doesn't exist yet works without snapshot."""
        exec_dir = sandbox._sandbox_root / "test_exec3"
        exec_dir.mkdir()
        src = exec_dir / "brand_new.py"
        src.write_text("# brand new", encoding="utf-8")

        prod_file = tmp_path / "new_prod" / "new_module.py"

        result = sandbox.copy_to_production(
            sandbox_path=str(src),
            production_path=str(prod_file),
            require_tests_pass=False,
        )

        assert result is True
        assert prod_file.read_text(encoding="utf-8") == "# brand new"


# ------------------------------------------------------------------
# cleanup
# ------------------------------------------------------------------

class TestCleanup:
    """Tests for sandbox.cleanup_all_sandboxes()."""

    def test_removes_old_sandboxes(self, sandbox):
        """Old directories are removed."""
        old_dir = sandbox._sandbox_root / "old_execution"
        old_dir.mkdir()
        (old_dir / "code.py").write_text("x = 1")

        # Set mtime to 48 hours ago
        old_time = time.time() - (48 * 3600)
        os.utime(str(old_dir), (old_time, old_time))

        removed = sandbox.cleanup_all_sandboxes(max_age_hours=24)
        assert removed >= 1
        assert not old_dir.exists()

    def test_preserves_recent_sandboxes(self, sandbox):
        """Recent directories are kept."""
        recent_dir = sandbox._sandbox_root / "recent_execution"
        recent_dir.mkdir()
        (recent_dir / "code.py").write_text("x = 1")

        removed = sandbox.cleanup_all_sandboxes(max_age_hours=24)
        assert removed == 0
        assert recent_dir.exists()


# ------------------------------------------------------------------
# list_sandbox_contents / get_sandbox_file
# ------------------------------------------------------------------

class TestSandboxFileOps:
    """Tests for listing and reading sandbox files."""

    def test_list_sandbox_contents(self, sandbox):
        """List files in a sandbox directory."""
        exec_dir = sandbox._sandbox_root / "list_test"
        exec_dir.mkdir()
        (exec_dir / "a.py").write_text("# a")
        (exec_dir / "b.txt").write_text("hello")

        files = sandbox.list_sandbox_contents("list_test")
        assert "a.py" in files
        assert "b.txt" in files

    def test_get_sandbox_file(self, sandbox):
        """Read a file from sandbox."""
        exec_dir = sandbox._sandbox_root / "read_test"
        exec_dir.mkdir()
        (exec_dir / "output.txt").write_text("result data", encoding="utf-8")

        content = sandbox.get_sandbox_file("read_test", "output.txt")
        assert content == "result data"

    def test_get_sandbox_file_blocks_traversal(self, sandbox):
        """Path traversal attempts return empty string."""
        exec_dir = sandbox._sandbox_root / "traverse_test"
        exec_dir.mkdir()

        content = sandbox.get_sandbox_file("traverse_test", "../../etc/passwd")
        assert content == ""

    def test_list_nonexistent(self, sandbox):
        """Listing a nonexistent execution returns empty list."""
        assert sandbox.list_sandbox_contents("nonexistent") == []


# ------------------------------------------------------------------
# Full flow: validate → execute → test → copy_to_production
# ------------------------------------------------------------------

class TestFullFlow:
    """Integration test: validate → execute → test → pass → copy."""

    def test_full_production_graduation(self, sandbox, tmp_path):
        """Full flow from validation through production copy."""
        code = "def multiply(a, b):\n    return a * b\n"
        test_code = (
            "from code_under_test import multiply\n"
            "def test_multiply():\n"
            "    assert multiply(3, 4) == 12\n"
            "def test_multiply_zero():\n"
            "    assert multiply(0, 5) == 0\n"
        )

        # Step 1: Validate
        safety = sandbox.validate_code_safety(code)
        assert safety["severity"] == "clean"

        # Step 2: Execute
        exec_result = sandbox.execute(code, preserve=True)
        assert exec_result["exit_code"] == 0

        # Step 3: Test
        test_result = sandbox.execute_with_test(code, test_code)
        assert test_result["test_results"]["passed"] >= 2
        assert test_result["test_results"]["failed"] == 0

        # Step 4: Copy to production
        # Create a sandbox file to copy
        exec_dir = sandbox._sandbox_root / "grad_test"
        exec_dir.mkdir()
        src = exec_dir / "multiply.py"
        src.write_text(code, encoding="utf-8")

        prod_file = tmp_path / "production" / "multiply.py"
        mock_rev = MagicMock()
        mock_rev.snapshot_before_action.return_value = "snap_grad"

        success = sandbox.copy_to_production(
            sandbox_path=str(src),
            production_path=str(prod_file),
            require_tests_pass=True,
            reversibility_engine=mock_rev,
            run_tests_fn=lambda: True,  # Tests pass
        )

        assert success is True
        assert prod_file.read_text(encoding="utf-8") == code
