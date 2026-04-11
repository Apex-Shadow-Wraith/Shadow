"""Tests for Grimoire Snapshot Exporter."""

import os
import sqlite3
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from modules.grimoire.snapshot_exporter import SnapshotExporter


@pytest.fixture
def mock_grimoire(tmp_path):
    """Create a mock Grimoire with a real SQLite connection for query testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            content TEXT,
            summary TEXT,
            category TEXT,
            source TEXT,
            source_module TEXT,
            trust_level REAL,
            confidence REAL,
            created_at TEXT,
            updated_at TEXT,
            accessed_at TEXT,
            access_count INTEGER DEFAULT 0,
            embedding_id TEXT,
            is_active INTEGER DEFAULT 1,
            parent_id TEXT,
            model_used TEXT,
            tools_called TEXT,
            safety_class TEXT,
            user_feedback TEXT,
            metadata_json TEXT,
            content_blocks TEXT
        )
    """)
    conn.commit()

    grimoire = MagicMock()
    grimoire.conn = conn
    return grimoire


def _insert_memory(conn, mid, content, category, trust=0.5, access_count=0,
                    source="conversation", source_module="test", active=1):
    """Helper to insert a test memory."""
    conn.cursor().execute(
        """INSERT INTO memories
           (id, content, category, trust_level, confidence, source, source_module,
            created_at, access_count, is_active, metadata_json)
           VALUES (?, ?, ?, ?, 0.8, ?, ?, '2026-04-11T12:00:00', ?, ?, NULL)""",
        (mid, content, category, trust, source, source_module, access_count, active),
    )
    conn.commit()


class TestExportCollection:
    """Tests for export_collection."""

    def test_creates_valid_markdown(self, mock_grimoire, tmp_path):
        """Export creates a well-formatted markdown file."""
        _insert_memory(mock_grimoire.conn, "m1", "Shadow uses phi4-mini for routing.",
                       "architecture", trust=0.9, access_count=5)
        _insert_memory(mock_grimoire.conn, "m2", "ChromaDB stores vector embeddings.",
                       "architecture", trust=0.7, access_count=3)

        exporter = SnapshotExporter(mock_grimoire)
        out = str(tmp_path / "arch.md")
        result = exporter.export_collection("architecture", out)

        assert result == out
        assert Path(out).exists()
        text = Path(out).read_text(encoding="utf-8")
        assert "# Collection: architecture" in text
        assert "## Entry 1" in text
        assert "## Entry 2" in text
        assert "Shadow uses phi4-mini" in text
        assert "ChromaDB stores vector" in text
        # Higher trust should come first
        lines = text.split("\n")
        entry1_idx = next(i for i, l in enumerate(lines) if "## Entry 1" in l)
        entry2_idx = next(i for i, l in enumerate(lines) if "## Entry 2" in l)
        # Entry 1 content should mention phi4-mini (trust 0.9)
        block1 = "\n".join(lines[entry1_idx:entry2_idx])
        assert "phi4-mini" in block1

    def test_empty_collection_produces_valid_file(self, mock_grimoire, tmp_path):
        """Empty collection produces a file with a header and empty message."""
        exporter = SnapshotExporter(mock_grimoire)
        out = str(tmp_path / "empty.md")
        result = exporter.export_collection("nonexistent", out)

        assert result == out
        text = Path(out).read_text(encoding="utf-8")
        assert "# Collection: nonexistent" in text
        assert "No entries" in text

    def test_max_entries_limit(self, mock_grimoire, tmp_path):
        """max_entries caps the number of exported entries."""
        for i in range(10):
            _insert_memory(mock_grimoire.conn, f"m{i}", f"Memory {i}",
                           "patterns", trust=0.5, access_count=i)

        exporter = SnapshotExporter(mock_grimoire)
        out = str(tmp_path / "limited.md")
        exporter.export_collection("patterns", out, max_entries=3)

        text = Path(out).read_text(encoding="utf-8")
        assert "## Entry 3" in text
        assert "## Entry 4" not in text

    def test_creates_parent_directories(self, mock_grimoire, tmp_path):
        """Export creates missing parent directories."""
        exporter = SnapshotExporter(mock_grimoire)
        out = str(tmp_path / "deep" / "nested" / "dir" / "export.md")
        result = exporter.export_collection("test", out)
        assert Path(result).exists()

    def test_inactive_memories_excluded(self, mock_grimoire, tmp_path):
        """Inactive (deleted/corrected) memories are not exported."""
        _insert_memory(mock_grimoire.conn, "active", "Active memory",
                       "bugs", trust=0.9, active=1)
        _insert_memory(mock_grimoire.conn, "deleted", "Deleted memory",
                       "bugs", trust=0.9, active=0)

        exporter = SnapshotExporter(mock_grimoire)
        out = str(tmp_path / "bugs.md")
        exporter.export_collection("bugs", out)

        text = Path(out).read_text(encoding="utf-8")
        assert "Active memory" in text
        assert "Deleted memory" not in text


