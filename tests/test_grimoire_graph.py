"""
Tests for Grimoire Graph Layer
================================
Covers GraphLayer (SQLite-backed knowledge graph), EntityExtractor
(rule-based entity/relationship extraction), and integration with
the main Grimoire class.

These tests mock Ollama embeddings so they run without a live server.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from modules.grimoire.graph_layer import (
    GraphLayer,
    VALID_ENTITY_TYPES,
    VALID_RELATION_TYPES,
)
from modules.grimoire.entity_extractor import EntityExtractor
from modules.grimoire.grimoire import Grimoire


# ===========================================================================
# Helpers
# ===========================================================================

def _fake_embedding(text):
    """Deterministic fake embedding — 768-dim vector derived from text hash."""
    import hashlib
    h = hashlib.sha256(text.encode()).hexdigest()
    nums = [int(h[i:i+2], 16) / 255.0 for i in range(0, len(h), 2)]
    return (nums * 24)[:768]


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def graph(tmp_path):
    """Fresh GraphLayer backed by a temp SQLite file."""
    db_path = str(tmp_path / "test_graph.db")
    g = GraphLayer(db_path)
    yield g
    g.close()


@pytest.fixture
def graph_memory():
    """In-memory GraphLayer for fast tests."""
    g = GraphLayer(":memory:")
    yield g
    g.close()


@pytest.fixture
def extractor():
    """EntityExtractor instance."""
    return EntityExtractor()


@pytest.fixture
def grimoire(tmp_path):
    """Grimoire instance with temp paths, mocked embeddings, graph enabled."""
    db_path = tmp_path / "test_memory.db"
    vector_path = tmp_path / "test_vectors"
    graph_db_path = str(tmp_path / "test_graph.db")

    with patch.object(Grimoire, '_get_embedding', side_effect=_fake_embedding):
        g = Grimoire(
            db_path=str(db_path),
            vector_path=str(vector_path),
            ollama_url="http://localhost:11434",
            embed_model="nomic-embed-text"
        )
        # Ensure graph layer is wired up with our temp path
        from modules.grimoire.graph_layer import GraphLayer as GL
        from modules.grimoire.entity_extractor import EntityExtractor as EE
        g._graph = GL(graph_db_path)
        g._extractor = EE()
        yield g
        g.close()


# ===========================================================================
# GraphLayer CRUD Tests
# ===========================================================================

class TestGraphLayerCRUD:
    """Basic node and edge operations."""

    def test_add_entity(self, graph_memory):
        graph_memory.add_entity("python", "technology", "mem-1")
        ent = graph_memory.get_entity("python")
        assert ent is not None
        assert ent["name"] == "python"
        assert ent["entity_type"] == "technology"
        assert ent["source_memory_id"] == "mem-1"

    def test_add_entity_upsert(self, graph_memory):
        """Adding same entity name again updates fields."""
        graph_memory.add_entity("python", "technology", "mem-1")
        graph_memory.add_entity("python", "technology", "mem-2",
                                metadata={"version": "3.14"})
        ent = graph_memory.get_entity("python")
        assert ent["source_memory_id"] == "mem-2"
        meta = json.loads(ent["metadata"])
        assert meta["version"] == "3.14"

    def test_add_entity_invalid_type(self, graph_memory):
        with pytest.raises(ValueError, match="Invalid entity_type"):
            graph_memory.add_entity("foo", "invalid_type", "mem-1")

    def test_get_entity_not_found(self, graph_memory):
        assert graph_memory.get_entity("nonexistent") is None

    def test_add_relationship(self, graph_memory):
        graph_memory.add_entity("grimoire", "module", "mem-1")
        graph_memory.add_entity("chromadb", "technology", "mem-1")
        graph_memory.add_relationship(
            "grimoire", "chromadb", "uses", 0.9, "mem-1"
        )
        stats = graph_memory.get_entity_stats()
        assert stats["total_relationships"] == 1

    def test_add_relationship_invalid_type(self, graph_memory):
        graph_memory.add_entity("a", "concept", "m1")
        graph_memory.add_entity("b", "concept", "m1")
        with pytest.raises(ValueError, match="Invalid relation_type"):
            graph_memory.add_relationship("a", "b", "bogus", 0.5, "m1")

    def test_add_relationship_invalid_confidence(self, graph_memory):
        graph_memory.add_entity("a", "concept", "m1")
        graph_memory.add_entity("b", "concept", "m1")
        with pytest.raises(ValueError, match="Confidence"):
            graph_memory.add_relationship("a", "b", "uses", 1.5, "m1")

    def test_add_relationship_missing_source(self, graph_memory):
        graph_memory.add_entity("b", "concept", "m1")
        with pytest.raises(ValueError, match="Source entity"):
            graph_memory.add_relationship("missing", "b", "uses", 0.5, "m1")

    def test_add_relationship_missing_target(self, graph_memory):
        graph_memory.add_entity("a", "concept", "m1")
        with pytest.raises(ValueError, match="Target entity"):
            graph_memory.add_relationship("a", "missing", "uses", 0.5, "m1")

    def test_get_entity_stats_empty(self, graph_memory):
        stats = graph_memory.get_entity_stats()
        assert stats["total_entities"] == 0
        assert stats["total_relationships"] == 0
        assert stats["entities_by_type"] == {}
        assert stats["relationships_by_type"] == {}

    def test_get_entity_stats(self, graph_memory):
        graph_memory.add_entity("python", "technology", "m1")
        graph_memory.add_entity("ollama", "technology", "m1")
        graph_memory.add_entity("shadow", "module", "m1")
        graph_memory.add_entity("grimoire", "module", "m1")
        graph_memory.add_relationship("shadow", "grimoire", "uses", 0.9, "m1")
        graph_memory.add_relationship("grimoire", "python", "depends_on", 0.8, "m1")

        stats = graph_memory.get_entity_stats()
        assert stats["total_entities"] == 4
        assert stats["total_relationships"] == 2
        assert stats["entities_by_type"]["technology"] == 2
        assert stats["entities_by_type"]["module"] == 2
        assert stats["relationships_by_type"]["uses"] == 1
        assert stats["relationships_by_type"]["depends_on"] == 1

    def test_close_and_reopen(self, tmp_path):
        """Data persists across close/reopen."""
        db_path = str(tmp_path / "persist_test.db")
        g = GraphLayer(db_path)
        g.add_entity("python", "technology", "m1")
        g.close()

        g2 = GraphLayer(db_path)
        ent = g2.get_entity("python")
        assert ent is not None
        assert ent["name"] == "python"
        g2.close()


# ===========================================================================
# GraphLayer Traversal Tests
# ===========================================================================

class TestGraphLayerTraversal:
    """BFS traversal, path finding, and conflict detection."""

    def _build_chain(self, g):
        """Build: A -uses-> B -depends_on-> C -related_to-> D"""
        for name in ["a", "b", "c", "d"]:
            g.add_entity(name, "concept", "m1")
        g.add_relationship("a", "b", "uses", 0.9, "m1")
        g.add_relationship("b", "c", "depends_on", 0.8, "m1")
        g.add_relationship("c", "d", "related_to", 0.5, "m1")

    def test_query_neighbors_depth_1(self, graph_memory):
        self._build_chain(graph_memory)
        result = graph_memory.query_neighbors("a", max_depth=1)
        names = {r["name"] for r in result}
        assert "b" in names
        assert "c" not in names

    def test_query_neighbors_depth_2(self, graph_memory):
        self._build_chain(graph_memory)
        result = graph_memory.query_neighbors("a", max_depth=2)
        names = {r["name"] for r in result}
        assert "b" in names
        assert "c" in names
        assert "d" not in names

    def test_query_neighbors_depth_3(self, graph_memory):
        self._build_chain(graph_memory)
        result = graph_memory.query_neighbors("a", max_depth=3)
        names = {r["name"] for r in result}
        assert {"b", "c", "d"} == names

    def test_query_neighbors_with_relation_filter(self, graph_memory):
        self._build_chain(graph_memory)
        # Only follow "uses" edges from a
        result = graph_memory.query_neighbors(
            "a", max_depth=3, relation_filter=["uses"]
        )
        names = {r["name"] for r in result}
        assert "b" in names
        # b->c is depends_on, so c should NOT appear with uses-only filter
        assert "c" not in names

    def test_query_neighbors_nonexistent_entity(self, graph_memory):
        result = graph_memory.query_neighbors("nonexistent")
        assert result == []

    def test_query_neighbors_bidirectional(self, graph_memory):
        """Traversal follows edges in both directions."""
        graph_memory.add_entity("x", "concept", "m1")
        graph_memory.add_entity("y", "concept", "m1")
        graph_memory.add_relationship("x", "y", "uses", 0.9, "m1")
        # Starting from y should find x via incoming edge
        result = graph_memory.query_neighbors("y", max_depth=1)
        names = {r["name"] for r in result}
        assert "x" in names

    def test_query_path_exists(self, graph_memory):
        self._build_chain(graph_memory)
        path = graph_memory.query_path("a", "d", max_depth=4)
        assert path is not None
        assert path[0]["name"] == "a"
        assert path[-1]["name"] == "d"
        assert len(path) == 4  # a -> b -> c -> d

    def test_query_path_no_path(self, graph_memory):
        """No path between disconnected entities."""
        graph_memory.add_entity("x", "concept", "m1")
        graph_memory.add_entity("y", "concept", "m1")
        path = graph_memory.query_path("x", "y", max_depth=4)
        assert path is None

    def test_query_path_same_node(self, graph_memory):
        graph_memory.add_entity("x", "concept", "m1")
        path = graph_memory.query_path("x", "x")
        assert path is not None
        assert len(path) == 1
        assert path[0]["name"] == "x"

    def test_query_path_nonexistent_source(self, graph_memory):
        graph_memory.add_entity("x", "concept", "m1")
        assert graph_memory.query_path("nope", "x") is None

    def test_query_path_nonexistent_target(self, graph_memory):
        graph_memory.add_entity("x", "concept", "m1")
        assert graph_memory.query_path("x", "nope") is None

    def test_find_conflicts_contradicts(self, graph_memory):
        graph_memory.add_entity("claim_a", "concept", "m1")
        graph_memory.add_entity("claim_b", "concept", "m1")
        graph_memory.add_relationship(
            "claim_a", "claim_b", "contradicts", 0.8, "m1"
        )
        conflicts = graph_memory.find_conflicts("claim_a")
        assert len(conflicts) == 1
        assert conflicts[0]["relation_type"] == "contradicts"

    def test_find_conflicts_supersedes(self, graph_memory):
        graph_memory.add_entity("old", "concept", "m1")
        graph_memory.add_entity("new", "concept", "m2")
        graph_memory.add_relationship("new", "old", "supersedes", 0.9, "m2")
        conflicts = graph_memory.find_conflicts("old")
        assert len(conflicts) == 1
        assert conflicts[0]["relation_type"] == "supersedes"

    def test_find_conflicts_none(self, graph_memory):
        graph_memory.add_entity("safe", "concept", "m1")
        assert graph_memory.find_conflicts("safe") == []


# ===========================================================================
# GraphLayer Merge Tests
# ===========================================================================

class TestGraphLayerMerge:
    """Entity merging / deduplication."""

    def test_merge_redirects_edges(self, graph_memory):
        graph_memory.add_entity("py", "technology", "m1")
        graph_memory.add_entity("python", "technology", "m1")
        graph_memory.add_entity("grimoire", "module", "m1")
        graph_memory.add_relationship("grimoire", "py", "uses", 0.9, "m1")

        graph_memory.merge_entities(keep="python", remove="py")

        # "py" should be gone
        assert graph_memory.get_entity("py") is None
        # Edge should now point to "python"
        stats = graph_memory.get_entity_stats()
        assert stats["total_entities"] == 2
        assert stats["total_relationships"] == 1

    def test_merge_removes_self_loops(self, graph_memory):
        """If merging creates a self-loop, the edge is removed."""
        graph_memory.add_entity("a", "concept", "m1")
        graph_memory.add_entity("b", "concept", "m1")
        graph_memory.add_relationship("a", "b", "related_to", 0.5, "m1")
        graph_memory.merge_entities(keep="a", remove="b")
        stats = graph_memory.get_entity_stats()
        # Self-loop a->a should have been cleaned up
        assert stats["total_relationships"] == 0

    def test_merge_keep_not_found(self, graph_memory):
        graph_memory.add_entity("a", "concept", "m1")
        with pytest.raises(ValueError, match="Keep entity"):
            graph_memory.merge_entities("nonexistent", "a")

    def test_merge_remove_not_found(self, graph_memory):
        graph_memory.add_entity("a", "concept", "m1")
        with pytest.raises(ValueError, match="Remove entity"):
            graph_memory.merge_entities("a", "nonexistent")


# ===========================================================================
# EntityExtractor Tests
# ===========================================================================

class TestEntityExtractor:
    """Rule-based entity and relationship extraction."""

    def test_extract_module_names(self, extractor):
        text = "Grimoire stores memories and Wraith handles daily tasks."
        entities = extractor.extract_entities(text, "mem-1")
        names = {e["name"] for e in entities}
        assert "grimoire" in names
        assert "wraith" in names

    def test_extract_technology_names(self, extractor):
        text = "Shadow uses Python and Ollama for local inference."
        entities = extractor.extract_entities(text, "mem-1")
        names = {e["name"] for e in entities}
        assert "python" in names
        assert "ollama" in names
        assert "shadow" in names  # Also a module

    def test_extract_person_name(self, extractor):
        text = "Master Morstad created Shadow for personal use."
        entities = extractor.extract_entities(text, "mem-1")
        names = {e["name"] for e in entities}
        assert "master morstad" in names
        person_ent = [e for e in entities if e["name"] == "master morstad"][0]
        assert person_ent["entity_type"] == "person"

    def test_extract_proper_nouns(self, extractor):
        text = "The Quick Brown Fox jumped over Lazy Dog."
        entities = extractor.extract_entities(text, "mem-1")
        names = {e["name"] for e in entities}
        # "Quick Brown Fox" and "Lazy Dog" are multi-word capitalized
        assert "quick brown fox" in names
        assert "lazy dog" in names

    def test_extract_empty_text(self, extractor):
        assert extractor.extract_entities("", "mem-1") == []
        assert extractor.extract_entities("   ", "mem-1") == []

    def test_extract_no_entities(self, extractor):
        text = "the quick brown fox jumped over the lazy dog"
        entities = extractor.extract_entities(text, "mem-1")
        # No capitalized multi-word names, no known entities
        assert len(entities) == 0

    def test_extract_deduplicates(self, extractor):
        text = "Python uses Python and more Python."
        entities = extractor.extract_entities(text, "mem-1")
        python_ents = [e for e in entities if e["name"] == "python"]
        assert len(python_ents) == 1

    def test_extract_known_entity_confidence(self, extractor):
        text = "Grimoire is the memory module."
        entities = extractor.extract_entities(text, "mem-1")
        grim = [e for e in entities if e["name"] == "grimoire"][0]
        assert grim["confidence"] == 0.9

    def test_extract_proper_noun_confidence(self, extractor):
        text = "The Grand Design was impressive."
        entities = extractor.extract_entities(text, "mem-1")
        gd = [e for e in entities if e["name"] == "grand design"]
        assert len(gd) == 1
        assert gd[0]["confidence"] == 0.5

    def test_relationship_uses(self, extractor):
        text = "Grimoire uses ChromaDB for vector search."
        entities = extractor.extract_entities(text, "m1")
        rels = extractor.extract_relationships(text, entities)
        uses_rels = [r for r in rels if r["relation_type"] == "uses"]
        assert len(uses_rels) >= 1
        assert uses_rels[0]["source"] == "grimoire"
        assert uses_rels[0]["target"] == "chromadb"

    def test_relationship_depends_on(self, extractor):
        text = "Grimoire depends on SQLite for persistence."
        entities = extractor.extract_entities(text, "m1")
        rels = extractor.extract_relationships(text, entities)
        dep_rels = [r for r in rels if r["relation_type"] == "depends_on"]
        assert len(dep_rels) >= 1

    def test_relationship_supersedes(self, extractor):
        text = "ChromaDB replaces SQLite for vector storage."
        entities = extractor.extract_entities(text, "m1")
        rels = extractor.extract_relationships(text, entities)
        sup = [r for r in rels if r["relation_type"] == "supersedes"]
        assert len(sup) >= 1

    def test_relationship_proximity(self, extractor):
        text = "Grimoire and ChromaDB work together on vector search."
        entities = extractor.extract_entities(text, "m1")
        rels = extractor.extract_relationships(text, entities)
        # Should get at least a proximity-based related_to
        assert len(rels) >= 1

    def test_relationship_empty_text(self, extractor):
        assert extractor.extract_relationships("", []) == []

    def test_relationship_single_entity(self, extractor):
        """No relationships possible with only one entity."""
        text = "Python is great."
        entities = extractor.extract_entities(text, "m1")
        rels = extractor.extract_relationships(text, entities)
        assert rels == []

    def test_extract_from_memory_convenience(self, extractor):
        text = "Shadow uses Grimoire for memory storage."
        entities, rels = extractor.extract_from_memory(text, "mem-1", "general")
        assert len(entities) >= 2
        assert isinstance(rels, list)

    def test_extract_source_memory_id_propagated(self, extractor):
        text = "Cerberus monitors ethics."
        entities = extractor.extract_entities(text, "special-id-123")
        for e in entities:
            assert e["source_memory_id"] == "special-id-123"


# ===========================================================================
# Integration Tests — Grimoire + Graph Layer
# ===========================================================================

class TestGrimoireGraphIntegration:
    """Test that Grimoire wires graph layer into remember/recall paths."""

    def test_remember_stores_to_graph(self, grimoire):
        """remember() should extract entities and store them in graph."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Grimoire uses ChromaDB for vector search.",
                check_duplicates=False,
            )

        stats = grimoire._graph.get_entity_stats()
        assert stats["total_entities"] >= 2  # grimoire, chromadb at minimum

    def test_remember_stores_relationships(self, grimoire):
        """remember() should extract and store relationships."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Grimoire uses ChromaDB for vector search.",
                check_duplicates=False,
            )

        stats = grimoire._graph.get_entity_stats()
        assert stats["total_relationships"] >= 1

    def test_remember_graph_failure_doesnt_break(self, grimoire):
        """If graph layer raises, remember() still returns a memory ID."""
        # Break the graph layer
        grimoire._graph.conn.close()
        grimoire._graph.conn = None

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="This should still work despite graph failure.",
                check_duplicates=False,
            )

        assert mid is not None
        assert len(mid) == 36  # UUID format

    def test_remember_no_graph_layer(self, grimoire):
        """With _graph=None, remember() works as vector-only."""
        grimoire._graph = None
        grimoire._extractor = None

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Vector-only memory storage.",
                check_duplicates=False,
            )

        assert mid is not None

    def test_recall_graph_returns_neighbors(self, grimoire):
        """recall_graph should return graph neighbors and related memories."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Grimoire uses ChromaDB for vector search.",
                check_duplicates=False,
            )

        result = grimoire.recall_graph("grimoire", max_depth=1)
        assert "graph_path" in result
        assert "related_memories" in result
        assert len(result["graph_path"]) >= 1

    def test_recall_graph_no_graph_layer(self, grimoire):
        """recall_graph returns empty result when graph is None."""
        grimoire._graph = None
        result = grimoire.recall_graph("anything")
        assert result == {"graph_path": [], "related_memories": []}

    def test_recall_enriched_merges_results(self, grimoire):
        """recall_enriched combines vector + graph results."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Grimoire uses ChromaDB for vector search.",
                check_duplicates=False,
            )
            grimoire.remember(
                content="Reaper uses Grimoire to store research results.",
                check_duplicates=False,
            )

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            result = grimoire.recall_enriched("chromadb vector database")

        assert "vector_results" in result
        assert "graph_results" in result
        assert "merged" in result
        assert len(result["merged"]) >= len(result["vector_results"])

    def test_recall_enriched_no_graph_fallback(self, grimoire):
        """Without graph layer, recall_enriched returns vector-only."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Some test memory content.",
                check_duplicates=False,
            )

        grimoire._graph = None
        grimoire._extractor = None

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            result = grimoire.recall_enriched("test memory")

        assert result["graph_results"] == []
        assert result["merged"] == result["vector_results"]


