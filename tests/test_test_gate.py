"""Tests for TestGate — Pre-Change Test Gate with Auto-Revert."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from modules.omen.test_gate import GateResult, TestGate, TestResult


# ---------------------------------------------------------------------------
# TestResult dataclass tests
# ---------------------------------------------------------------------------

class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_from_failure_creates_failed_result(self):
        """from_failure should produce errors=1, success=False."""
        r = TestResult.from_failure("boom", 1.5)
        assert r.success is False
        assert r.errors == 1
        assert r.passed == 0
        assert r.failed == 0
        assert r.duration_seconds == 1.5
        assert r.output == "boom"

    def test_from_failure_truncates_long_output(self):
        """Output should be capped at 500 chars."""
        long_output = "x" * 1000
        r = TestResult.from_failure(long_output)
        assert len(r.output) == 500

    def test_success_when_all_pass(self):
        """success=True when failed==0 and errors==0 and total>0."""
        r = TestResult(passed=10, failed=0, errors=0, total=10,
                       duration_seconds=1.0, output="", success=True)
        assert r.success is True

    def test_not_success_when_failures(self):
        """success=False when there are failures."""
        r = TestResult(passed=9, failed=1, errors=0, total=10,
                       duration_seconds=1.0, output="", success=False)
        assert r.success is False


# ---------------------------------------------------------------------------
# TestGate — checkpoint tests
# ---------------------------------------------------------------------------

class TestCreateCheckpoint:
    """Tests for TestGate.create_checkpoint."""

    @patch("modules.omen.test_gate.subprocess.run")
    def test_returns_commit_hash(self, mock_run):
        """create_checkpoint should return a valid commit hash."""
        mock_run.side_effect = [
            # _detect_git_root
            MagicMock(returncode=0, stdout="/project\n"),
            # rev-parse --is-inside-work-tree
            MagicMock(returncode=0, stdout="true\n"),
            # status --porcelain (has changes)
            MagicMock(returncode=0, stdout="M file.py\n"),
            # git add -A
            MagicMock(returncode=0),
            # git commit
            MagicMock(returncode=0),
            # rev-parse HEAD
            MagicMock(returncode=0, stdout="abc123def456\n"),
        ]
        gate = TestGate()
        h = gate.create_checkpoint("test checkpoint")
        assert h == "abc123def456"

    @patch("modules.omen.test_gate.subprocess.run")
    def test_clean_tree_returns_head(self, mock_run):
        """Clean working tree should just return current HEAD."""
        mock_run.side_effect = [
            # _detect_git_root
            MagicMock(returncode=0, stdout="/project\n"),
            # rev-parse --is-inside-work-tree
            MagicMock(returncode=0, stdout="true\n"),
            # status --porcelain (clean)
            MagicMock(returncode=0, stdout=""),
            # rev-parse HEAD
            MagicMock(returncode=0, stdout="headhash\n"),
        ]
        gate = TestGate()
        h = gate.create_checkpoint()
        assert h == "headhash"

    @patch("modules.omen.test_gate.subprocess.run")
    def test_not_git_repo_raises(self, mock_run):
        """Should raise RuntimeError if not in a git repo."""
        mock_run.side_effect = [
            # _detect_git_root
            MagicMock(returncode=0, stdout="/project\n"),
            # rev-parse --is-inside-work-tree (fails)
            MagicMock(returncode=128, stdout="", stderr="not a repo"),
        ]
        gate = TestGate()
        with pytest.raises(RuntimeError, match="Not inside a git repository"):
            gate.create_checkpoint()


# ---------------------------------------------------------------------------
# TestGate — run_tests tests
# ---------------------------------------------------------------------------

class TestRunTests:
    """Tests for TestGate.run_tests."""

    @patch("modules.omen.test_gate.subprocess.run")
    def test_parses_pytest_output(self, mock_run):
        """Should correctly parse pytest summary line."""
        mock_run.side_effect = [
            # _detect_git_root
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        mock_run.side_effect = [
            MagicMock(
                returncode=0,
                stdout="947 passed, 2 failed, 1 error in 12.34s\n",
                stderr="",
            ),
        ]
        r = gate.run_tests()
        assert r.passed == 947
        assert r.failed == 2
        assert r.errors == 1
        assert r.total == 950
        assert r.success is False

    @patch("modules.omen.test_gate.subprocess.run")
    def test_all_passed(self, mock_run):
        """All tests passing should give success=True."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="100 passed in 5.0s\n", stderr=""),
        ]
        r = gate.run_tests()
        assert r.passed == 100
        assert r.failed == 0
        assert r.success is True

    @patch("modules.omen.test_gate.subprocess.run")
    def test_pytest_not_found(self, mock_run):
        """Should handle FileNotFoundError gracefully."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        mock_run.side_effect = FileNotFoundError("pytest not found")
        r = gate.run_tests()
        assert r.success is False
        assert "not found" in r.output.lower()

    @patch("modules.omen.test_gate.subprocess.run")
    def test_timeout(self, mock_run):
        """Should handle timeout gracefully."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)
        r = gate.run_tests()
        assert r.success is False
        assert "timed out" in r.output.lower()


