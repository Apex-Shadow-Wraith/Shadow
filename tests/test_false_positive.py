"""Tests for Cerberus false positive tracking and calibration stats."""

import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from modules.cerberus.cerberus import Cerberus


@pytest.fixture
def cerberus_with_db(tmp_path):
    """Create a Cerberus instance with a temporary SQLite database."""
    db_path = tmp_path / "test_audit.db"
    limits_file = tmp_path / "cerberus_limits.yaml"
    limits_file.write_text(
        "hard_limits: {}\nautonomous_tools: []\napproval_required_tools: []\nhooks: {}\n"
    )
    cerberus = Cerberus({
        "db_path": str(db_path),
        "limits_file": str(limits_file),
    })
    return cerberus, db_path


def _insert_check(db_path, category, action="safety_check", days_ago=0):
    """Helper to insert a check row into the audit log."""
    ts = (datetime.now() - timedelta(days=days_ago)).isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cerberus_audit_log (timestamp, action, type, category) "
        "VALUES (?, ?, ?, ?)",
        (ts, action, action, category),
    )
    conn.commit()
    conn.close()


class TestLogFalsePositive:
    """Tests for log_false_positive method."""

    def test_log_false_positive_in_db(self, cerberus_with_db):
        """Log a false positive and verify it's stored in the database."""
        cerberus, db_path = cerberus_with_db
        result = cerberus.log_false_positive("chk_001", "shell_metacharacters", "pipe in grep")

        assert result["logged"] is True
        assert result["check_id"] == "chk_001"
        assert result["category"] == "shell_metacharacters"
        assert "timestamp" in result

        # Verify in DB
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM cerberus_audit_log WHERE action = 'false_positive'").fetchall()
        conn.close()
        assert len(rows) == 1

    def test_empty_check_id_fails(self, cerberus_with_db):
        """Empty check_id raises ValueError."""
        cerberus, _ = cerberus_with_db
        with pytest.raises(ValueError, match="check_id is required"):
            cerberus.log_false_positive("", "some_category")

    def test_empty_category_fails(self, cerberus_with_db):
        """Empty category raises ValueError."""
        cerberus, _ = cerberus_with_db
        with pytest.raises(ValueError, match="category is required"):
            cerberus.log_false_positive("chk_001", "")

    def test_details_json_stored(self, cerberus_with_db):
        """Verify check_id, category, and notes are stored in details JSON."""
        cerberus, db_path = cerberus_with_db
        cerberus.log_false_positive("chk_042", "pii_detection", "name wasn't PII")

        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT details FROM cerberus_audit_log WHERE action = 'false_positive'"
        ).fetchone()
        conn.close()

        details = json.loads(row[0])
        assert details["check_id"] == "chk_042"
        assert details["category"] == "pii_detection"
        assert details["notes"] == "name wasn't PII"

    def test_false_positive_counter_increments(self, cerberus_with_db):
        """Internal counter increments with each false positive logged."""
        cerberus, _ = cerberus_with_db
        assert cerberus._false_positive_count == 0
        cerberus.log_false_positive("chk_1", "cat_a")
        assert cerberus._false_positive_count == 1
        cerberus.log_false_positive("chk_2", "cat_b")
        assert cerberus._false_positive_count == 2


