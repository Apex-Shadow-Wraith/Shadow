"""
Tests for SelfImprovementEngine — Morpheus × Omen RSI Bridge
==============================================================
Covers: static analysis, proposal generation, approval/rejection,
statistics, rejection patterns, safety invariants, and Morpheus
tool integration.
"""

from __future__ import annotations

import os
import textwrap
import time
from pathlib import Path

import pytest
import pytest_asyncio

from modules.morpheus.self_improvement import SelfImprovementEngine

# Path to the deliberate-issues fixture
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_module.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def engine(tmp_path):
    """Create a fresh SelfImprovementEngine with an isolated DB."""
    db = tmp_path / "test_self_improvement.db"
    eng = SelfImprovementEngine(db_path=db)
    yield eng
    eng.close()


@pytest.fixture
def clean_file(tmp_path):
    """A small, clean Python file with no issues."""
    f = tmp_path / "clean.py"
    f.write_text(textwrap.dedent('''\
        """Clean module with no issues."""


        def add(a: int, b: int) -> int:
            """Return the sum of a and b."""
            return a + b


        def multiply(x: float, y: float) -> float:
            """Return the product of x and y."""
            return x * y
    '''), encoding="utf-8")
    return f


@pytest.fixture
def empty_file(tmp_path):
    """An empty Python file."""
    f = tmp_path / "empty.py"
    f.write_text("", encoding="utf-8")
    return f


@pytest.fixture
def syntax_error_file(tmp_path):
    """A Python file with a syntax error."""
    f = tmp_path / "bad.py"
    f.write_text("def broken(\n    pass\n", encoding="utf-8")
    return f


def _insert_proposal(engine, **overrides):
    """Insert a proposal directly for test setup."""
    defaults = {
        "target_module": "wraith",
        "target_file": "modules/wraith/wraith.py",
        "hypothesis": "Test hypothesis",
        "change_type": "refactor",
    }
    defaults.update(overrides)
    proposals = [engine._make_proposal(
        module_name=defaults["target_module"],
        source_path=defaults["target_file"],
        hypothesis=defaults["hypothesis"],
        change_type=defaults["change_type"],
    )]
    engine._persist_proposal(proposals[0])
    return proposals[0]


# ===========================================================================
# TestAnalyzeModule
# ===========================================================================

class TestAnalyzeModule:
    """Tests for analyze_module — pure AST/regex static analysis."""

    def test_detects_long_functions(self, engine):
        result = engine.analyze_module("sample", str(FIXTURE_PATH))
        long_fns = result["long_functions"]
        names = [f["name"] for f in long_fns]
        assert "very_long_function" in names

    def test_detects_bare_excepts(self, engine):
        result = engine.analyze_module("sample", str(FIXTURE_PATH))
        assert len(result["bare_excepts"]) >= 2

    def test_detects_missing_docstrings(self, engine):
        result = engine.analyze_module("sample", str(FIXTURE_PATH))
        names = [d["name"] for d in result["missing_docstrings"]]
        assert "very_long_function" in names
        assert "another_undocumented" in names

    def test_detects_todo_comments(self, engine):
        result = engine.analyze_module("sample", str(FIXTURE_PATH))
        types = [t["type"] for t in result["todo_comments"]]
        assert "TODO" in types
        assert "FIXME" in types

    def test_counts_correctly(self, engine):
        result = engine.analyze_module("sample", str(FIXTURE_PATH))
        assert result["line_count"] > 0
        assert result["function_count"] >= 4  # very_long, another_undocumented, clean, method_without_docs

    def test_handles_empty_file(self, engine, empty_file):
        result = engine.analyze_module("empty", str(empty_file))
        assert result["line_count"] == 0
        assert result["function_count"] == 0
        assert result["todo_comments"] == []
        assert result["bare_excepts"] == []
        assert result["long_functions"] == []

    def test_handles_syntax_error(self, engine, syntax_error_file):
        result = engine.analyze_module("bad", str(syntax_error_file))
        assert "parse_error" in result
        # Regex-based checks should still work
        assert "line_count" in result

    def test_file_not_found(self, engine):
        result = engine.analyze_module("ghost", "/nonexistent/path.py")
        assert "error" in result

    def test_clean_file_no_issues(self, engine, clean_file):
        result = engine.analyze_module("clean", str(clean_file))
        assert result["long_functions"] == []
        assert result["bare_excepts"] == []
        assert result["missing_docstrings"] == []
        assert result["todo_comments"] == []

    def test_detects_undocumented_class(self, engine):
        result = engine.analyze_module("sample", str(FIXTURE_PATH))
        names = [d["name"] for d in result["missing_docstrings"]]
        assert "UndocumentedClass" in names

    def test_is_read_only(self, engine):
        """analyze_module must NOT modify the source file."""
        content_before = FIXTURE_PATH.read_text(encoding="utf-8")
        engine.analyze_module("sample", str(FIXTURE_PATH))
        content_after = FIXTURE_PATH.read_text(encoding="utf-8")
        assert content_before == content_after