# ---------------------------------------------------------------------------
# TestGate — execute_with_gate tests
# ---------------------------------------------------------------------------

class TestExecuteWithGate:
    """Tests for TestGate.execute_with_gate."""

    def _make_gate(self, mock_run):
        """Helper: create a TestGate with mocked git root."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        return TestGate()

    def _checkpoint_calls(self):
        """Mock responses for create_checkpoint (clean tree)."""
        return [
            # rev-parse --is-inside-work-tree
            MagicMock(returncode=0, stdout="true\n"),
            # status --porcelain (clean)
            MagicMock(returncode=0, stdout=""),
            # rev-parse HEAD
            MagicMock(returncode=0, stdout="checkpoint123\n"),
        ]

    def _test_result(self, passed=100, failed=0, errors=0):
        """Mock subprocess result mimicking pytest output."""
        parts = []
        if passed:
            parts.append(f"{passed} passed")
        if failed:
            parts.append(f"{failed} failed")
        if errors:
            parts.append(f"{errors} error")
        summary = ", ".join(parts) + " in 5.0s\n"
        return MagicMock(returncode=0 if not failed else 1,
                         stdout=summary, stderr="")

    @patch("modules.omen.test_gate.subprocess.run")
    def test_change_passes_tests_allowed(self, mock_run):
        """Change that passes tests should be allowed, not reverted."""
        gate = self._make_gate(mock_run)
        mock_run.side_effect = [
            *self._checkpoint_calls(),
            self._test_result(passed=100),    # baseline
            self._test_result(passed=100),    # post-change
        ]
        result = gate.execute_with_gate(lambda: None, "no-op change")
        assert result.allowed is True
        assert result.reverted is False

    @patch("modules.omen.test_gate.subprocess.run")
    def test_change_breaks_tests_reverted(self, mock_run):
        """Change that breaks tests should be reverted."""
        gate = self._make_gate(mock_run)
        mock_run.side_effect = [
            *self._checkpoint_calls(),
            self._test_result(passed=100),            # baseline
            self._test_result(passed=99, failed=1),   # post-change: failure!
            # revert: git reset --hard checkpoint123
            MagicMock(returncode=0),
        ]
        result = gate.execute_with_gate(lambda: None, "breaking change")
        assert result.allowed is False
        assert result.reverted is True
        assert "REVERTED" in result.reason

    @patch("modules.omen.test_gate.subprocess.run")
    def test_even_one_fewer_pass_reverted(self, mock_run):
        """Even 1 fewer passing test should trigger revert."""
        gate = self._make_gate(mock_run)
        mock_run.side_effect = [
            *self._checkpoint_calls(),
            self._test_result(passed=100),   # baseline
            self._test_result(passed=99),    # post: 1 less pass, no failures
            # revert
            MagicMock(returncode=0),
        ]
        result = gate.execute_with_gate(lambda: None, "subtle regression")
        assert result.allowed is False
        assert result.reverted is True
        assert "dropped by 1" in result.reason

    @patch("modules.omen.test_gate.subprocess.run")
    def test_new_failures_reverted(self, mock_run):
        """New test failures should trigger revert."""
        gate = self._make_gate(mock_run)
        mock_run.side_effect = [
            *self._checkpoint_calls(),
            self._test_result(passed=100),                    # baseline
            self._test_result(passed=100, errors=1),          # post: error
            # revert
            MagicMock(returncode=0),
        ]
        result = gate.execute_with_gate(lambda: None, "error introduction")
        assert result.allowed is False
        assert result.reverted is True

    @patch("modules.omen.test_gate.subprocess.run")
    def test_pass_count_increases_allowed(self, mock_run):
        """If pass count goes up (new tests added), allow it."""
        gate = self._make_gate(mock_run)
        mock_run.side_effect = [
            *self._checkpoint_calls(),
            self._test_result(passed=100),   # baseline
            self._test_result(passed=105),   # post: 5 new tests
        ]
        result = gate.execute_with_gate(lambda: None, "added tests")
        assert result.allowed is True
        assert result.reverted is False

    @patch("modules.omen.test_gate.subprocess.run")
    def test_change_fn_exception_reverts(self, mock_run):
        """If change_fn raises, revert cleanly."""
        gate = self._make_gate(mock_run)
        mock_run.side_effect = [
            *self._checkpoint_calls(),
            self._test_result(passed=100),   # baseline
            # revert after exception
            MagicMock(returncode=0),
        ]

        def exploding_change():
            raise ValueError("kaboom")

        result = gate.execute_with_gate(exploding_change, "exploding change")
        assert result.allowed is False
        assert result.reverted is True
        assert "kaboom" in result.reason

    @patch("modules.omen.test_gate.subprocess.run")
    def test_baseline_already_failing(self, mock_run):
        """If baseline tests already fail, refuse to gate (not reverted)."""
        gate = self._make_gate(mock_run)
        mock_run.side_effect = [
            *self._checkpoint_calls(),
            self._test_result(passed=95, failed=5),   # baseline failing
        ]
        result = gate.execute_with_gate(lambda: None, "on broken baseline")
        assert result.allowed is False
        assert result.reverted is False
        assert "Baseline tests already failing" in result.reason

    @patch("modules.omen.test_gate.subprocess.run")
    def test_checkpoint_hash_in_result(self, mock_run):
        """GateResult should contain the checkpoint hash."""
        gate = self._make_gate(mock_run)
        mock_run.side_effect = [
            *self._checkpoint_calls(),
            self._test_result(passed=100),
            self._test_result(passed=100),
        ]
        result = gate.execute_with_gate(lambda: None, "hash check")
        assert result.checkpoint_hash == "checkpoint123"


# ---------------------------------------------------------------------------
# TestGate — revert_to_checkpoint tests
# ---------------------------------------------------------------------------

class TestRevertToCheckpoint:
    """Tests for TestGate.revert_to_checkpoint."""

    @patch("modules.omen.test_gate.subprocess.run")
    def test_revert_success(self, mock_run):
        """Successful revert returns True."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        mock_run.side_effect = [
            MagicMock(returncode=0),   # git reset --hard
        ]
        assert gate.revert_to_checkpoint("abc123") is True

    @patch("modules.omen.test_gate.subprocess.run")
    def test_revert_failure(self, mock_run):
        """Failed revert returns False."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        mock_run.side_effect = [
            MagicMock(returncode=1, stderr="reset failed"),
        ]
        assert gate.revert_to_checkpoint("abc123") is False

    @patch("modules.omen.test_gate.subprocess.run")
    def test_revert_exception(self, mock_run):
        """Exception during revert returns False."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        mock_run.side_effect = Exception("git crashed")
        assert gate.revert_to_checkpoint("abc123") is False