class TestCalibrationStats:
    """Tests for get_calibration_stats method."""

    def test_no_data_returns_zeros(self, cerberus_with_db):
        """Empty audit log returns zero stats."""
        cerberus, _ = cerberus_with_db
        stats = cerberus.get_calibration_stats()

        assert stats["overall_fp_rate"] == 0.0
        assert stats["total_checks"] == 0
        assert stats["total_false_positives"] == 0
        assert stats["categories"] == {}
        assert stats["needs_calibration"] == []

    def test_calculates_fp_rate(self, cerberus_with_db):
        """Correctly calculates false positive rate."""
        cerberus, db_path = cerberus_with_db

        # 4 safety checks + 1 false positive in same category = 5 total, 1 FP
        for _ in range(4):
            _insert_check(db_path, "shell_metacharacters", action="safety_check")
        cerberus.log_false_positive("chk_1", "shell_metacharacters")

        stats = cerberus.get_calibration_stats()
        assert stats["total_checks"] == 5
        assert stats["total_false_positives"] == 1
        assert stats["overall_fp_rate"] == 0.2

    def test_high_fp_rate_triggers_calibration(self, cerberus_with_db):
        """Categories with fp_rate > 0.15 flagged for calibration."""
        cerberus, db_path = cerberus_with_db

        # 2 checks + 1 false positive = 3 total, 33% FP rate
        _insert_check(db_path, "pii_detection", action="safety_check")
        _insert_check(db_path, "pii_detection", action="denial")
        cerberus.log_false_positive("chk_1", "pii_detection")

        stats = cerberus.get_calibration_stats()
        assert "pii_detection" in stats["needs_calibration"]

    def test_low_fp_rate_no_calibration(self, cerberus_with_db):
        """Categories with low fp_rate not flagged."""
        cerberus, db_path = cerberus_with_db

        # 9 checks + 1 FP = 10 total, 10% rate (below 15% threshold)
        for _ in range(9):
            _insert_check(db_path, "shell_metacharacters", action="safety_check")
        cerberus.log_false_positive("chk_1", "shell_metacharacters")

        stats = cerberus.get_calibration_stats()
        assert stats["needs_calibration"] == []

    def test_category_breakdown_accurate(self, cerberus_with_db):
        """Per-category breakdown is correct."""
        cerberus, db_path = cerberus_with_db

        _insert_check(db_path, "cat_a", action="safety_check")
        _insert_check(db_path, "cat_a", action="safety_check")
        cerberus.log_false_positive("chk_1", "cat_a")

        _insert_check(db_path, "cat_b", action="denial")
        _insert_check(db_path, "cat_b", action="denial")
        _insert_check(db_path, "cat_b", action="denial")

        stats = cerberus.get_calibration_stats()
        assert stats["categories"]["cat_a"]["total_checks"] == 3
        assert stats["categories"]["cat_a"]["false_positives"] == 1
        assert stats["categories"]["cat_b"]["total_checks"] == 3
        assert stats["categories"]["cat_b"]["false_positives"] == 0

    def test_multiple_categories_independent(self, cerberus_with_db):
        """Multiple categories tracked independently."""
        cerberus, db_path = cerberus_with_db

        cerberus.log_false_positive("chk_1", "cat_a")
        cerberus.log_false_positive("chk_2", "cat_b")
        cerberus.log_false_positive("chk_3", "cat_b")

        stats = cerberus.get_calibration_stats()
        assert stats["categories"]["cat_a"]["false_positives"] == 1
        assert stats["categories"]["cat_b"]["false_positives"] == 2

    def test_date_filtering(self, cerberus_with_db):
        """Only includes entries within the specified day range."""
        cerberus, db_path = cerberus_with_db

        # Recent entry
        _insert_check(db_path, "cat_a", action="safety_check", days_ago=0)
        cerberus.log_false_positive("chk_1", "cat_a")

        # Old entry (45 days ago — outside default 30-day window)
        _insert_check(db_path, "cat_a", action="safety_check", days_ago=45)

        stats = cerberus.get_calibration_stats(days=30)
        # Should only see the 2 recent entries (1 safety_check + 1 false_positive)
        assert stats["total_checks"] == 2

    def test_no_db_path_returns_zeros(self, tmp_path):
        """Cerberus without db_path returns empty calibration stats."""
        limits_file = tmp_path / "cerberus_limits.yaml"
        limits_file.write_text(
            "hard_limits: {}\nautonomous_tools: []\napproval_required_tools: []\nhooks: {}\n"
        )
        cerberus = Cerberus({"limits_file": str(limits_file)})
        stats = cerberus.get_calibration_stats()
        assert stats["overall_fp_rate"] == 0.0
        assert stats["total_checks"] == 0


class TestToolExecution:
    """Tests for tool execution via execute() method."""

    @pytest.mark.asyncio
    async def test_false_positive_log_via_execute(self, cerberus_with_db):
        """false_positive_log tool works through execute()."""
        cerberus, db_path = cerberus_with_db
        limits_file = cerberus._config.get("limits_file")
        await cerberus.initialize()

        result = await cerberus.execute("false_positive_log", {
            "check_id": "chk_exec_1",
            "category": "test_cat",
            "notes": "testing via execute",
        })

        assert result.success is True
        assert result.content["logged"] is True
        assert result.content["check_id"] == "chk_exec_1"

    @pytest.mark.asyncio
    async def test_calibration_stats_via_execute(self, cerberus_with_db):
        """calibration_stats tool works through execute()."""
        cerberus, db_path = cerberus_with_db
        await cerberus.initialize()

        result = await cerberus.execute("calibration_stats", {"days": 7})

        assert result.success is True
        assert "overall_fp_rate" in result.content
        assert "categories" in result.content
        assert "needs_calibration" in result.content

    @pytest.mark.asyncio
    async def test_false_positive_log_empty_check_id_via_execute(self, cerberus_with_db):
        """false_positive_log tool fails with empty check_id through execute()."""
        cerberus, _ = cerberus_with_db
        await cerberus.initialize()

        result = await cerberus.execute("false_positive_log", {
            "check_id": "",
            "category": "test",
        })

        assert result.success is False
        assert "check_id" in result.error
