"""
Tests for GrimoireReader — Read-Only Grimoire Access
======================================================
Tests the lightweight read-only interface that gives any module
independent access to Grimoire's knowledge base.
"""

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.grimoire.grimoire_reader import GrimoireReader


@pytest.fixture
def memory_db(tmp_path):
    """Create a test SQLite database with sample memories."""
    db_path = tmp_path / "test_memory.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            summary TEXT,
            category TEXT DEFAULT 'uncategorized',
            source TEXT DEFAULT 'conversation',
            source_module TEXT DEFAULT 'grimoire',
            trust_level REAL DEFAULT 0.5,
            confidence REAL DEFAULT 0.5,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            accessed_at TEXT,
            access_count INTEGER DEFAULT 0,
            embedding_id TEXT,
            is_active INTEGER DEFAULT 1,
            parent_id TEXT,
            model_used TEXT,
            tools_called TEXT,
            safety_class TEXT,
            user_feedback TEXT,
            metadata_json TEXT DEFAULT '{}',
            content_blocks TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            tag TEXT NOT NULL
        )
    """)

    now = datetime.now().isoformat()
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    two_days_ago = (datetime.now() - timedelta(days=2)).isoformat()

    # Insert sample memories
    memories = [
        ("mem-001", "Firewall rules for port 443", "firewall rules",
         "security_knowledge", "research", "sentinel", 0.7, 0.8, now, now, 5),
        ("mem-002", "Python list comprehension patterns", "list comprehensions",
         "code_pattern", "conversation", "omen", 0.5, 0.6, one_hour_ago, one_hour_ago, 3),
        ("mem-003", "Biblical ethics on stewardship", "stewardship ethics",
         "ethics", "user_stated", "cerberus", 0.9, 0.9, two_days_ago, two_days_ago, 10),
        ("mem-004", "LMN software pricing structure", "LMN pricing",
         "business", "user_stated", "wraith", 0.9, 0.8, now, now, 7),
        ("mem-005", "Old deprecated info", "old stuff",
         "uncategorized", "conversation", "grimoire", 0.3, 0.3, two_days_ago, two_days_ago, 0),
    ]

    for mem in memories:
        conn.execute("""
            INSERT INTO memories (id, content, summary, category, source, source_module,
                                  trust_level, confidence, created_at, updated_at, access_count,
                                  is_active, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '{}')
        """, mem)

    # Inactive memory (should not appear in searches)
    conn.execute("""
        INSERT INTO memories (id, content, summary, category, source, source_module,
                              trust_level, confidence, created_at, updated_at, access_count,
                              is_active, metadata_json)
        VALUES ('mem-inactive', 'This is deleted', 'deleted', 'uncategorized',
                'conversation', 'grimoire', 0.5, 0.5, ?, ?, 0, 0, '{}')
    """, (now, now))

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def mock_collection():
    """Create a mock ChromaDB collection."""
    collection = MagicMock()
    return collection


@pytest.fixture
def reader(memory_db, mock_collection):
    """Create a GrimoireReader with mocked ChromaDB."""
    r = GrimoireReader(
        module_name="test_module",
        memory_db_path=str(memory_db),
        vector_db_path="/tmp/fake_vectors",
    )
    # Manually initialize with mocked collection
    r._conn = sqlite3.connect(str(memory_db))
    r._conn.row_factory = sqlite3.Row
    r._collection = mock_collection
    r._initialized = True
    return r


class TestSearch:
    """Tests for semantic search."""

    def test_search_returns_results(self, reader, mock_collection):
        """Search should return enriched results from ChromaDB + SQLite."""
        mock_collection.query.return_value = {
            "ids": [["mem-001", "mem-002"]],
            "distances": [[0.1, 0.3]],
        }

        with patch.object(reader, "_get_embedding", return_value=[0.1] * 768):
            results = reader.search("firewall security")

        assert len(results) == 2
        assert results[0]["content"] == "Firewall rules for port 443"
        assert results[0]["relevance_score"] == 0.9
        assert results[0]["source"] == "research"
        assert results[0]["category"] == "security_knowledge"
        assert results[0]["id"] == "mem-001"
        assert results[1]["relevance_score"] == 0.7

    def test_search_with_category_filter(self, reader, mock_collection):
        """Search should pass category filter to ChromaDB."""
        mock_collection.query.return_value = {
            "ids": [["mem-001"]],
            "distances": [[0.15]],
        }

        with patch.object(reader, "_get_embedding", return_value=[0.1] * 768):
            results = reader.search("security", category="security_knowledge")

        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["where"] == {"category": "security_knowledge"}

    def test_search_empty_results(self, reader, mock_collection):
        """Search should return empty list when no matches."""
        mock_collection.query.return_value = {
            "ids": [[]],
            "distances": [[]],
        }

        with patch.object(reader, "_get_embedding", return_value=[0.1] * 768):
            results = reader.search("nonexistent topic")

        assert results == []

    def test_search_skips_inactive_memories(self, reader, mock_collection):
        """Search should not return inactive (deleted) memories."""
        mock_collection.query.return_value = {
            "ids": [["mem-inactive"]],
            "distances": [[0.05]],
        }

        with patch.object(reader, "_get_embedding", return_value=[0.1] * 768):
            results = reader.search("deleted stuff")

        assert results == []

    def test_search_graceful_when_not_connected(self):
        """Search should return empty list when not connected."""
        r = GrimoireReader("test", "/nonexistent/path.db", "/nonexistent/vectors")
        r._initialized = True  # Skip lazy init
        results = r.search("anything")
        assert results == []


class TestSearchByCategory:
    """Tests for category browsing."""

    def test_filters_by_category(self, reader):
        """Should return only memories in the specified category."""
        results = reader.search_by_category("security_knowledge")
        assert len(results) == 1
        assert results[0]["content"] == "Firewall rules for port 443"
        assert results[0]["category"] == "security_knowledge"

    def test_empty_category(self, reader):
        """Should return empty list for nonexistent category."""
        results = reader.search_by_category("nonexistent_category")
        assert results == []

    def test_respects_limit(self, reader):
        """Should respect the limit parameter."""
        results = reader.search_by_category("security_knowledge", limit=1)
        assert len(results) <= 1

    def test_ordered_newest_first(self, reader):
        """Results should be ordered by created_at DESC."""
        results = reader.search_by_category("ethics")
        if len(results) > 1:
            assert results[0]["timestamp"] >= results[1]["timestamp"]


class TestCheckKnowledgeExists:
    """Tests for deduplication check."""

    def test_returns_true_for_existing_knowledge(self, reader, mock_collection):
        """Should return True when similar knowledge exists above threshold."""
        mock_collection.query.return_value = {
            "ids": [["mem-001"]],
            "distances": [[0.1]],  # relevance = 0.9 > 0.85
        }

        with patch.object(reader, "_get_embedding", return_value=[0.1] * 768):
            assert reader.check_knowledge_exists("firewall rules") is True

    def test_returns_false_for_new_knowledge(self, reader, mock_collection):
        """Should return False when nothing similar exists."""
        mock_collection.query.return_value = {
            "ids": [["mem-001"]],
            "distances": [[0.5]],  # relevance = 0.5 < 0.85
        }

        with patch.object(reader, "_get_embedding", return_value=[0.1] * 768):
            assert reader.check_knowledge_exists("quantum computing") is False

    def test_returns_false_when_no_results(self, reader, mock_collection):
        """Should return False when ChromaDB has no results."""
        mock_collection.query.return_value = {
            "ids": [[]],
            "distances": [[]],
        }

        with patch.object(reader, "_get_embedding", return_value=[0.1] * 768):
            assert reader.check_knowledge_exists("brand new topic") is False

    def test_custom_threshold(self, reader, mock_collection):
        """Should respect custom threshold."""
        mock_collection.query.return_value = {
            "ids": [["mem-001"]],
            "distances": [[0.15]],  # relevance = 0.85
        }

        with patch.object(reader, "_get_embedding", return_value=[0.1] * 768):
            # Default threshold 0.85 — should pass
            assert reader.check_knowledge_exists("test", threshold=0.85) is True
            # Higher threshold — should fail
            assert reader.check_knowledge_exists("test", threshold=0.90) is False


class TestGetModuleKnowledge:
    """Tests for module-specific knowledge retrieval."""

    def test_filters_by_module_name(self, reader):
        """Should return only knowledge stored by the specified module."""
        results = reader.get_module_knowledge("sentinel")
        assert len(results) == 1
        assert results[0]["source_module"] == "sentinel"
        assert results[0]["content"] == "Firewall rules for port 443"

    def test_returns_empty_for_unknown_module(self, reader):
        """Should return empty list for a module with no stored knowledge."""
        results = reader.get_module_knowledge("unknown_module")
        assert results == []

    def test_respects_limit(self, reader):
        """Should respect the limit parameter."""
        results = reader.get_module_knowledge("sentinel", limit=1)
        assert len(results) <= 1

    def test_multiple_results(self, reader):
        """Modules with multiple entries should return all of them."""
        results = reader.get_module_knowledge("grimoire")
        # grimoire has mem-005 (active)
        assert len(results) >= 1


class TestGetRecent:
    """Tests for time-windowed retrieval."""

    def test_returns_recent_memories(self, reader):
        """Should return memories created within the time window."""
        results = reader.get_recent(limit=10, hours=24)
        # mem-001, mem-002, mem-004 are recent (within 24h)
        assert len(results) >= 2

    def test_excludes_old_memories(self, reader):
        """Should not return memories older than the time window."""
        results = reader.get_recent(limit=10, hours=1)
        # Only very recent ones (within 1 hour)
        for result in results:
            created = datetime.fromisoformat(result["timestamp"])
            cutoff = datetime.now() - timedelta(hours=1)
            assert created >= cutoff

    def test_ordered_newest_first(self, reader):
        """Results should be ordered by created_at DESC."""
        results = reader.get_recent(limit=10, hours=48)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i]["timestamp"] >= results[i + 1]["timestamp"]


class TestSearchRelated:
    """Tests for finding related memories."""

    def test_finds_related_memories(self, reader, mock_collection):
        """Should find memories related to a given memory."""
        # Mock getting the source memory's embedding
        mock_collection.get.return_value = {
            "embeddings": [[0.1] * 768],
        }
        # Mock finding neighbors
        mock_collection.query.return_value = {
            "ids": [["mem-001", "mem-002", "mem-003"]],
            "distances": [[0.0, 0.2, 0.4]],  # First is self (distance 0)
        }

        results = reader.search_related("mem-001", limit=2)
        # Should exclude the source memory itself
        assert all(r["id"] != "mem-001" for r in results)
        assert len(results) <= 2

    def test_returns_empty_for_missing_memory(self, reader, mock_collection):
        """Should return empty list if source memory not found in vectors."""
        mock_collection.get.return_value = {
            "embeddings": [None],
        }

        results = reader.search_related("nonexistent-id")
        assert results == []


class TestClose:
    """Tests for cleanup."""

    def test_close_cleans_up(self, reader):
        """Close should clean up connections."""
        reader.close()
        assert reader._conn is None
        assert reader._initialized is False

    def test_double_close_safe(self, reader):
        """Closing twice should not raise."""
        reader.close()
        reader.close()  # Should not raise
