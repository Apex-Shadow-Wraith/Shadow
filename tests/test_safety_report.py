"""Tests for DailySafetyReport — Cerberus audit log reporting."""

import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from modules.harbinger.safety_report import AUDIT_TABLE_DDL, DailySafetyReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_entries(db_path: Path, entries: list[dict]) -> None:
    """Insert audit log entries into the test database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(AUDIT_TABLE_DDL)
    for e in entries:
        conn.execute(
            "INSERT INTO cerberus_audit_log "
            "(timestamp, type, tool, module, reason, rule, verdict, "
            " resolved, resolved_at, category, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                e.get("timestamp", "2026-04-05T10:00:00"),
                e.get("type", "allow"),
                e.get("tool"),
                e.get("module"),
                e.get("reason"),
                e.get("rule"),
                e.get("verdict"),
                e.get("resolved", 0),
                e.get("resolved_at"),
                e.get("category"),
                e.get("metadata"),
            ),
        )
    conn.commit()
    conn.close()


TARGET_DATE = date(2026, 4, 5)

# A reusable set of mixed entries covering the target date
MIXED_ENTRIES = [
    {"timestamp": "2026-04-05T08:00:00", "type": "allow", "tool": "web_search",
     "module": "wraith", "verdict": "allow", "category": "search"},
    {"timestamp": "2026-04-05T08:05:00", "type": "allow", "tool": "web_fetch",
     "module": "reaper", "verdict": "allow", "category": "search"},
    {"timestamp": "2026-04-05T09:00:00", "type": "log", "tool": "remember",
     "module": "grimoire", "verdict": "log", "category": "memory"},
    {"timestamp": "2026-04-05T09:30:00", "type": "denial", "tool": "bash_exec",
     "module": "omen", "reason": "shell metacharacter detected",
     "rule": "no_shell_injection", "verdict": "deny", "category": "execution",
     "resolved": 0},
    {"timestamp": "2026-04-05T10:00:00", "type": "denial", "tool": "file_write",
     "module": "omen", "reason": "protected path write attempt",
     "rule": "protected_paths", "verdict": "deny", "category": "filesystem",
     "resolved": 1, "resolved_at": "2026-04-05T10:15:00"},
    {"timestamp": "2026-04-05T11:00:00", "type": "approval_required",
     "tool": "notification_send", "module": "harbinger", "verdict": "approval_required",
     "category": "external"},
    {"timestamp": "2026-04-05T12:00:00", "type": "modify", "tool": "web_search",
     "module": "reaper", "reason": "PII stripped from query",
     "verdict": "modify", "category": "search"},
    {"timestamp": "2026-04-05T14:00:00", "type": "creator_exception",
     "tool": "bash_exec", "module": "wraith", "verdict": "allow",
     "category": "execution"},
    {"timestamp": "2026-04-05T15:00:00", "type": "creator_authorization",
     "tool": "notification_send", "module": "harbinger", "verdict": "allow",
     "category": "external"},
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEnsureTable:
    def test_creates_schema(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        DailySafetyReport._ensure_table(db_path)

        conn = sqlite3.connect(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()

        table_names = [t[0] for t in tables]
        assert "cerberus_audit_log" in table_names


class TestGenerateEmptyDay:
    def test_returns_zeroed_summary(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        report = DailySafetyReport().generate(TARGET_DATE, db_path)

        s = report["summary"]
        assert s["total_actions"] == 0
        assert s["blocked"] == 0
        assert s["approved_autonomous"] == 0
        assert report["blocks"] == []
        assert report["anomalies"] == []
        assert report["false_positive_rate"]["overall"] == 0.0


class TestGenerateCounts:
    def test_counts_by_type(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _insert_entries(db_path, MIXED_ENTRIES)

        report = DailySafetyReport().generate(TARGET_DATE, db_path)
        s = report["summary"]

        assert s["total_actions"] == 9
        assert s["approved_autonomous"] == 2
        assert s["approved_with_logging"] == 1
        assert s["deferred_to_queue"] == 1
        assert s["blocked"] == 2
        assert s["modified"] == 1
        assert s["creator_exceptions"] == 1
        assert s["creator_authorizations"] == 1


class TestBlocksList:
    def test_blocks_populated(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _insert_entries(db_path, MIXED_ENTRIES)

        report = DailySafetyReport().generate(TARGET_DATE, db_path)
        blocks = report["blocks"]

        assert len(blocks) == 2
        assert blocks[0]["action_type"] == "bash_exec"
        assert blocks[0]["requesting_module"] == "omen"
        assert blocks[0]["resolved"] is False
        assert blocks[1]["resolved"] is True


class TestFalsePositiveRate:
    def test_calculation(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _insert_entries(db_path, MIXED_ENTRIES)

        report = DailySafetyReport().generate(TARGET_DATE, db_path)
        fp = report["false_positive_rate"]

        assert fp["total_blocks"] == 2
        assert fp["total_resolved"] == 1
        assert fp["overall"] == 0.5

        # filesystem category: 1 block, 1 resolved = 100% FP rate
        assert fp["by_category"]["filesystem"]["rate"] == 1.0
        # execution category: 1 block, 0 resolved = 0% FP rate
        assert fp["by_category"]["execution"]["rate"] == 0.0


class TestCalibrationAlerts:
    def test_triggered_above_threshold(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _insert_entries(db_path, MIXED_ENTRIES)

        report = DailySafetyReport().generate(TARGET_DATE, db_path)
        alerts = report["calibration_alerts"]

        # filesystem has 100% FP rate — should trigger
        categories = [a["category"] for a in alerts]
        assert "filesystem" in categories

        # execution has 0% FP rate — should NOT trigger
        assert "execution" not in categories


class TestFormatForHarbinger:
    def test_readable_output(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _insert_entries(db_path, MIXED_ENTRIES)

        report = DailySafetyReport().generate(TARGET_DATE, db_path)
        text = DailySafetyReport.format_for_harbinger(report)

        assert isinstance(text, str)
        assert len(text) > 0
        assert "DAILY SAFETY REPORT" in text
        assert "SUMMARY" in text
        assert "BLOCKED ACTIONS" in text
        assert "FALSE POSITIVE RATE" in text
        assert "CALIBRATION ALERTS" in text


class TestSaveReport:
    def test_creates_yaml(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        _insert_entries(db_path, MIXED_ENTRIES)

        report = DailySafetyReport().generate(TARGET_DATE, db_path)
        output_dir = tmp_path / "reports" / "safety"
        filepath = DailySafetyReport.save_report(report, output_dir)

        assert filepath.exists()
        assert filepath.name == "2026-04-05_safety_report.yaml"

        with open(filepath, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        assert loaded["date"] == "2026-04-05"
        assert loaded["summary"]["total_actions"] == 9


class TestDateFiltering:
    def test_only_target_date_included(self, tmp_path: Path):
        db_path = tmp_path / "test.db"

        entries = [
            # Day before
            {"timestamp": "2026-04-04T23:59:59", "type": "denial",
             "tool": "bash_exec", "module": "omen", "category": "execution"},
            # Target day
            {"timestamp": "2026-04-05T00:00:01", "type": "allow",
             "tool": "web_search", "module": "wraith", "category": "search"},
            {"timestamp": "2026-04-05T23:59:58", "type": "denial",
             "tool": "file_write", "module": "omen", "category": "filesystem"},
            # Day after
            {"timestamp": "2026-04-06T00:00:01", "type": "denial",
             "tool": "bash_exec", "module": "omen", "category": "execution"},
        ]
        _insert_entries(db_path, entries)

        report = DailySafetyReport().generate(TARGET_DATE, db_path)
        assert report["summary"]["total_actions"] == 2
        assert report["summary"]["blocked"] == 1
        assert report["summary"]["approved_autonomous"] == 1
