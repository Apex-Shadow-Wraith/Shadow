"""
Tests for CrossReferenceLinker — Grimoire's memory linking system.

Tests that the linker correctly discovers related memories, creates
bidirectional links, respects threshold filtering, and builds valid
graph structures. All tests use a mock Grimoire to avoid needing
Ollama running.

Author: Patrick (with Claude Opus 4.6)
Project: Shadow
"""

import sys
import sqlite3
import uuid
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.grimoire.cross_reference import CrossReferenceLinker


def _make_memory_id():
    """Generate a random UUID string for test memories."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_grimoire(tmp_path):
    """
    Create a mock Grimoire with a real SQLite connection.

    The linker needs a real SQLite connection for its cross_references table,
    but we mock recall() to avoid needing Ollama/ChromaDB.
    """
    conn = sqlite3.connect(str(tmp_path / "test_xref.db"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    # Create the memories table (simplified — just the columns the linker reads)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'uncategorized',
            source TEXT DEFAULT 'conversation',
            trust_level REAL DEFAULT 0.5,
            confidence REAL DEFAULT 0.5,
            created_at TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.commit()

    grimoire = MagicMock()
    grimoire.conn = conn
    # Default: recall returns nothing
    grimoire.recall = MagicMock(return_value=[])

    yield grimoire

    conn.close()


def _insert_memory(conn, memory_id, content, category="uncategorized"):
    """Helper to insert a test memory into the mock database."""
    conn.execute(
        "INSERT INTO memories (id, content, category, created_at, is_active) VALUES (?, ?, ?, ?, 1)",
        (memory_id, content, category, datetime.now().isoformat())
    )
    conn.commit()


class TestLinkRelated:
    """Tests for link_related() — finding and linking similar entries."""

    def test_finds_similar_entries(self, mock_grimoire):
        """link_related should find and return entries above the threshold."""
        entry_id = _make_memory_id()
        related_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "Shadow uses Ollama for local inference")
        _insert_memory(mock_grimoire.conn, related_id, "Ollama serves models locally on port 11434")

        # Mock recall to return the related entry with high similarity
        mock_grimoire.recall.return_value = [
            {
                "id": related_id,
                "content": "Ollama serves models locally on port 11434",
                "relevance": 0.85
            }
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        links = linker.link_related(entry_id, threshold=0.75)

        assert len(links) == 1
        assert links[0]["related_id"] == related_id
        assert links[0]["similarity_score"] == 0.85
        assert "Ollama" in links[0]["snippet"]

    def test_skips_self_reference(self, mock_grimoire):
        """link_related should not link a memory to itself."""
        entry_id = _make_memory_id()
        _insert_memory(mock_grimoire.conn, entry_id, "Shadow's architecture overview")

        # Recall returns the entry itself (which it would in real usage)
        mock_grimoire.recall.return_value = [
            {
                "id": entry_id,
                "content": "Shadow's architecture overview",
                "relevance": 1.0
            }
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        links = linker.link_related(entry_id)

        assert len(links) == 0

    def test_returns_empty_for_missing_entry(self, mock_grimoire):
        """link_related should return empty list for non-existent entry."""
        linker = CrossReferenceLinker(mock_grimoire)
        links = linker.link_related("nonexistent-id")

        assert links == []
        # recall should not even be called if entry doesn't exist
        mock_grimoire.recall.assert_not_called()

    def test_multiple_related_entries(self, mock_grimoire):
        """link_related should link to multiple entries above threshold."""
        entry_id = _make_memory_id()
        related_1 = _make_memory_id()
        related_2 = _make_memory_id()
        related_3 = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "GPU hardware specs")
        _insert_memory(mock_grimoire.conn, related_1, "RTX 5090 has 32GB VRAM")
        _insert_memory(mock_grimoire.conn, related_2, "Dual GPU setup for Shadow")
        _insert_memory(mock_grimoire.conn, related_3, "Python virtual environment setup")

        mock_grimoire.recall.return_value = [
            {"id": related_1, "content": "RTX 5090 has 32GB VRAM", "relevance": 0.92},
            {"id": related_2, "content": "Dual GPU setup for Shadow", "relevance": 0.80},
            {"id": related_3, "content": "Python virtual environment setup", "relevance": 0.40},
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        links = linker.link_related(entry_id, threshold=0.75)

        # Only the first two should be linked (above 0.75)
        assert len(links) == 2
        linked_ids = {link["related_id"] for link in links}
        assert related_1 in linked_ids
        assert related_2 in linked_ids
        assert related_3 not in linked_ids


class TestBidirectionalLinks:
    """Tests that links are stored in both directions."""

    def test_links_are_bidirectional(self, mock_grimoire):
        """Creating a link from A->B should also create B->A."""
        entry_id = _make_memory_id()
        related_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "Memory A")
        _insert_memory(mock_grimoire.conn, related_id, "Memory B")

        mock_grimoire.recall.return_value = [
            {"id": related_id, "content": "Memory B", "relevance": 0.90}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        linker.link_related(entry_id)

        # Check forward link: entry -> related
        forward = linker.get_links(entry_id)
        assert len(forward) == 1
        assert forward[0]["related_id"] == related_id

        # Check reverse link: related -> entry
        reverse = linker.get_links(related_id)
        assert len(reverse) == 1
        assert reverse[0]["related_id"] == entry_id

    def test_bidirectional_similarity_matches(self, mock_grimoire):
        """Both directions of a link should have the same similarity score."""
        entry_id = _make_memory_id()
        related_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "Memory A")
        _insert_memory(mock_grimoire.conn, related_id, "Memory B")

        mock_grimoire.recall.return_value = [
            {"id": related_id, "content": "Memory B", "relevance": 0.88}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        linker.link_related(entry_id)

        forward = linker.get_links(entry_id)
        reverse = linker.get_links(related_id)

        assert forward[0]["similarity"] == reverse[0]["similarity"] == 0.88


class TestGetLinks:
    """Tests for get_links() — retrieving cross-references."""

    def test_returns_correct_references(self, mock_grimoire):
        """get_links should return all links for a given entry."""
        entry_id = _make_memory_id()
        r1 = _make_memory_id()
        r2 = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "Base memory")
        _insert_memory(mock_grimoire.conn, r1, "Related 1")
        _insert_memory(mock_grimoire.conn, r2, "Related 2")

        mock_grimoire.recall.return_value = [
            {"id": r1, "content": "Related 1", "relevance": 0.90},
            {"id": r2, "content": "Related 2", "relevance": 0.80},
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        linker.link_related(entry_id)

        links = linker.get_links(entry_id)
        assert len(links) == 2

        # Should be sorted by similarity descending
        assert links[0]["similarity"] >= links[1]["similarity"]
        linked_ids = {link["related_id"] for link in links}
        assert r1 in linked_ids
        assert r2 in linked_ids

    def test_returns_empty_for_unlinked_entry(self, mock_grimoire):
        """get_links should return empty list if entry has no links."""
        linker = CrossReferenceLinker(mock_grimoire)
        links = linker.get_links("no-links-id")
        assert links == []

    def test_link_dict_structure(self, mock_grimoire):
        """Each link should have related_id, similarity, and created_at."""
        entry_id = _make_memory_id()
        related_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "Memory A")
        _insert_memory(mock_grimoire.conn, related_id, "Memory B")

        mock_grimoire.recall.return_value = [
            {"id": related_id, "content": "Memory B", "relevance": 0.85}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        linker.link_related(entry_id)

        links = linker.get_links(entry_id)
        assert len(links) == 1

        link = links[0]
        assert "related_id" in link
        assert "similarity" in link
        assert "created_at" in link
        assert isinstance(link["similarity"], float)
        assert isinstance(link["created_at"], str)


class TestAutoLinkNewEntry:
    """Tests for auto_link_new_entry() — the remember() integration point."""

    def test_creates_links_on_insert(self, mock_grimoire):
        """auto_link_new_entry should find and link related memories."""
        new_id = _make_memory_id()
        existing_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, new_id, "New memory about GPUs")
        _insert_memory(mock_grimoire.conn, existing_id, "Existing GPU memory")

        mock_grimoire.recall.return_value = [
            {"id": existing_id, "content": "Existing GPU memory", "relevance": 0.88}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        count = linker.auto_link_new_entry(new_id)

        assert count == 1
        assert len(linker.get_links(new_id)) == 1

    def test_returns_zero_when_no_matches(self, mock_grimoire):
        """auto_link_new_entry should return 0 when nothing is similar enough."""
        new_id = _make_memory_id()
        _insert_memory(mock_grimoire.conn, new_id, "Completely unique memory")

        mock_grimoire.recall.return_value = [
            {"id": _make_memory_id(), "content": "Unrelated stuff", "relevance": 0.30}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        count = linker.auto_link_new_entry(new_id)

        assert count == 0

    def test_respects_custom_threshold(self, mock_grimoire):
        """auto_link_new_entry should use the provided threshold."""
        new_id = _make_memory_id()
        related_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, new_id, "Memory A")
        _insert_memory(mock_grimoire.conn, related_id, "Memory B")

        mock_grimoire.recall.return_value = [
            {"id": related_id, "content": "Memory B", "relevance": 0.80}
        ]

        linker = CrossReferenceLinker(mock_grimoire)

        # With high threshold, 0.80 isn't enough
        count_high = linker.auto_link_new_entry(new_id, threshold=0.90)
        assert count_high == 0

        # With lower threshold, 0.80 is enough
        count_low = linker.auto_link_new_entry(new_id, threshold=0.75)
        assert count_low == 1


class TestBuildLinkGraph:
    """Tests for build_link_graph() — graph structure generation."""

    def test_returns_valid_graph_structure(self, mock_grimoire):
        """build_link_graph should return {nodes: [...], edges: [...]}."""
        a = _make_memory_id()
        b = _make_memory_id()
        c = _make_memory_id()

        _insert_memory(mock_grimoire.conn, a, "Alpha memory")
        _insert_memory(mock_grimoire.conn, b, "Beta memory")
        _insert_memory(mock_grimoire.conn, c, "Charlie memory")

        # Link a -> b and a -> c
        mock_grimoire.recall.return_value = [
            {"id": b, "content": "Beta memory", "relevance": 0.90},
            {"id": c, "content": "Charlie memory", "relevance": 0.85},
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        linker.link_related(a)

        graph = linker.build_link_graph()

        assert "nodes" in graph
        assert "edges" in graph
        assert isinstance(graph["nodes"], list)
        assert isinstance(graph["edges"], list)

    def test_graph_contains_correct_nodes(self, mock_grimoire):
        """Graph nodes should include all linked memories."""
        a = _make_memory_id()
        b = _make_memory_id()

        _insert_memory(mock_grimoire.conn, a, "Alpha memory")
        _insert_memory(mock_grimoire.conn, b, "Beta memory")

        mock_grimoire.recall.return_value = [
            {"id": b, "content": "Beta memory", "relevance": 0.90}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        linker.link_related(a)

        graph = linker.build_link_graph()
        node_ids = {node["id"] for node in graph["nodes"]}

        assert a in node_ids
        assert b in node_ids

    def test_graph_nodes_have_labels(self, mock_grimoire):
        """Each node should have an id and label field."""
        a = _make_memory_id()
        b = _make_memory_id()

        _insert_memory(mock_grimoire.conn, a, "Alpha memory content here")
        _insert_memory(mock_grimoire.conn, b, "Beta memory content here")

        mock_grimoire.recall.return_value = [
            {"id": b, "content": "Beta memory content here", "relevance": 0.90}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        linker.link_related(a)

        graph = linker.build_link_graph()
        for node in graph["nodes"]:
            assert "id" in node
            assert "label" in node
            assert isinstance(node["label"], str)

    def test_graph_edges_deduplicated(self, mock_grimoire):
        """Bidirectional links should produce only one edge per pair."""
        a = _make_memory_id()
        b = _make_memory_id()

        _insert_memory(mock_grimoire.conn, a, "Alpha memory")
        _insert_memory(mock_grimoire.conn, b, "Beta memory")

        mock_grimoire.recall.return_value = [
            {"id": b, "content": "Beta memory", "relevance": 0.90}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        linker.link_related(a)

        graph = linker.build_link_graph()

        # Despite bidirectional storage, there should be only 1 edge
        assert len(graph["edges"]) == 1
        edge = graph["edges"][0]
        assert "source" in edge
        assert "target" in edge
        assert "weight" in edge
        assert edge["weight"] == 0.90

    def test_graph_empty_when_no_links(self, mock_grimoire):
        """build_link_graph should return empty nodes/edges when no links exist."""
        linker = CrossReferenceLinker(mock_grimoire)
        graph = linker.build_link_graph()

        assert graph["nodes"] == []
        assert graph["edges"] == []

    def test_graph_filters_by_collection(self, mock_grimoire):
        """build_link_graph with collection param should filter by category."""
        a = _make_memory_id()
        b = _make_memory_id()
        c = _make_memory_id()

        _insert_memory(mock_grimoire.conn, a, "GPU related", category="hardware")
        _insert_memory(mock_grimoire.conn, b, "More GPU info", category="hardware")
        _insert_memory(mock_grimoire.conn, c, "Python basics", category="coding")

        # Link a -> b (both hardware) and a -> c (hardware -> coding)
        mock_grimoire.recall.return_value = [
            {"id": b, "content": "More GPU info", "relevance": 0.90},
            {"id": c, "content": "Python basics", "relevance": 0.80},
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        linker.link_related(a)

        # Filter to hardware only
        graph = linker.build_link_graph(collection="hardware")
        node_ids = {node["id"] for node in graph["nodes"]}

        assert a in node_ids
        assert b in node_ids
        # c is in "coding" category, should be excluded
        assert c not in node_ids


class TestThresholdFiltering:
    """Tests that threshold filtering works correctly."""

    def test_threshold_zero_links_everything(self, mock_grimoire):
        """With threshold=0, even low similarity should create links."""
        entry_id = _make_memory_id()
        low_sim_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "Entry")
        _insert_memory(mock_grimoire.conn, low_sim_id, "Low similarity")

        mock_grimoire.recall.return_value = [
            {"id": low_sim_id, "content": "Low similarity", "relevance": 0.10}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        links = linker.link_related(entry_id, threshold=0.0)

        assert len(links) == 1

    def test_threshold_one_links_nothing(self, mock_grimoire):
        """With threshold=1.0, only perfect matches would link (practically none)."""
        entry_id = _make_memory_id()
        high_sim_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "Entry")
        _insert_memory(mock_grimoire.conn, high_sim_id, "Very similar")

        mock_grimoire.recall.return_value = [
            {"id": high_sim_id, "content": "Very similar", "relevance": 0.99}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        links = linker.link_related(entry_id, threshold=1.0)

        assert len(links) == 0

    def test_exact_threshold_boundary_included(self, mock_grimoire):
        """Entry at exact threshold value SHOULD be linked (threshold is inclusive)."""
        entry_id = _make_memory_id()
        boundary_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "Entry")
        _insert_memory(mock_grimoire.conn, boundary_id, "Boundary")

        mock_grimoire.recall.return_value = [
            {"id": boundary_id, "content": "Boundary", "relevance": 0.75}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        links = linker.link_related(entry_id, threshold=0.75)

        # 0.75 is NOT less than 0.75, so the entry passes the filter
        assert len(links) == 1

    def test_just_below_threshold_excluded(self, mock_grimoire):
        """Entry just below threshold should NOT be linked."""
        entry_id = _make_memory_id()
        below_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "Entry")
        _insert_memory(mock_grimoire.conn, below_id, "Just below")

        mock_grimoire.recall.return_value = [
            {"id": below_id, "content": "Just below", "relevance": 0.749}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        links = linker.link_related(entry_id, threshold=0.75)

        assert len(links) == 0

    def test_just_above_threshold(self, mock_grimoire):
        """Entry just above threshold should be linked."""
        entry_id = _make_memory_id()
        above_id = _make_memory_id()

        _insert_memory(mock_grimoire.conn, entry_id, "Entry")
        _insert_memory(mock_grimoire.conn, above_id, "Just above")

        mock_grimoire.recall.return_value = [
            {"id": above_id, "content": "Just above", "relevance": 0.751}
        ]

        linker = CrossReferenceLinker(mock_grimoire)
        links = linker.link_related(entry_id, threshold=0.75)

        assert len(links) == 1