# ===========================================================================
# TestGenerateProposals
# ===========================================================================

class TestGenerateProposals:
    """Tests for generate_proposals — rule-based proposal generation."""

    def test_produces_proposals_for_fixture(self, engine):
        proposals = engine.generate_proposals("sample", str(FIXTURE_PATH))
        assert len(proposals) > 0

    def test_respects_max_proposals(self, engine):
        proposals = engine.generate_proposals(
            "sample", str(FIXTURE_PATH), max_proposals=1,
        )
        assert len(proposals) == 1

    def test_each_has_hypothesis(self, engine):
        proposals = engine.generate_proposals("sample", str(FIXTURE_PATH))
        for p in proposals:
            assert p["hypothesis"]
            assert len(p["hypothesis"]) > 10

    def test_correct_change_types(self, engine):
        proposals = engine.generate_proposals(
            "sample", str(FIXTURE_PATH), max_proposals=10,
        )
        for p in proposals:
            assert p["change_type"] in {
                "optimize", "refactor", "add_feature", "fix_pattern", "add_test",
            }

    def test_no_proposals_for_clean_file(self, engine, clean_file):
        proposals = engine.generate_proposals("clean", str(clean_file))
        assert proposals == []

    def test_proposals_persisted_to_db(self, engine):
        proposals = engine.generate_proposals("sample", str(FIXTURE_PATH))
        stored = engine.get_proposals()
        assert len(stored) == len(proposals)
        stored_ids = {p["id"] for p in stored}
        for p in proposals:
            assert p["id"] in stored_ids

    def test_no_proposals_for_missing_file(self, engine):
        proposals = engine.generate_proposals("ghost", "/no/such/file.py")
        assert proposals == []

    def test_no_proposals_for_syntax_error(self, engine, syntax_error_file):
        proposals = engine.generate_proposals("bad", str(syntax_error_file))
        assert proposals == []

    def test_rejection_pattern_suppression(self, engine):
        """Proposals whose (change_type, module) were rejected 2+ times are suppressed."""
        # Insert 2 rejected refactor proposals for 'sample'
        for _ in range(2):
            p = _insert_proposal(
                engine,
                target_module="sample",
                change_type="refactor",
            )
            engine.reject_proposal(p["id"], "not wanted")

        # Also reject 2 fix_pattern proposals for 'sample'
        for _ in range(2):
            p = _insert_proposal(
                engine,
                target_module="sample",
                change_type="fix_pattern",
            )
            engine.reject_proposal(p["id"], "not needed")

        # Also reject 2 add_feature proposals for 'sample'
        for _ in range(2):
            p = _insert_proposal(
                engine,
                target_module="sample",
                change_type="add_feature",
            )
            engine.reject_proposal(p["id"], "nope")

        # Now generate — should be suppressed
        proposals = engine.generate_proposals(
            "sample", str(FIXTURE_PATH), max_proposals=10,
        )
        suppressed_types = {"refactor", "fix_pattern", "add_feature"}
        for p in proposals:
            assert p["change_type"] not in suppressed_types


# ===========================================================================
# TestTestProposal
# ===========================================================================

class TestTestProposal:
    """Tests for test_proposal — Phase 1 stub."""

    def test_returns_pending_status(self, engine):
        p = _insert_proposal(engine)
        result = engine.test_proposal(p["id"], "/tmp/sandbox")
        assert result["status"] == "pending"
        assert "Phase 2" in result["message"]

    def test_updates_db_status(self, engine):
        p = _insert_proposal(engine)
        engine.test_proposal(p["id"], "/tmp/sandbox")
        stored = engine.get_proposals()
        match = [x for x in stored if x["id"] == p["id"]]
        assert match[0]["status"] == "testing"

    def test_not_found(self, engine):
        result = engine.test_proposal("nonexistent-id", "/tmp/sandbox")
        assert result["status"] == "error"


# ===========================================================================
# TestApproveReject
# ===========================================================================