# ===========================================================================
# Edge Case Tests
# ===========================================================================

class TestEdgeCases:
    """Edge cases for graph layer and extractor."""

    def test_special_characters_in_entity_name(self, graph_memory):
        graph_memory.add_entity("c++", "technology", "m1")
        ent = graph_memory.get_entity("c++")
        assert ent is not None
        assert ent["name"] == "c++"

    def test_very_long_entity_name(self, graph_memory):
        long_name = "a" * 1000
        graph_memory.add_entity(long_name, "concept", "m1")
        ent = graph_memory.get_entity(long_name)
        assert ent is not None

    def test_very_long_text_extraction(self, extractor):
        text = "Python is great. " * 10000
        entities = extractor.extract_entities(text, "m1")
        assert any(e["name"] == "python" for e in entities)

    def test_self_referential_edge_allowed(self, graph_memory):
        """Self-loops are technically allowed (entity references itself)."""
        graph_memory.add_entity("recursive", "concept", "m1")
        graph_memory.add_relationship(
            "recursive", "recursive", "related_to", 0.5, "m1"
        )
        stats = graph_memory.get_entity_stats()
        assert stats["total_relationships"] == 1

    def test_multiple_edges_between_same_pair(self, graph_memory):
        """Same entity pair can have multiple relationship types."""
        graph_memory.add_entity("a", "concept", "m1")
        graph_memory.add_entity("b", "concept", "m1")
        graph_memory.add_relationship("a", "b", "uses", 0.9, "m1")
        graph_memory.add_relationship("a", "b", "depends_on", 0.8, "m1")
        stats = graph_memory.get_entity_stats()
        assert stats["total_relationships"] == 2

    def test_all_valid_entity_types(self, graph_memory):
        """Every declared valid entity type can be used."""
        for i, etype in enumerate(sorted(VALID_ENTITY_TYPES)):
            graph_memory.add_entity(f"test_{i}", etype, "m1")
        stats = graph_memory.get_entity_stats()
        assert stats["total_entities"] == len(VALID_ENTITY_TYPES)

    def test_all_valid_relation_types(self, graph_memory):
        """Every declared valid relation type can be used."""
        graph_memory.add_entity("src", "concept", "m1")
        graph_memory.add_entity("tgt", "concept", "m1")
        for rtype in sorted(VALID_RELATION_TYPES):
            graph_memory.add_relationship("src", "tgt", rtype, 0.5, "m1")
        stats = graph_memory.get_entity_stats()
        assert stats["total_relationships"] == len(VALID_RELATION_TYPES)

    def test_confidence_boundary_zero(self, graph_memory):
        graph_memory.add_entity("a", "concept", "m1")
        graph_memory.add_entity("b", "concept", "m1")
        graph_memory.add_relationship("a", "b", "uses", 0.0, "m1")

    def test_confidence_boundary_one(self, graph_memory):
        graph_memory.add_entity("a", "concept", "m1")
        graph_memory.add_entity("b", "concept", "m1")
        graph_memory.add_relationship("a", "b", "uses", 1.0, "m1")

    def test_query_neighbors_isolated_node(self, graph_memory):
        """Node with no edges returns empty neighbors."""
        graph_memory.add_entity("lonely", "concept", "m1")
        result = graph_memory.query_neighbors("lonely")
        assert result == []

    def test_unicode_entity_name(self, graph_memory):
        graph_memory.add_entity("café", "location", "m1")
        ent = graph_memory.get_entity("café")
        assert ent is not None
        assert ent["name"] == "café"
