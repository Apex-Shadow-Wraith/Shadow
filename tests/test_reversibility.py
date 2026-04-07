"""
Tests for Cerberus Reversibility Engine
=========================================
Snapshot and rollback. If this breaks, Shadow can't undo mistakes.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from modules.cerberus.reversibility import ReversibilityEngine


@pytest.fixture
def engine(tmp_path: Path) -> ReversibilityEngine:
    """Create a ReversibilityEngine with temp directories."""
    snapshot_dir = tmp_path / "snapshots"
    db_path = snapshot_dir / "cerberus_snapshots.db"
    eng = ReversibilityEngine(snapshot_dir=snapshot_dir, db_path=db_path)
    yield eng
    eng.close()


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a sample file to snapshot."""
    f = tmp_path / "target.txt"
    f.write_text("original content", encoding="utf-8")
    return f


@pytest.fixture
def sample_db(tmp_path: Path) -> Path:
    """Create a sample SQLite database with test data."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, value TEXT)")
    conn.execute("INSERT INTO items VALUES (1, 'alpha', 'first')")
    conn.execute("INSERT INTO items VALUES (2, 'beta', 'second')")
    conn.commit()
    conn.close()
    return db


# --- File snapshot and rollback ---

class TestFileSnapshot:
    def test_creates_copy_and_records(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_before_action("file", str(sample_file))
        snap = engine.get_snapshot(sid)
        assert snap is not None
        assert snap["action_type"] == "file"
        assert snap["status"] == "active"
        assert Path(snap["original_state_path"]).exists()
        # Verify copied content matches
        copied = Path(snap["original_state_path"]).read_text(encoding="utf-8")
        assert copied == "original content"

    def test_rollback_restores_file(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_before_action("file", str(sample_file))
        # Modify the original
        sample_file.write_text("modified content", encoding="utf-8")
        assert sample_file.read_text(encoding="utf-8") == "modified content"
        # Rollback
        assert engine.rollback(sid) is True
        assert sample_file.read_text(encoding="utf-8") == "original content"
        # Status updated
        snap = engine.get_snapshot(sid)
        assert snap["status"] == "rolled_back"

    def test_rollback_restores_deleted_file(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_before_action("file", str(sample_file))
        sample_file.unlink()
        assert not sample_file.exists()
        assert engine.rollback(sid) is True
        assert sample_file.exists()
        assert sample_file.read_text(encoding="utf-8") == "original content"

    def test_missing_file_raises(self, engine: ReversibilityEngine, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            engine.snapshot_before_action("file", str(tmp_path / "nonexistent.txt"))

    def test_double_rollback_fails(self, engine: ReversibilityEngine, sample_file: Path):
        sid = engine.snapshot_before_action("file", str(sample_file))
        assert engine.rollback(sid) is True
        assert engine.rollback(sid) is False


# --- Config snapshot and rollback ---

class TestConfigSnapshot:
    def test_saves_state_and_records(self, engine: ReversibilityEngine, tmp_path: Path):
        config_path = tmp_path / "config.json"
        config_path.write_text('{"key": "old_value"}', encoding="utf-8")
        sid = engine.snapshot_before_action(
            "config",
            str(config_path),
            metadata={"config_state": {"key": "old_value"}, "risk_level": "medium"},
        )
        snap = engine.get_snapshot(sid)
        assert snap is not None
        assert snap["action_type"] == "config"
        assert snap["status"] == "active"
        # Verify saved state
        state = json.loads(Path(snap["original_state_path"]).read_text(encoding="utf-8"))
        assert state["key"] == "old_value"

    def test_rollback_restores_config(self, engine: ReversibilityEngine, tmp_path: Path):
        config_path = tmp_path / "settings.json"
        config_path.write_text('{"mode": "safe"}', encoding="utf-8")
        sid = engine.snapshot_before_action(
            "config",
            str(config_path),
            metadata={"config_state": {"mode": "safe"}},
        )
        # Modify config
        config_path.write_text('{"mode": "dangerous"}', encoding="utf-8")
        # Rollback
        assert engine.rollback(sid) is True
        restored = json.loads(config_path.read_text(encoding="utf-8"))
        assert restored["mode"] == "safe"
        snap = engine.get_snapshot(sid)
        assert snap["status"] == "rolled_back"


# --- Database snapshot and rollback ---

class TestDatabaseSnapshot:
    def test_saves_rows_and_records(self, engine: ReversibilityEngine, sample_db: Path):
        sid = engine.snapshot_before_action(
            "database",
            "items",
            metadata={
                "db_path": str(sample_db),
                "table": "items",
                "where_clause": "id = 1",
            },
        )
        snap = engine.get_snapshot(sid)
        assert snap is not None
        assert snap["action_type"] == "database"
        log = json.loads(Path(snap["original_state_path"]).read_text(encoding="utf-8"))
        assert log["row_count"] == 1
        assert log["rows"][0]["name"] == "alpha"

    def test_rollback_restores_rows(self, engine: ReversibilityEngine, sample_db: Path):
        sid = engine.snapshot_before_action(
            "database",
            "items",
            metadata={
                "db_path": str(sample_db),
                "table": "items",
                "where_clause": "id = 1",
            },
        )
        # Delete the row
        conn = sqlite3.connect(str(sample_db))
        conn.execute("DELETE FROM items WHERE id = 1")
        conn.commit()
        conn.close()
        # Rollback
        assert engine.rollback(sid) is True
        # Verify restored
        conn = sqlite3.connect(str(sample_db))
        row = conn.execute("SELECT * FROM items WHERE id = 1").fetchone()
        conn.close()
        assert row is not None
        assert row[1] == "alpha"


# --- External action snapshot ---

class TestExternalSnapshot:
    def test_records_but_rollback_fails(self, engine: ReversibilityEngine):
        sid = engine.snapshot_before_action(
            "external",
            "email_send",
            metadata={
                "content_sent": "Hello, world!",
                "recipients": ["test@example.com"],
                "risk_level": "high",
            },
        )
        snap = engine.get_snapshot(sid)
        assert snap is not None
        assert snap["action_type"] == "external"
        assert snap["status"] == "active"
        # Rollback should return False
        assert engine.rollback(sid) is False
        # Status should still be active (not rolled_back)
        snap = engine.get_snapshot(sid)
        assert snap["status"] == "active"


# --- list_snapshots ---

class TestListSnapshots:
    def test_returns_snapshots_newest_first(self, engine: ReversibilityEngine, tmp_path: Path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a", encoding="utf-8")
        f2.write_text("b", encoding="utf-8")
        engine.snapshot_before_action("file", str(f1))
        engine.snapshot_before_action("file", str(f2))
        snaps = engine.list_snapshots()
        assert len(snaps) == 2
        # Newest first
        assert snaps[0]["target"] == str(f2)

    def test_filters_by_action_type(self, engine: ReversibilityEngine, tmp_path: Path):
        f = tmp_path / "c.txt"
        f.write_text("c", encoding="utf-8")
        engine.snapshot_before_action("file", str(f))
        engine.snapshot_before_action(
            "config", "some_key", metadata={"config_state": {"x": 1}}
        )
        engine.snapshot_before_action(
            "external", "email_send", metadata={"content_sent": "hi"}
        )
        file_snaps = engine.list_snapshots(action_type="file")
        assert len(file_snaps) == 1
        assert file_snaps[0]["action_type"] == "file"
        ext_snaps = engine.list_snapshots(action_type="external")
        assert len(ext_snaps) == 1

    def test_respects_limit(self, engine: ReversibilityEngine, tmp_path: Path):
        for i in range(5):
            f = tmp_path / f"file_{i}.txt"
            f.write_text(str(i), encoding="utf-8")
            engine.snapshot_before_action("file", str(f))
        snaps = engine.list_snapshots(limit=3)
        assert len(snaps) == 3


# --- cleanup_expired ---

class TestCleanupExpired:
    def test_deletes_old_snapshots(self, engine: ReversibilityEngine, tmp_path: Path):
        f = tmp_path / "old.txt"
        f.write_text("old", encoding="utf-8")
        sid = engine.snapshot_before_action("file", str(f))
        # Backdate the timestamp
        old_time = (datetime.now() - timedelta(days=60)).isoformat()
        engine._conn.execute(
            "UPDATE snapshots SET timestamp = ? WHERE snapshot_id = ?",
            (old_time, sid),
        )
        engine._conn.commit()
        deleted = engine.cleanup_expired(retention_days=30)
        assert deleted == 1
        assert engine.get_snapshot(sid) is None

    def test_preserves_high_risk(self, engine: ReversibilityEngine, tmp_path: Path):
        sid = engine.snapshot_before_action(
            "external",
            "email_send",
            metadata={"content_sent": "important", "risk_level": "high"},
        )
        old_time = (datetime.now() - timedelta(days=60)).isoformat()
        engine._conn.execute(
            "UPDATE snapshots SET timestamp = ? WHERE snapshot_id = ?",
            (old_time, sid),
        )
        engine._conn.commit()
        deleted = engine.cleanup_expired(retention_days=30, keep_high_risk=True)
        assert deleted == 0
        assert engine.get_snapshot(sid) is not None

    def test_deletes_high_risk_when_disabled(self, engine: ReversibilityEngine, tmp_path: Path):
        sid = engine.snapshot_before_action(
            "external",
            "email_send",
            metadata={"content_sent": "hi", "risk_level": "high"},
        )
        old_time = (datetime.now() - timedelta(days=60)).isoformat()
        engine._conn.execute(
            "UPDATE snapshots SET timestamp = ? WHERE snapshot_id = ?",
            (old_time, sid),
        )
        engine._conn.commit()
        deleted = engine.cleanup_expired(retention_days=30, keep_high_risk=False)
        assert deleted == 1


# --- SQLite persistence ---

class TestSQLitePersistence:
    def test_snapshots_persist_across_instances(self, tmp_path: Path):
        snapshot_dir = tmp_path / "persist_test"
        db_path = snapshot_dir / "cerberus_snapshots.db"
        f = tmp_path / "persist.txt"
        f.write_text("persist me", encoding="utf-8")

        # Create snapshot with first instance
        eng1 = ReversibilityEngine(snapshot_dir=snapshot_dir, db_path=db_path)
        sid = eng1.snapshot_before_action("file", str(f))
        eng1.close()

        # Load with second instance
        eng2 = ReversibilityEngine(snapshot_dir=snapshot_dir, db_path=db_path)
        snap = eng2.get_snapshot(sid)
        assert snap is not None
        assert snap["target"] == str(f)
        assert snap["status"] == "active"
        eng2.close()


# --- Invalid action type ---

class TestInvalidActionType:
    def test_unknown_type_raises(self, engine: ReversibilityEngine):
        with pytest.raises(ValueError, match="Unknown action_type"):
            engine.snapshot_before_action("invalid_type", "target")

    def test_rollback_nonexistent_id(self, engine: ReversibilityEngine):
        assert engine.rollback("nonexistent_id") is False