class TestExportKeyMemories:
    """Tests for export_key_memories."""

    def test_filters_by_default_categories(self, mock_grimoire, tmp_path):
        """Uses default categories when none specified."""
        for cat in SnapshotExporter.DEFAULT_CATEGORIES:
            _insert_memory(mock_grimoire.conn, f"m-{cat}", f"Content for {cat}",
                           cat, trust=0.8)

        exporter = SnapshotExporter(mock_grimoire)
        files = exporter.export_key_memories(str(tmp_path))

        assert len(files) == 4
        for f in files:
            assert Path(f).exists()

        filenames = [Path(f).name for f in files]
        assert "architecture.md" in filenames
        assert "bug_fixes.md" in filenames
        assert "decisions.md" in filenames
        assert "patterns.md" in filenames

    def test_custom_categories(self, mock_grimoire, tmp_path):
        """Custom category list is respected."""
        _insert_memory(mock_grimoire.conn, "m1", "Python tip", "python", trust=0.8)

        exporter = SnapshotExporter(mock_grimoire)
        files = exporter.export_key_memories(str(tmp_path), categories=["python"])

        assert len(files) == 1
        assert Path(files[0]).name == "python.md"
        text = Path(files[0]).read_text(encoding="utf-8")
        assert "Python tip" in text

    def test_importance_ordering(self, mock_grimoire, tmp_path):
        """Entries are ordered by trust_level DESC, access_count DESC."""
        _insert_memory(mock_grimoire.conn, "low", "Low importance",
                       "architecture", trust=0.1, access_count=1)
        _insert_memory(mock_grimoire.conn, "high", "High importance",
                       "architecture", trust=1.0, access_count=50)

        exporter = SnapshotExporter(mock_grimoire)
        files = exporter.export_key_memories(str(tmp_path), categories=["architecture"])

        text = Path(files[0]).read_text(encoding="utf-8")
        high_pos = text.index("High importance")
        low_pos = text.index("Low importance")
        assert high_pos < low_pos


class TestExportForProjectKnowledge:
    """Tests for export_for_project_knowledge."""

    def test_creates_index_file(self, mock_grimoire, tmp_path):
        """Full export creates an index.md linking all categories."""
        _insert_memory(mock_grimoire.conn, "m1", "Arch note", "architecture", trust=0.9)
        _insert_memory(mock_grimoire.conn, "m2", "Bug fix", "bug_fixes", trust=0.8)

        exporter = SnapshotExporter(mock_grimoire)
        result = exporter.export_for_project_knowledge(str(tmp_path))

        assert "files_created" in result
        assert "total_entries" in result
        assert "total_size_bytes" in result

        index_path = tmp_path / "index.md"
        assert index_path.exists()
        index_text = index_path.read_text(encoding="utf-8")
        assert "Grimoire Snapshot Index" in index_text
        assert "architecture" in index_text
        assert "bug_fixes" in index_text
        assert "Total entries" in index_text

    def test_one_file_per_category(self, mock_grimoire, tmp_path):
        """Creates one .md file per active category."""
        cats = ["hardware", "python", "business"]
        for cat in cats:
            _insert_memory(mock_grimoire.conn, f"m-{cat}", f"About {cat}", cat)

        exporter = SnapshotExporter(mock_grimoire)
        result = exporter.export_for_project_knowledge(str(tmp_path))

        # One per category + index
        assert len(result["files_created"]) == len(cats) + 1
        for cat in cats:
            assert (tmp_path / f"{cat}.md").exists()

    def test_total_entries_count(self, mock_grimoire, tmp_path):
        """total_entries reflects actual memory count."""
        for i in range(5):
            _insert_memory(mock_grimoire.conn, f"m{i}", f"Memory {i}", "decisions")

        exporter = SnapshotExporter(mock_grimoire)
        result = exporter.export_for_project_knowledge(str(tmp_path))
        assert result["total_entries"] == 5

    def test_total_size_bytes(self, mock_grimoire, tmp_path):
        """total_size_bytes is a positive integer matching actual file sizes."""
        _insert_memory(mock_grimoire.conn, "m1", "Some content", "test")

        exporter = SnapshotExporter(mock_grimoire)
        result = exporter.export_for_project_knowledge(str(tmp_path))
        assert result["total_size_bytes"] > 0

        # Verify it matches actual sizes
        actual_size = sum(Path(f).stat().st_size for f in result["files_created"])
        assert result["total_size_bytes"] == actual_size

    def test_empty_grimoire(self, mock_grimoire, tmp_path):
        """Export on empty Grimoire creates only index.md."""
        exporter = SnapshotExporter(mock_grimoire)
        result = exporter.export_for_project_knowledge(str(tmp_path))

        assert result["total_entries"] == 0
        assert len(result["files_created"]) == 1  # just index
        assert "index.md" in result["files_created"][0]

    def test_excludes_inactive_memories(self, mock_grimoire, tmp_path):
        """Inactive memories don't appear in categories or counts."""
        _insert_memory(mock_grimoire.conn, "active", "Active", "test_cat", active=1)
        _insert_memory(mock_grimoire.conn, "inactive", "Inactive", "ghost_cat", active=0)

        exporter = SnapshotExporter(mock_grimoire)
        result = exporter.export_for_project_knowledge(str(tmp_path))

        assert result["total_entries"] == 1
        # ghost_cat should not get its own file
        assert not (tmp_path / "ghost_cat.md").exists()