# ---------------------------------------------------------------------------
# TestGate — history tests
# ---------------------------------------------------------------------------

class TestGateHistory:
    """Tests for TestGate.get_gate_history."""

    @patch("modules.omen.test_gate.subprocess.run")
    def test_empty_history(self, mock_run):
        """Fresh gate should have empty history."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()
        assert gate.get_gate_history() == []

    @patch("modules.omen.test_gate.subprocess.run")
    def test_history_records_decisions(self, mock_run):
        """Gate history should record decisions."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        # Manually add a history entry
        gate._history.append({
            "timestamp": "2026-04-07T10:00:00",
            "description": "test change",
            "allowed": True,
            "reverted": False,
            "reason": "all good",
            "baseline_passed": 100,
            "post_passed": 100,
            "checkpoint": "abc123",
        })
        history = gate.get_gate_history()
        assert len(history) == 1
        assert history[0]["allowed"] is True

    @patch("modules.omen.test_gate.subprocess.run")
    def test_history_respects_limit(self, mock_run):
        """get_gate_history should respect the limit parameter."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        for i in range(30):
            gate._history.append({
                "timestamp": f"2026-04-07T10:{i:02d}:00",
                "description": f"change {i}",
                "allowed": True,
                "reverted": False,
                "reason": "ok",
                "baseline_passed": 100,
                "post_passed": 100,
                "checkpoint": f"hash{i}",
            })

        assert len(gate.get_gate_history(limit=5)) == 5
        assert len(gate.get_gate_history(limit=20)) == 20

    @patch("modules.omen.test_gate.subprocess.run")
    def test_history_newest_first(self, mock_run):
        """History should be returned newest first."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        gate._history.append({"description": "first", "timestamp": "t1",
                              "allowed": True, "reverted": False,
                              "reason": "", "baseline_passed": 0,
                              "post_passed": 0, "checkpoint": ""})
        gate._history.append({"description": "second", "timestamp": "t2",
                              "allowed": True, "reverted": False,
                              "reason": "", "baseline_passed": 0,
                              "post_passed": 0, "checkpoint": ""})
        history = gate.get_gate_history()
        assert history[0]["description"] == "second"
        assert history[1]["description"] == "first"


