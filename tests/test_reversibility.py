"""
Tests for Reversibility Engine
================================
Verifies that pre-action snapshots work correctly and rollback
restores files to their original state. If this breaks, Shadow
can't undo mistakes.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from modules.cerberus.reversibility import ReversibilityEngine


@pytest.fixture
def engine(tmp_path: Path) -> ReversibilityEngine:
    """Create a ReversibilityEngine with temp directories."""
    snap_dir = tmp_path / "snapshots"
    eng = ReversibilityEngine(snapshot_dir=snap_dir)
    yield eng
    eng.close()


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a sample file to snapshot."""
    f = tmp_path / "test_file.txt"
    f.write_text("original content", encoding="utf-8")
    return f


@pytest.fixture
def sample_db(tmp_path: Path) -> Path:
    """Create a sample SQLite database for DB snapshot tests."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, value TEXT)")
    conn.execute("INSERT INTO items VALUES (1, 'alpha', 'first')")
    conn.execute("INSERT INTO items VALUES (2, 'beta', 'second')")
    conn.execute("INSERT INTO items VALUES (3, 'gamma', 'third')")
    conn.commit()
    conn.close()
    return db_path


# --- File Snapshot Tests ---

class TestSnapshotFile:
    def test_creates_snapshot(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_file(sample_file, "action_001")
        assert sid is not None
        assert len(sid) == 32  # uuid4 hex

    def test_snapshot_preserves_content(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_file(sample_file, "action_001")
        # Find the snapshot file
        row = engine._conn.execute(
            "SELECT data_path FROM cerberus_snapshots WHERE snapshot_id = ?", (sid,)
        ).fetchone()
        snap_path = Path(row["data_path"])
        assert snap_path.read_text(encoding="utf-8") == "original content"

    def test_missing_file_raises(self, engine: ReversibilityEngine, tmp_path: Path):
        missing = tmp_path / "nonexistent.txt"
        with pytest.raises(FileNotFoundError):
            engine.snapshot_file(missing, "action_001")

    def test_records_in_database(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_file(sample_file, "action_002", risk_level="high")
        row = engine._conn.execute(
            "SELECT * FROM cerberus_snapshots WHERE snapshot_id = ?", (sid,)
        ).fetchone()
        assert row["type"] == "file"
        assert row["action_id"] == "action_002"
        assert row["risk_level"] == "high"


# --- Config Snapshot Tests ---

class TestSnapshotConfig:
    def test_creates_config_snapshot(self, engine: ReversibilityEngine):
        config = {"key": "value", "nested": {"a": 1}}
        sid = engine.snapshot_config("app.settings", config, "action_003")
        assert sid is not None

        row = engine._conn.execute(
            "SELECT data_path FROM cerberus_snapshots WHERE snapshot_id = ?", (sid,)
        ).fetchone()
        snap_path = Path(row["data_path"])
        loaded = yaml.safe_load(snap_path.read_text(encoding="utf-8"))
        assert loaded == config


# --- DB Snapshot Tests ---

class TestSnapshotDb:
    def test_creates_db_snapshot(self, engine: ReversibilityEngine, sample_db: Path):
        sid = engine.snapshot_db("items", "id <= 2", sample_db, "action_004")
        assert sid is not None

        row = engine._conn.execute(
            "SELECT data_path FROM cerberus_snapshots WHERE snapshot_id = ?", (sid,)
        ).fetchone()
        snap_path = Path(row["data_path"])
        data = json.loads(snap_path.read_text(encoding="utf-8"))
        assert data["table"] == "items"
        assert len(data["rows"]) == 2


# --- Rollback Tests ---

class TestRollback:
    def test_file_rollback_restores(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_file(sample_file, "action_005")
        # Modify the original
        sample_file.write_text("modified content", encoding="utf-8")
        assert sample_file.read_text(encoding="utf-8") == "modified content"

        # Rollback
        assert engine.rollback(sid) is True
        assert sample_file.read_text(encoding="utf-8") == "original content"

    def test_config_rollback_returns_false(self, engine: ReversibilityEngine):
        sid = engine.snapshot_config("key", {"a": 1}, "action_006")
        assert engine.rollback(sid) is False  # Phase 2 feature

    def test_db_rollback_returns_false(self, engine: ReversibilityEngine, sample_db: Path):
        sid = engine.snapshot_db("items", "1=1", sample_db, "action_007")
        assert engine.rollback(sid) is False  # Phase 2 feature

    def test_unknown_snapshot_returns_false(self, engine: ReversibilityEngine):
        assert engine.rollback("nonexistent_id") is False


# --- Cleanup Tests ---

class TestCleanup:
    def test_cleanup_removes_old(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_file(sample_file, "action_008")
        # Backdate the snapshot
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        engine._conn.execute(
            "UPDATE cerberus_snapshots SET created_at = ? WHERE snapshot_id = ?",
            (old_date, sid),
        )
        engine._conn.commit()

        deleted = engine.cleanup(max_age_days=30)
        assert deleted == 1

    def test_cleanup_keeps_high_risk(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_file(sample_file, "action_009", risk_level="high")
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        engine._conn.execute(
            "UPDATE cerberus_snapshots SET created_at = ? WHERE snapshot_id = ?",
            (old_date, sid),
        )
        engine._conn.commit()

        deleted = engine.cleanup(max_age_days=30, keep_high_risk=True)
        assert deleted == 0

    def test_cleanup_can_force_delete_high_risk(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_file(sample_file, "action_010", risk_level="high")
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        engine._conn.execute(
            "UPDATE cerberus_snapshots SET created_at = ? WHERE snapshot_id = ?",
            (old_date, sid),
        )
        engine._conn.commit()

        deleted = engine.cleanup(max_age_days=30, keep_high_risk=False)
        assert deleted == 1
