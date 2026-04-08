"""
Test Gate — Pre-Change Test Gate with Auto-Revert
===================================================
Every code change Omen makes is automatically reverted if tests fail.
First line of defense against Shadow breaking himself.

NEVER bypass the gate — this is a hard safety system.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("shadow.omen.test_gate")


@dataclass
class TestResult:
    """Result of a test suite run."""

    passed: int
    failed: int
    errors: int
    total: int
    duration_seconds: float
    output: str
    success: bool

    @classmethod
    def from_failure(cls, output: str, duration: float = 0.0) -> TestResult:
        """Create a TestResult representing a complete failure (e.g. pytest not found)."""
        return cls(
            passed=0, failed=0, errors=1, total=0,
            duration_seconds=duration,
            output=output[-500:] if len(output) > 500 else output,
            success=False,
        )


@dataclass
class GateResult:
    """Result of executing a change through the test gate."""

    allowed: bool
    pre_test: TestResult | None
    post_test: TestResult | None
    reverted: bool
    checkpoint_hash: str
    description: str
    reason: str


class TestGate:
    """Pre-change test gate that auto-reverts code changes if tests fail.

    Every code modification goes through this gate:
    1. Create a git checkpoint
    2. Run baseline tests
    3. Apply the change
    4. Run tests again
    5. If ANY test regression: revert immediately. No exceptions.

    Args:
        project_root: Root directory of the codebase. Auto-detects from git if None.
        test_command: Command to run tests. Defaults to pytest.
        test_timeout: Timeout in seconds for test runs.
    """

    def __init__(
        self,
        project_root: str | None = None,
        test_command: str = "python -m pytest tests/ -x -q",
        test_timeout: int = 300,
    ) -> None:
        if project_root:
            self._project_root = Path(project_root).resolve()
        else:
            self._project_root = self._detect_git_root()

        self._test_command = test_command
        self._test_timeout = test_timeout
        self._history: list[dict[str, Any]] = []

    def _detect_git_root(self) -> Path:
        """Detect the git root directory."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip()).resolve()
        except Exception:
            pass
        raise RuntimeError(
            "TestGate requires a git repository. Could not detect git root."
        )

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        """Run a git command in the project root."""
        return subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=30,
            cwd=str(self._project_root),
        )

    def create_checkpoint(self, message: str = "pre-change checkpoint") -> str:
        """Create a git checkpoint by staging and committing all changes.

        Args:
            message: Commit message for the checkpoint.

        Returns:
            The commit hash of the checkpoint.

        Raises:
            RuntimeError: If not in a git repo or git operations fail.
        """
        # Verify we're in a git repo
        check = self._run_git("rev-parse", "--is-inside-work-tree")
        if check.returncode != 0:
            raise RuntimeError(
                f"Not inside a git repository: {self._project_root}"
            )

        # Check if there are changes to commit
        status = self._run_git("status", "--porcelain")
        if status.stdout.strip():
            # Stage and commit
            add_result = self._run_git("add", "-A")
            if add_result.returncode != 0:
                raise RuntimeError(f"git add failed: {add_result.stderr}")

            commit_result = self._run_git("commit", "-m", message)
            if commit_result.returncode != 0:
                raise RuntimeError(f"git commit failed: {commit_result.stderr}")

        # Return current HEAD hash
        head = self._run_git("rev-parse", "HEAD")
        if head.returncode != 0:
            raise RuntimeError(f"Could not get HEAD hash: {head.stderr}")

        return head.stdout.strip()

    def run_tests(self) -> TestResult:
        """Run the test suite and parse results.

        Returns:
            TestResult with pass/fail counts and output.
        """
        start = time.time()
        try:
            result = subprocess.run(
                self._test_command.split(),
                capture_output=True, text=True,
                timeout=self._test_timeout,
                cwd=str(self._project_root),
            )
            duration = time.time() - start
            combined_output = result.stdout + result.stderr
            return self._parse_pytest_output(combined_output, duration)

        except subprocess.TimeoutExpired:
            duration = time.time() - start
            return TestResult.from_failure(
                f"Test suite timed out after {self._test_timeout}s",
                duration,
            )
        except FileNotFoundError:
            duration = time.time() - start
            return TestResult.from_failure(
                "pytest not found. Is it installed?", duration,
            )
        except Exception as e:
            duration = time.time() - start
            return TestResult.from_failure(
                f"Test execution failed: {e}", duration,
            )

    def _parse_pytest_output(self, output: str, duration: float) -> TestResult:
        """Parse pytest output to extract pass/fail/error counts.

        Args:
            output: Raw pytest stdout+stderr.
            duration: How long the run took.

        Returns:
            Parsed TestResult.
        """
        passed = 0
        failed = 0
        errors = 0

        # Match pytest summary line: "X passed", "X failed", "X error"
        passed_match = re.search(r"(\d+)\s+passed", output)
        failed_match = re.search(r"(\d+)\s+failed", output)
        error_match = re.search(r"(\d+)\s+error", output)

        if passed_match:
            passed = int(passed_match.group(1))
        if failed_match:
            failed = int(failed_match.group(1))
        if error_match:
            errors = int(error_match.group(1))

        total = passed + failed + errors
        truncated = output[-500:] if len(output) > 500 else output

        return TestResult(
            passed=passed,
            failed=failed,
            errors=errors,
            total=total,
            duration_seconds=duration,
            output=truncated,
            success=(failed == 0 and errors == 0 and total > 0),
        )

    def execute_with_gate(
        self,
        change_fn: Callable[[], Any],
        description: str = "",
    ) -> GateResult:
        """Execute a code change through the test gate.

        This is the core safety mechanism:
        1. Checkpoint current state
        2. Run baseline tests
        3. Apply the change
        4. Run tests again
        5. If ANY regression → revert immediately

        Args:
            change_fn: Callable that applies the code change.
            description: Human-readable description of the change.

        Returns:
            GateResult indicating whether the change was allowed or reverted.
        """
        checkpoint_hash = ""
        pre_test = None
        post_test = None

        try:
            # Step 1: Create checkpoint
            checkpoint_hash = self.create_checkpoint(
                f"pre-change checkpoint: {description}"
            )
            logger.info("TestGate checkpoint: %s for '%s'", checkpoint_hash, description)

            # Step 2: Run baseline tests
            pre_test = self.run_tests()
            if not pre_test.success:
                reason = (
                    f"Baseline tests already failing "
                    f"({pre_test.failed} failed, {pre_test.errors} errors). "
                    f"Cannot gate changes against a broken baseline."
                )
                logger.warning("TestGate: %s", reason)
                result = GateResult(
                    allowed=False, pre_test=pre_test, post_test=None,
                    reverted=False, checkpoint_hash=checkpoint_hash,
                    description=description, reason=reason,
                )
                self._record_history(result)
                return result

            baseline_passed = pre_test.passed

            # Step 3: Apply the change
            try:
                change_fn()
            except Exception as e:
                # Change function itself failed — revert
                logger.error("TestGate: change_fn raised %s, reverting", e)
                self.revert_to_checkpoint(checkpoint_hash)
                reason = f"change_fn raised exception: {e}"
                result = GateResult(
                    allowed=False, pre_test=pre_test, post_test=None,
                    reverted=True, checkpoint_hash=checkpoint_hash,
                    description=description, reason=reason,
                )
                self._record_history(result)
                return result

            # Step 4: Run tests again
            post_test = self.run_tests()

            # Step 5: Hard gate — revert if ANY regression
            if not post_test.success or post_test.passed < baseline_passed:
                reasons = []
                if post_test.failed > 0:
                    reasons.append(f"{post_test.failed} test(s) failed")
                if post_test.errors > 0:
                    reasons.append(f"{post_test.errors} error(s)")
                if post_test.passed < baseline_passed:
                    drop = baseline_passed - post_test.passed
                    reasons.append(
                        f"pass count dropped by {drop} "
                        f"({baseline_passed} → {post_test.passed})"
                    )
                reason = "REVERTED: " + "; ".join(reasons)
                logger.warning("TestGate: %s", reason)

                self.revert_to_checkpoint(checkpoint_hash)

                result = GateResult(
                    allowed=False, pre_test=pre_test, post_test=post_test,
                    reverted=True, checkpoint_hash=checkpoint_hash,
                    description=description, reason=reason,
                )
                self._record_history(result)
                return result

            # Step 6: All clear — change allowed
            reason = (
                f"Tests passed: {post_test.passed} "
                f"(baseline: {baseline_passed})"
            )
            logger.info("TestGate ALLOWED: %s", reason)
            result = GateResult(
                allowed=True, pre_test=pre_test, post_test=post_test,
                reverted=False, checkpoint_hash=checkpoint_hash,
                description=description, reason=reason,
            )
            self._record_history(result)
            return result

        except Exception as e:
            # Catastrophic failure — try to revert
            logger.error("TestGate catastrophic error: %s", e)
            reverted = False
            if checkpoint_hash:
                reverted = self.revert_to_checkpoint(checkpoint_hash)

            result = GateResult(
                allowed=False, pre_test=pre_test, post_test=post_test,
                reverted=reverted, checkpoint_hash=checkpoint_hash,
                description=description,
                reason=f"Gate error: {e}",
            )
            self._record_history(result)
            return result

    def revert_to_checkpoint(self, commit_hash: str) -> bool:
        """Revert to a previous checkpoint.

        Uses git reset --hard to restore the exact state at the checkpoint.

        Args:
            commit_hash: The commit hash to revert to.

        Returns:
            True if revert succeeded, False otherwise.
        """
        try:
            result = self._run_git("reset", "--hard", commit_hash)
            if result.returncode == 0:
                logger.info("TestGate reverted to checkpoint %s", commit_hash)
                return True
            else:
                logger.error(
                    "TestGate revert failed: %s", result.stderr
                )
                return False
        except Exception as e:
            logger.error("TestGate revert error: %s", e)
            return False

    def get_gate_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent gate decisions for the Growth Engine.

        Args:
            limit: Max number of entries to return.

        Returns:
            List of gate decision records, newest first.
        """
        return self._history[-limit:][::-1]

    def _record_history(self, result: GateResult) -> None:
        """Record a gate decision in history."""
        self._history.append({
            "timestamp": datetime.now().isoformat(),
            "description": result.description,
            "allowed": result.allowed,
            "reverted": result.reverted,
            "reason": result.reason,
            "baseline_passed": result.pre_test.passed if result.pre_test else None,
            "post_passed": result.post_test.passed if result.post_test else None,
            "checkpoint": result.checkpoint_hash,
        })