# ---------------------------------------------------------------------------
# TestGate — sequential gates
# ---------------------------------------------------------------------------

class TestSequentialGates:
    """Tests for multiple sequential gate operations."""

    @patch("modules.omen.test_gate.subprocess.run")
    def test_multiple_sequential_gates(self, mock_run):
        """Multiple gates in sequence should each work independently."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()

        # First gate — allowed
        mock_run.side_effect = [
            # checkpoint
            MagicMock(returncode=0, stdout="true\n"),
            MagicMock(returncode=0, stdout=""),
            MagicMock(returncode=0, stdout="hash1\n"),
            # baseline
            MagicMock(returncode=0, stdout="100 passed in 1s\n", stderr=""),
            # post
            MagicMock(returncode=0, stdout="100 passed in 1s\n", stderr=""),
        ]
        r1 = gate.execute_with_gate(lambda: None, "change 1")
        assert r1.allowed is True

        # Second gate — reverted
        mock_run.side_effect = [
            # checkpoint
            MagicMock(returncode=0, stdout="true\n"),
            MagicMock(returncode=0, stdout=""),
            MagicMock(returncode=0, stdout="hash2\n"),
            # baseline
            MagicMock(returncode=0, stdout="100 passed in 1s\n", stderr=""),
            # post (failure)
            MagicMock(returncode=1, stdout="99 passed, 1 failed in 1s\n", stderr=""),
            # revert
            MagicMock(returncode=0),
        ]
        r2 = gate.execute_with_gate(lambda: None, "change 2")
        assert r2.allowed is False
        assert r2.reverted is True

        # History should have both
        assert len(gate.get_gate_history()) == 2


# ---------------------------------------------------------------------------
# TestGate — no git repo
# ---------------------------------------------------------------------------

class TestNoGitRepo:
    """Tests for TestGate when no git repo is available."""

    @patch("modules.omen.test_gate.subprocess.run")
    def test_no_git_repo_raises_on_init(self, mock_run):
        """TestGate without project_root should raise if git root detection fails."""
        mock_run.side_effect = [
            MagicMock(returncode=128, stdout="", stderr="not a git repo"),
        ]
        with pytest.raises(RuntimeError, match="requires a git repository"):
            TestGate()

    def test_explicit_project_root_no_detect(self):
        """Providing project_root should skip git detection."""
        gate = TestGate(project_root="/tmp/fake")
        assert gate._project_root.name == "fake"


# ---------------------------------------------------------------------------
# TestGate — parse edge cases
# ---------------------------------------------------------------------------

class TestParseEdgeCases:
    """Edge cases for pytest output parsing."""

    @patch("modules.omen.test_gate.subprocess.run")
    def test_no_summary_line(self, mock_run):
        """No pytest summary → all zeros, success=False."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()
        r = gate._parse_pytest_output("some random output", 1.0)
        assert r.passed == 0
        assert r.total == 0
        assert r.success is False

    @patch("modules.omen.test_gate.subprocess.run")
    def test_output_truncation(self, mock_run):
        """Long output should be truncated to 500 chars."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/project\n"),
        ]
        gate = TestGate()
        long_output = "x" * 1000 + "\n10 passed in 1s"
        r = gate._parse_pytest_output(long_output, 1.0)
        assert len(r.output) == 500