class TestApproveReject:
    """Tests for approve_proposal and reject_proposal."""

    def test_approve_works(self, engine):
        p = _insert_proposal(engine)
        result = engine.approve_proposal(p["id"])
        assert result["success"] is True
        assert result["status"] == "approved"

    def test_reject_works(self, engine):
        p = _insert_proposal(engine)
        result = engine.reject_proposal(p["id"], "Not useful")
        assert result["success"] is True
        assert result["status"] == "rejected"

    def test_reject_stores_reason(self, engine):
        p = _insert_proposal(engine)
        engine.reject_proposal(p["id"], "Too risky")
        stored = engine.get_proposals()
        match = [x for x in stored if x["id"] == p["id"]]
        assert match[0]["rejection_reason"] == "Too risky"

    def test_cannot_approve_rejected(self, engine):
        p = _insert_proposal(engine)
        engine.reject_proposal(p["id"], "Bad idea")
        result = engine.approve_proposal(p["id"])
        assert result["success"] is False
        assert "rejected" in result["error"].lower()

    def test_cannot_reject_approved(self, engine):
        p = _insert_proposal(engine)
        engine.approve_proposal(p["id"])
        result = engine.reject_proposal(p["id"], "Changed my mind")
        assert result["success"] is False
        assert "approved" in result["error"].lower()

    def test_resolved_at_set_on_approve(self, engine):
        p = _insert_proposal(engine)
        before = time.time()
        engine.approve_proposal(p["id"])
        stored = engine.get_proposals()
        match = [x for x in stored if x["id"] == p["id"]]
        assert match[0]["resolved_at"] is not None
        assert match[0]["resolved_at"] >= before

    def test_resolved_at_set_on_reject(self, engine):
        p = _insert_proposal(engine)
        before = time.time()
        engine.reject_proposal(p["id"], "nope")
        stored = engine.get_proposals()
        match = [x for x in stored if x["id"] == p["id"]]
        assert match[0]["resolved_at"] is not None
        assert match[0]["resolved_at"] >= before

    def test_approve_not_found(self, engine):
        result = engine.approve_proposal("nonexistent")
        assert result["success"] is False

    def test_reject_not_found(self, engine):
        result = engine.reject_proposal("nonexistent", "reason")
        assert result["success"] is False


# ===========================================================================
# TestGetProposals
# ===========================================================================

class TestGetProposals:
    """Tests for get_proposals filtering."""

    def test_returns_all_when_no_filter(self, engine):
        _insert_proposal(engine, target_module="a")
        _insert_proposal(engine, target_module="b")
        assert len(engine.get_proposals()) == 2

    def test_filter_by_status(self, engine):
        p1 = _insert_proposal(engine)
        _insert_proposal(engine)
        engine.approve_proposal(p1["id"])
        approved = engine.get_proposals(status="approved")
        assert len(approved) == 1
        assert approved[0]["id"] == p1["id"]

    def test_filter_by_module(self, engine):
        _insert_proposal(engine, target_module="wraith")
        _insert_proposal(engine, target_module="cipher")
        wraith_only = engine.get_proposals(module="wraith")
        assert len(wraith_only) == 1
        assert wraith_only[0]["target_module"] == "wraith"

    def test_empty_results(self, engine):
        assert engine.get_proposals() == []
        assert engine.get_proposals(status="approved") == []


# ===========================================================================
# TestStats
# ===========================================================================

class TestStats:
    """Tests for get_improvement_stats."""

    def test_zero_proposals(self, engine):
        stats = engine.get_improvement_stats()
        assert stats["total"] == 0
        assert stats["approval_rate"] == 0.0
        assert stats["by_status"] == {}

    def test_counts_correct(self, engine):
        p1 = _insert_proposal(engine, change_type="refactor")
        p2 = _insert_proposal(engine, change_type="fix_pattern")
        _insert_proposal(engine, change_type="refactor")
        engine.approve_proposal(p1["id"])
        engine.reject_proposal(p2["id"], "no")

        stats = engine.get_improvement_stats()
        assert stats["total"] == 3
        assert stats["by_status"]["approved"] == 1
        assert stats["by_status"]["rejected"] == 1
        assert stats["by_status"]["proposed"] == 1

    def test_approval_rate(self, engine):
        p1 = _insert_proposal(engine)
        p2 = _insert_proposal(engine)
        p3 = _insert_proposal(engine)
        engine.approve_proposal(p1["id"])
        engine.approve_proposal(p2["id"])
        engine.reject_proposal(p3["id"], "no")

        stats = engine.get_improvement_stats()
        assert abs(stats["approval_rate"] - 2 / 3) < 0.01

    def test_groups_by_change_type(self, engine):
        _insert_proposal(engine, change_type="refactor")
        _insert_proposal(engine, change_type="refactor")
        _insert_proposal(engine, change_type="fix_pattern")

        stats = engine.get_improvement_stats()
        assert stats["by_change_type"]["refactor"] == 2
        assert stats["by_change_type"]["fix_pattern"] == 1

    def test_most_improved_modules(self, engine):
        p1 = _insert_proposal(engine, target_module="wraith")
        p2 = _insert_proposal(engine, target_module="wraith")
        p3 = _insert_proposal(engine, target_module="cipher")
        engine.approve_proposal(p1["id"])
        engine.approve_proposal(p2["id"])
        engine.approve_proposal(p3["id"])

        stats = engine.get_improvement_stats()
        modules = stats["most_improved_modules"]
        assert modules[0]["module"] == "wraith"
        assert modules[0]["approved_count"] == 2


