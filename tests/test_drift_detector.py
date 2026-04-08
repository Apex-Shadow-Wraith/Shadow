"""Tests for Module Specialization Drift Detection."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from modules.shadow.drift_detector import DriftDetector, MODULE_ROLES, GENERALIST_THRESHOLD


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_drift.db")


@pytest.fixture
def detector(tmp_db):
    """Provide a fresh DriftDetector instance."""
    return DriftDetector(db_path=tmp_db)


# --- DB Initialization ---

class TestInit:
    def test_db_created_on_init(self, tmp_db):
        """SQLite DB is created on init."""
        det = DriftDetector(db_path=tmp_db)
        assert Path(tmp_db).exists()

    def test_tables_exist(self, tmp_db):
        """Required tables exist after init."""
        det = DriftDetector(db_path=tmp_db)
        with sqlite3.connect(tmp_db) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
        assert "routing_logs" in table_names

    def test_custom_config(self, tmp_db):
        """Config dict is stored."""
        det = DriftDetector(db_path=tmp_db, config={"threshold": 10})
        assert det.config["threshold"] == 10


# --- Logging ---

class TestLogRouting:
    def test_log_returns_id(self, detector):
        """log_routing returns a log_id string."""
        log_id = detector.log_routing("code", "omen")
        assert isinstance(log_id, str)
        assert len(log_id) > 0

    def test_logs_accumulate(self, detector):
        """Multiple logs are stored."""
        detector.log_routing("code", "omen")
        detector.log_routing("math", "cipher")
        detector.log_routing("ethics", "cerberus")
        with sqlite3.connect(str(detector.db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM routing_logs").fetchone()[0]
        assert count == 3

    def test_log_stores_description(self, detector):
        """Task description is persisted."""
        log_id = detector.log_routing("code", "omen", "Fix the login bug")
        with sqlite3.connect(str(detector.db_path)) as conn:
            desc = conn.execute(
                "SELECT task_description FROM routing_logs WHERE log_id = ?",
                (log_id,),
            ).fetchone()[0]
        assert desc == "Fix the login bug"

    def test_log_marks_violation(self, detector):
        """Violations are flagged at log time."""
        log_id = detector.log_routing("math", "omen")  # math → omen is wrong
        with sqlite3.connect(str(detector.db_path)) as conn:
            row = conn.execute(
                "SELECT is_violation, violation_reason FROM routing_logs WHERE log_id = ?",
                (log_id,),
            ).fetchone()
        assert row[0] == 1
        assert "math" in row[1].lower()

    def test_log_correct_routing_no_violation(self, detector):
        """Correct routing is not flagged."""
        log_id = detector.log_routing("code", "omen")
        with sqlite3.connect(str(detector.db_path)) as conn:
            row = conn.execute(
                "SELECT is_violation FROM routing_logs WHERE log_id = ?",
                (log_id,),
            ).fetchone()
        assert row[0] == 0


# --- Real-time Detection ---

class TestDetectViolations:
    def test_wrong_module_returns_violation(self, detector):
        """Math task to Omen = violation."""
        result = detector.detect_violations("math", "omen")
        assert result is not None
        assert result["task_type"] == "math"
        assert result["routed_to"] == "omen"
        assert "cipher" in [m for m in result["suggested_modules"]]

    def test_correct_module_returns_none(self, detector):
        """Code task to Omen = correct, returns None."""
        result = detector.detect_violations("code", "omen")
        assert result is None

    def test_unknown_module_returns_none(self, detector):
        """Unknown module is not flagged."""
        result = detector.detect_violations("code", "unknown_module")
        assert result is None

    def test_unknown_task_type(self, detector):
        """Unknown task type to known module is flagged (not in should_handle)."""
        result = detector.detect_violations("quantum_physics", "wraith")
        assert result is not None
        assert result["task_type"] == "quantum_physics"

    def test_violation_includes_suggestions(self, detector):
        """Violation includes suggested correct modules."""
        result = detector.detect_violations("ethics", "omen")
        assert result is not None
        assert "cerberus" in result["suggested_modules"]


# --- Analysis ---

class TestAnalyzeDrift:
    def test_empty_logs_zero_drift(self, detector):
        """Empty logs produce 0.0 drift score."""
        analysis = detector.analyze_drift()
        assert analysis["drift_score"] == 0.0
        assert analysis["violations"] == []
        assert analysis["generalists"] == []
        assert analysis["underused"] == []

    def test_violation_detected(self, detector):
        """Math task → Omen is a violation."""
        detector.log_routing("math", "omen", "Calculate profit margin")
        analysis = detector.analyze_drift()
        assert len(analysis["violations"]) == 1
        assert analysis["violations"][0]["task_type"] == "math"
        assert analysis["drift_score"] > 0.0

    def test_correct_routing_no_violation(self, detector):
        """Code task → Omen is correct."""
        detector.log_routing("code", "omen")
        analysis = detector.analyze_drift()
        assert len(analysis["violations"]) == 0
        assert analysis["drift_score"] == 0.0

    def test_identifies_generalist_modules(self, detector):
        """Module handling 5+ task types flagged as generalist."""
        for task in ["code", "math", "ethics", "writing", "web_search", "alerts"]:
            detector.log_routing(task, "shadow")
        analysis = detector.analyze_drift()
        generalist_modules = [g["module"] for g in analysis["generalists"]]
        assert "shadow" in generalist_modules

    def test_identifies_underused_modules(self, detector):
        """Modules receiving very few tasks are flagged."""
        # Give omen 50 tasks, everything else gets nothing
        for _ in range(50):
            detector.log_routing("code", "omen")
        analysis = detector.analyze_drift()
        underused_modules = [u["module"] for u in analysis["underused"]]
        # Many modules should be underused since only omen got tasks
        assert len(underused_modules) > 5

    def test_drift_score_reflects_violations(self, detector):
        """drift_score increases with more violations."""
        # 3 correct, 3 violations
        detector.log_routing("code", "omen")
        detector.log_routing("math", "cipher")
        detector.log_routing("ethics", "cerberus")
        detector.log_routing("math", "omen")       # violation
        detector.log_routing("ethics", "omen")      # violation
        detector.log_routing("web_search", "omen")  # violation
        analysis = detector.analyze_drift()
        assert analysis["drift_score"] == 0.5

    def test_examples_limited(self, detector):
        """Examples list is capped at 5."""
        for _ in range(10):
            detector.log_routing("math", "omen")
        analysis = detector.analyze_drift()
        assert len(analysis["examples"]) <= 5


# --- Module Profiles ---

class TestModuleProfile:
    def test_empty_profile(self, detector):
        """Module with no tasks has clean profile."""
        profile = detector.get_module_profile("cipher")
        assert profile["module"] == "cipher"
        assert profile["designed_role"] == "math_logic"
        assert profile["actual_task_types"] == []
        assert profile["on_role_pct"] == 1.0
        assert profile["off_role_tasks"] == []

    def test_on_role_percentage(self, detector):
        """on_role_pct is calculated correctly."""
        detector.log_routing("code", "omen")
        detector.log_routing("code", "omen")
        detector.log_routing("debugging", "omen")
        detector.log_routing("math", "omen")  # off-role
        profile = detector.get_module_profile("omen")
        assert profile["on_role_pct"] == 0.75  # 3 of 4 are on-role
        assert "math" in profile["off_role_tasks"]

    def test_actual_task_types(self, detector):
        """Profile shows all task types handled."""
        detector.log_routing("code", "omen")
        detector.log_routing("debugging", "omen")
        profile = detector.get_module_profile("omen")
        assert "code" in profile["actual_task_types"]
        assert "debugging" in profile["actual_task_types"]

    def test_unknown_module_profile(self, detector):
        """Unknown module gets 'unknown' role."""
        detector.log_routing("something", "new_module")
        profile = detector.get_module_profile("new_module")
        assert profile["designed_role"] == "unknown"


# --- Reports ---

class TestCorrectionReport:
    def test_clean_report(self, detector):
        """Report with no violations says so."""
        report = detector.generate_correction_report()
        assert "No issues detected" in report or "0.0" in report

    def test_report_mentions_modules(self, detector):
        """Report names specific modules with violations."""
        detector.log_routing("math", "omen")
        detector.log_routing("math", "omen")
        report = detector.generate_correction_report()
        assert "Omen" in report
        assert "math" in report.lower()
        assert "Cipher" in report

    def test_report_mentions_underused(self, detector):
        """Report flags underused modules."""
        for _ in range(30):
            detector.log_routing("code", "omen")
        report = detector.generate_correction_report()
        assert "Underused" in report


class TestDriftStats:
    def test_stats_structure(self, detector):
        """get_drift_stats returns expected keys."""
        stats = detector.get_drift_stats()
        assert "overall_drift_score" in stats
        assert "violations_this_week" in stats
        assert "trend" in stats

    def test_stats_with_no_data(self, detector):
        """Empty stats are valid."""
        stats = detector.get_drift_stats()
        assert stats["overall_drift_score"] == 0.0
        assert stats["violations_this_week"] == 0
        assert stats["trend"] == "stable"

    def test_stats_trend_stable(self, detector):
        """Equal violations = stable trend."""
        detector.log_routing("code", "omen")
        stats = detector.get_drift_stats()
        assert stats["trend"] == "stable"


# --- Edge Cases ---

class TestEdgeCases:
    def test_all_module_roles_defined(self, detector):
        """All 13 modules have role definitions."""
        assert len(MODULE_ROLES) == 13
        for mod in ["shadow", "wraith", "grimoire", "reaper", "cerberus",
                     "apex", "harbinger", "cipher", "omen", "nova",
                     "sentinel", "void", "morpheus"]:
            assert mod in MODULE_ROLES

    def test_generalist_threshold_value(self):
        """GENERALIST_THRESHOLD is 5."""
        assert GENERALIST_THRESHOLD == 5

    def test_concurrent_db_access(self, tmp_db):
        """Two detectors can share a DB path."""
        d1 = DriftDetector(db_path=tmp_db)
        d2 = DriftDetector(db_path=tmp_db)
        d1.log_routing("code", "omen")
        d2.log_routing("math", "cipher")
        analysis = d1.analyze_drift()
        # Both logs visible
        with sqlite3.connect(tmp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM routing_logs").fetchone()[0]
        assert count == 2
