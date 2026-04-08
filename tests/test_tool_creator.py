"""
Tests for Autonomous Tool Creation Pipeline
=============================================
Covers pattern detection, tool proposal, validation,
staging, approval/rejection, and edge cases.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from modules.omen.tool_creator import ToolCandidate, ToolCreator


# --- Fixtures ---

@pytest.fixture
def staging_dir(tmp_path: Path) -> Path:
    return tmp_path / "staged_tools"


@pytest.fixture
def creator(staging_dir: Path) -> ToolCreator:
    return ToolCreator(staging_dir=str(staging_dir))


@pytest.fixture
def mock_generate_fn() -> MagicMock:
    fn = MagicMock()
    fn.return_value = {
        "name": "format_date",
        "code": "def format_date(dt):\n    return dt.strftime('%Y-%m-%d')\n",
        "tests": "def test_format_date():\n    assert format_date is not None\n",
        "docstring": "Format a datetime to YYYY-MM-DD string",
        "description": "Date formatting utility",
    }
    return fn


@pytest.fixture
def sample_executions() -> list[dict]:
    """Three similar code executions (same structure)."""
    code = "x = data.get('value', 0)\nresult = x * 2\nprint(result)"
    return [
        {"code": code, "timestamp": 1},
        {"code": code, "timestamp": 2},
        {"code": code, "timestamp": 3},
    ]


@pytest.fixture
def sample_pattern() -> dict:
    return {
        "pattern": "abc123",
        "occurrences": 5,
        "example_code": "def helper(x):\n    return x * 2\n",
    }


# --- Pattern Detection ---

class TestDetectPattern:
    def test_three_similar_executions_detected(self, creator, sample_executions):
        """3 similar executions → pattern detected."""
        patterns = creator.detect_pattern(sample_executions)
        assert len(patterns) == 1
        assert patterns[0]["occurrences"] == 3

    def test_two_similar_below_threshold(self, creator):
        """2 similar executions → no pattern (below default threshold of 3)."""
        code = "x = 1\ny = x + 1"
        executions = [{"code": code}, {"code": code}]
        patterns = creator.detect_pattern(executions)
        assert len(patterns) == 0

    def test_different_code_no_pattern(self, creator):
        """Different code structures → no shared pattern."""
        executions = [
            {"code": "x = 1"},
            {"code": "def foo():\n    pass"},
            {"code": "import os\nos.getcwd()"},
        ]
        patterns = creator.detect_pattern(executions)
        assert len(patterns) == 0

    def test_empty_executions(self, creator):
        """Empty list → empty result."""
        assert creator.detect_pattern([]) == []

    def test_custom_min_occurrences(self, creator, sample_executions):
        """Custom threshold of 4 → 3 occurrences not enough."""
        patterns = creator.detect_pattern(sample_executions, min_occurrences=4)
        assert len(patterns) == 0


# --- Tool Proposal ---

class TestProposeTool:
    def test_propose_with_generate_fn(self, staging_dir, mock_generate_fn, sample_pattern):
        """propose_tool uses generate_fn to create code."""
        creator = ToolCreator(
            generate_fn=mock_generate_fn, staging_dir=str(staging_dir)
        )
        candidate = creator.propose_tool(sample_pattern)
        assert candidate.name == "format_date"
        assert candidate.status == "proposed"
        assert "format_date" in candidate.code
        mock_generate_fn.assert_called_once()

    def test_propose_generates_tests(self, staging_dir, mock_generate_fn, sample_pattern):
        """propose_tool generates tests via generate_fn."""
        creator = ToolCreator(
            generate_fn=mock_generate_fn, staging_dir=str(staging_dir)
        )
        candidate = creator.propose_tool(sample_pattern)
        assert candidate.tests != ""
        assert "test_" in candidate.tests

    def test_propose_without_generate_fn(self, creator, sample_pattern):
        """Fallback: propose_tool wraps code without generate_fn."""
        candidate = creator.propose_tool(sample_pattern)
        assert candidate.status == "proposed"
        assert candidate.name.startswith("auto_tool_")
        assert "def " in candidate.code

    def test_candidate_has_all_fields(self, creator, sample_pattern):
        """ToolCandidate has all required dataclass fields."""
        candidate = creator.propose_tool(sample_pattern)
        assert candidate.candidate_id
        assert candidate.name
        assert candidate.description
        assert candidate.code
        assert candidate.docstring
        assert candidate.detected_pattern == sample_pattern["pattern"]
        assert candidate.occurrence_count == 5
        assert candidate.created_at > 0
        assert candidate.approved_at is None

    def test_propose_increments_stats(self, creator, sample_pattern):
        """Stats updated on proposal."""
        creator.propose_tool(sample_pattern)
        stats = creator.get_creation_stats()
        assert stats["tools_proposed"] == 1


# --- Validation ---

class TestValidateTool:
    def test_cerberus_classifies_risk(self, staging_dir, sample_pattern):
        """Cerberus mock classifies risk level."""
        cerberus = MagicMock()
        cerberus.classify_risk.return_value = "internal"
        creator = ToolCreator(cerberus=cerberus, staging_dir=str(staging_dir))
        candidate = creator.propose_tool(sample_pattern)
        validated = creator.validate_tool(candidate)
        assert validated.risk_classification == "internal"
        cerberus.classify_risk.assert_called_once()

    def test_sandbox_runs_tests(self, staging_dir, sample_pattern):
        """Sandbox mock runs generated tests."""
        sandbox = MagicMock()
        sandbox.run_tests.return_value = {"passed": True}
        creator = ToolCreator(sandbox=sandbox, staging_dir=str(staging_dir))
        candidate = creator.propose_tool(sample_pattern)
        validated = creator.validate_tool(candidate)
        assert validated.sandbox_test_passed is True
        sandbox.run_tests.assert_called_once()

    def test_sandbox_pass_stages_tool(self, staging_dir, sample_pattern):
        """Test pass → status 'staged'."""
        sandbox = MagicMock()
        sandbox.run_tests.return_value = {"passed": True}
        creator = ToolCreator(sandbox=sandbox, staging_dir=str(staging_dir))
        candidate = creator.propose_tool(sample_pattern)
        validated = creator.validate_tool(candidate)
        assert validated.status == "staged"

    def test_sandbox_fail_stays_proposed(self, staging_dir, sample_pattern):
        """Test fail → status stays 'proposed'."""
        sandbox = MagicMock()
        sandbox.run_tests.return_value = {"passed": False}
        creator = ToolCreator(sandbox=sandbox, staging_dir=str(staging_dir))
        candidate = creator.propose_tool(sample_pattern)
        validated = creator.validate_tool(candidate)
        assert validated.status == "proposed"
        assert validated.sandbox_test_passed is False


# --- Staging ---

class TestStageTool:
    def test_stage_writes_to_directory(self, creator, staging_dir, sample_pattern):
        """stage_tool writes .py file to staging directory."""
        candidate = creator.propose_tool(sample_pattern)
        cid = creator.stage_tool(candidate)
        tool_file = staging_dir / f"{candidate.name}.py"
        assert tool_file.exists()
        assert cid == candidate.candidate_id

    def test_stage_writes_metadata(self, creator, staging_dir, sample_pattern):
        """stage_tool writes .meta.json alongside tool file."""
        candidate = creator.propose_tool(sample_pattern)
        creator.stage_tool(candidate)
        meta_file = staging_dir / f"{candidate.name}.meta.json"
        assert meta_file.exists()
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        assert meta["candidate_id"] == candidate.candidate_id

    def test_stage_sends_notification(self, staging_dir, sample_pattern):
        """stage_tool sends Telegram notification via notifier."""
        notifier = MagicMock()
        creator = ToolCreator(notifier=notifier, staging_dir=str(staging_dir))
        candidate = creator.propose_tool(sample_pattern)
        creator.stage_tool(candidate)
        notifier.send.assert_called_once()
        msg = notifier.send.call_args[0][0]
        assert candidate.name in msg
        assert candidate.candidate_id in msg

    def test_get_staged_tools(self, creator, sample_pattern):
        """get_staged_tools returns staged candidates."""
        candidate = creator.propose_tool(sample_pattern)
        candidate.status = "staged"
        creator._candidates[candidate.candidate_id] = candidate
        staged = creator.get_staged_tools()
        assert len(staged) == 1
        assert staged[0].candidate_id == candidate.candidate_id


# --- Approval & Rejection ---

class TestApproveReject:
    def test_approve_moves_to_production(self, creator, sample_pattern):
        """approve_tool sets status to 'approved'."""
        candidate = creator.propose_tool(sample_pattern)
        candidate.status = "staged"
        creator._candidates[candidate.candidate_id] = candidate
        result = creator.approve_tool(candidate.candidate_id)
        assert result is True
        assert creator._candidates[candidate.candidate_id].status == "approved"
        assert creator._candidates[candidate.candidate_id].approved_at is not None

    def test_approve_registers_with_cerberus(self, staging_dir, sample_pattern):
        """approve_tool calls cerberus.register_tool."""
        cerberus = MagicMock()
        creator = ToolCreator(cerberus=cerberus, staging_dir=str(staging_dir))
        candidate = creator.propose_tool(sample_pattern)
        candidate.status = "staged"
        creator._candidates[candidate.candidate_id] = candidate
        creator.approve_tool(candidate.candidate_id)
        cerberus.register_tool.assert_called_once()

    def test_reject_marks_rejected_with_reason(self, creator, sample_pattern):
        """reject_tool marks as rejected with reason."""
        candidate = creator.propose_tool(sample_pattern)
        candidate.status = "staged"
        creator._candidates[candidate.candidate_id] = candidate
        result = creator.reject_tool(candidate.candidate_id, reason="Too risky")
        assert result is True
        rejected = creator._candidates[candidate.candidate_id]
        assert rejected.status == "rejected"
        assert rejected.rejection_reason == "Too risky"

    def test_rejected_tools_kept_in_staging(self, creator, staging_dir, sample_pattern):
        """Rejected tools remain in candidates for reference."""
        candidate = creator.propose_tool(sample_pattern)
        creator.stage_tool(candidate)
        creator.reject_tool(candidate.candidate_id, reason="Not needed")
        assert candidate.candidate_id in creator._candidates
        tool_file = staging_dir / f"{candidate.name}.py"
        assert tool_file.exists()


# --- Edge Cases ---

class TestEdgeCases:
    def test_no_cerberus_skips_classification(self, creator, sample_pattern):
        """No cerberus → skip classification, can still stage."""
        candidate = creator.propose_tool(sample_pattern)
        validated = creator.validate_tool(candidate)
        assert validated.risk_classification == "unclassified"
        # Without sandbox, tool goes to staged
        assert validated.status == "staged"

    def test_no_sandbox_skips_testing(self, staging_dir, sample_pattern):
        """No sandbox → skip testing, stage with warning."""
        cerberus = MagicMock()
        cerberus.classify_risk.return_value = "internal"
        creator = ToolCreator(cerberus=cerberus, staging_dir=str(staging_dir))
        candidate = creator.propose_tool(sample_pattern)
        validated = creator.validate_tool(candidate)
        assert validated.sandbox_test_passed is False
        assert validated.status == "staged"

    def test_no_notifier_stages_without_notification(self, creator, staging_dir, sample_pattern):
        """No notifier → tool staged, no crash."""
        candidate = creator.propose_tool(sample_pattern)
        cid = creator.stage_tool(candidate)
        assert cid == candidate.candidate_id
        tool_file = staging_dir / f"{candidate.name}.py"
        assert tool_file.exists()

    def test_staging_dir_created_if_not_exists(self, tmp_path, sample_pattern):
        """staging_dir auto-created."""
        new_dir = tmp_path / "new" / "nested" / "staging"
        creator = ToolCreator(staging_dir=str(new_dir))
        candidate = creator.propose_tool(sample_pattern)
        creator.stage_tool(candidate)
        assert new_dir.exists()

    def test_get_creation_stats_valid(self, creator, sample_pattern):
        """Stats return valid data after operations."""
        candidate = creator.propose_tool(sample_pattern)
        candidate.status = "staged"
        creator._candidates[candidate.candidate_id] = candidate
        creator.approve_tool(candidate.candidate_id)

        candidate2 = creator.propose_tool(sample_pattern)
        candidate2.status = "staged"
        creator._candidates[candidate2.candidate_id] = candidate2
        creator.reject_tool(candidate2.candidate_id, reason="test")

        stats = creator.get_creation_stats()
        assert stats["tools_proposed"] == 2
        assert stats["tools_approved"] == 1
        assert stats["tools_rejected"] == 1
        assert stats["approval_rate"] == 0.5

    def test_approve_nonexistent_returns_false(self, creator):
        """Approve unknown candidate_id → False."""
        assert creator.approve_tool("nonexistent") is False

    def test_reject_nonexistent_returns_false(self, creator):
        """Reject unknown candidate_id → False."""
        assert creator.reject_tool("nonexistent") is False