# ===========================================================================
# TestRejectionPatterns
# ===========================================================================

class TestRejectionPatterns:
    """Tests for get_rejection_patterns."""

    def test_empty_when_no_rejections(self, engine):
        assert engine.get_rejection_patterns() == []

    def test_threshold_of_two(self, engine):
        """Single rejection does not create a pattern."""
        p = _insert_proposal(engine, change_type="refactor", target_module="wraith")
        engine.reject_proposal(p["id"], "no")
        assert engine.get_rejection_patterns() == []

    def test_groups_correctly(self, engine):
        for _ in range(3):
            p = _insert_proposal(
                engine, change_type="fix_pattern", target_module="sentinel",
            )
            engine.reject_proposal(p["id"], "not needed")

        patterns = engine.get_rejection_patterns()
        assert len(patterns) == 1
        assert patterns[0]["change_type"] == "fix_pattern"
        assert patterns[0]["target_module"] == "sentinel"
        assert patterns[0]["count"] == 3

    def test_multiple_patterns(self, engine):
        for _ in range(2):
            p = _insert_proposal(engine, change_type="refactor", target_module="a")
            engine.reject_proposal(p["id"], "no")
        for _ in range(2):
            p = _insert_proposal(engine, change_type="fix_pattern", target_module="b")
            engine.reject_proposal(p["id"], "no")

        patterns = engine.get_rejection_patterns()
        assert len(patterns) == 2


# ===========================================================================
# TestSafety
# ===========================================================================

class TestSafety:
    """Safety invariant tests."""

    def test_analyze_is_read_only(self, engine):
        """analyze_module must not modify source files."""
        content_before = FIXTURE_PATH.read_text(encoding="utf-8")
        engine.analyze_module("sample", str(FIXTURE_PATH))
        content_after = FIXTURE_PATH.read_text(encoding="utf-8")
        assert content_before == content_after

    def test_approve_not_a_morpheus_tool(self):
        """approve_proposal must NOT be registered as a Morpheus tool."""
        from modules.morpheus.morpheus import Morpheus

        m = Morpheus()
        tool_names = [t["name"] for t in m.get_tools()]
        assert "approve_proposal" not in tool_names
        assert "reject_proposal" not in tool_names

    def test_analysis_tools_are_autonomous(self):
        """self_improve_analyze and self_improve_proposals must be autonomous."""
        from modules.morpheus.morpheus import Morpheus

        m = Morpheus()
        tools = {t["name"]: t for t in m.get_tools()}
        assert tools["self_improve_analyze"]["permission_level"] == "autonomous"
        assert tools["self_improve_proposals"]["permission_level"] == "autonomous"


# ===========================================================================
# TestMorpheusIntegration
# ===========================================================================

class TestMorpheusIntegration:
    """Tests for Morpheus tool registration and execution."""

    def test_tools_registered(self):
        from modules.morpheus.morpheus import Morpheus

        m = Morpheus()
        tool_names = [t["name"] for t in m.get_tools()]
        assert "self_improve_analyze" in tool_names
        assert "self_improve_proposals" in tool_names

    @pytest.mark.asyncio
    async def test_analyze_executes(self, tmp_path):
        from modules.morpheus.morpheus import Morpheus

        m = Morpheus(config={"db_path": str(tmp_path / "morph.db")})
        await m.initialize()
        try:
            result = await m.execute("self_improve_analyze", {
                "module_name": "sample",
                "source_path": str(FIXTURE_PATH),
            })
            assert result.success is True
            assert result.content["proposal_count"] > 0
        finally:
            await m.shutdown()

    @pytest.mark.asyncio
    async def test_proposals_executes(self, tmp_path):
        from modules.morpheus.morpheus import Morpheus

        m = Morpheus(config={"db_path": str(tmp_path / "morph.db")})
        await m.initialize()
        try:
            result = await m.execute("self_improve_proposals", {})
            assert result.success is True
            assert result.content["count"] == 0
        finally:
            await m.shutdown()

    @pytest.mark.asyncio
    async def test_analyze_requires_module_name(self, tmp_path):
        from modules.morpheus.morpheus import Morpheus

        m = Morpheus(config={"db_path": str(tmp_path / "morph.db")})
        await m.initialize()
        try:
            result = await m.execute("self_improve_analyze", {})
            assert result.success is False
            assert "module_name" in result.error.lower()
        finally:
            await m.shutdown()
