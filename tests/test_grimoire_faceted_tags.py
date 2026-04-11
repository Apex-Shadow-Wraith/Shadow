"""
Tests for Grimoire Faceted Multi-Dimensional Tagging (32C Item 7)
==================================================================
Verifies structured tag storage, auto-tagging heuristics, and
filtered recall across multiple tag dimensions.

These tests mock Ollama embeddings so they run without a live server.
"""

import json
import pytest
from unittest.mock import patch

from modules.grimoire.grimoire import (
    Grimoire,
    SOURCE_CONVERSATION,
    SOURCE_RESEARCH,
    TRUST_CONVERSATION,
    TRUST_USER_STATED,
    VALID_DOMAINS,
    VALID_CONTENT_TYPES,
    VALID_PHASES,
    VALID_TEMPORAL_RELEVANCE,
    FACETED_TAG_KEYS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _fake_embedding(text):
    """Deterministic fake embedding — 768-dim vector derived from text hash."""
    import hashlib
    h = hashlib.sha256(text.encode()).hexdigest()
    nums = [int(h[i:i+2], 16) / 255.0 for i in range(0, len(h), 2)]
    return (nums * 24)[:768]


@pytest.fixture
def grimoire(tmp_path):
    """Create a Grimoire instance with temp paths and mocked embeddings."""
    db_path = tmp_path / "test_memory.db"
    vector_path = tmp_path / "test_vectors"

    with patch.object(Grimoire, '_get_embedding', side_effect=_fake_embedding):
        g = Grimoire(
            db_path=str(db_path),
            vector_path=str(vector_path),
            ollama_url="http://localhost:11434",
            embed_model="nomic-embed-text"
        )
        yield g
        g.close()


# ---------------------------------------------------------------------------
# Test: Manual faceted tags stored and retrieved correctly
# ---------------------------------------------------------------------------

class TestManualFacetedTags:
    def test_manual_tags_stored_in_metadata(self, grimoire):
        """Manual faceted_tags dict is stored in SQLite metadata_json."""
        tags = {
            "domain": "code",
            "content_type": "procedure",
            "phase": "implementation",
            "temporal_relevance": "current",
            "entities": ["python", "chromadb"],
        }

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="How to initialize ChromaDB with persistent storage",
                faceted_tags=tags,
                check_duplicates=False,
            )

        # Verify in SQLite
        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT metadata_json FROM memories WHERE id = ?", (mid,))
        row = cursor.fetchone()
        meta = json.loads(row["metadata_json"])
        stored = meta["faceted_tags"]

        assert stored["domain"] == "code"
        assert stored["content_type"] == "procedure"
        assert stored["phase"] == "implementation"
        assert stored["temporal_relevance"] == "current"
        assert stored["entities"] == ["python", "chromadb"]

    def test_manual_tags_in_chromadb_metadata(self, grimoire):
        """Faceted tags are flattened into ChromaDB metadata with tag_ prefix."""
        tags = {
            "domain": "security",
            "content_type": "fact",
            "entities": ["firewall", "sentinel"],
        }

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Sentinel monitors firewall rules and network traffic",
                faceted_tags=tags,
                check_duplicates=False,
            )

        # Inspect ChromaDB metadata directly
        result = grimoire.collection.get(ids=[mid], include=["metadatas"])
        chroma_meta = result["metadatas"][0]

        assert chroma_meta["tag_domain"] == "security"
        assert chroma_meta["tag_content_type"] == "fact"
        assert chroma_meta["tag_entities"] == "firewall,sentinel"

    def test_invalid_domain_raises(self, grimoire):
        """Invalid faceted tag values are rejected with ValueError."""
        with pytest.raises(ValueError, match="Invalid faceted tag"):
            with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
                grimoire.remember(
                    content="Some content",
                    faceted_tags={"domain": "cooking"},
                    check_duplicates=False,
                )

    def test_invalid_content_type_raises(self, grimoire):
        """Invalid content_type value raises ValueError."""
        with pytest.raises(ValueError, match="Invalid faceted tag"):
            with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
                grimoire.remember(
                    content="Some content",
                    faceted_tags={"content_type": "poem"},
                    check_duplicates=False,
                )

    def test_unknown_keys_ignored(self, grimoire):
        """Unknown faceted tag keys are silently dropped."""
        tags = {
            "domain": "code",
            "flavor": "chocolate",  # Not a valid key
        }

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="def hello(): pass",
                faceted_tags=tags,
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT metadata_json FROM memories WHERE id = ?", (mid,))
        meta = json.loads(cursor.fetchone()["metadata_json"])
        stored = meta["faceted_tags"]

        assert "flavor" not in stored
        assert stored["domain"] == "code"


# ---------------------------------------------------------------------------
# Test: Auto-tagging heuristics
# ---------------------------------------------------------------------------

class TestAutoTagging:
    def test_auto_tag_code_content(self, grimoire):
        """Content with code patterns auto-tags as domain=code."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="def calculate_total(items): return sum(i.price for i in items)",
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT metadata_json FROM memories WHERE id = ?", (mid,))
        meta = json.loads(cursor.fetchone()["metadata_json"])
        assert meta["faceted_tags"]["domain"] == "code"
        assert meta["faceted_tags"]["content_type"] == "fact"

    def test_auto_tag_bible_content(self, grimoire):
        """Content with verse references auto-tags as domain=bible."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Romans 12:2 teaches us to be transformed by the renewing of our minds",
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT metadata_json FROM memories WHERE id = ?", (mid,))
        meta = json.loads(cursor.fetchone()["metadata_json"])
        assert meta["faceted_tags"]["domain"] == "bible"

    def test_auto_tag_business_content(self, grimoire):
        """Content with business terms auto-tags as domain=business."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Customer requested a quote for mowing the front lawn biweekly",
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT metadata_json FROM memories WHERE id = ?", (mid,))
        meta = json.loads(cursor.fetchone()["metadata_json"])
        assert meta["faceted_tags"]["domain"] == "business"

    def test_auto_tag_no_domain_match(self, grimoire):
        """Content that doesn't match any pattern gets content_type but no domain."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="The weather today is sunny and warm",
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT metadata_json FROM memories WHERE id = ?", (mid,))
        meta = json.loads(cursor.fetchone()["metadata_json"])
        assert "domain" not in meta["faceted_tags"]
        assert meta["faceted_tags"]["content_type"] == "fact"

    def test_manual_tags_override_auto(self, grimoire):
        """Explicit faceted_tags prevent auto-tagging from running."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="def mow_lawn(): pass",  # Would auto-tag as code
                faceted_tags={"domain": "business", "content_type": "procedure"},
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT metadata_json FROM memories WHERE id = ?", (mid,))
        meta = json.loads(cursor.fetchone()["metadata_json"])
        assert meta["faceted_tags"]["domain"] == "business"
        assert meta["faceted_tags"]["content_type"] == "procedure"


# ---------------------------------------------------------------------------
# Test: Recall with single tag filter
# ---------------------------------------------------------------------------

class TestRecallWithTagFilters:
    def test_recall_single_domain_filter(self, grimoire):
        """Recall with domain filter returns only matching entries."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="def connect_db(): return sqlite3.connect('test.db')",
                faceted_tags={"domain": "code", "content_type": "procedure"},
                check_duplicates=False,
            )
            grimoire.remember(
                content="Customer wants a quote for hedge trimming service",
                faceted_tags={"domain": "business", "content_type": "fact"},
                check_duplicates=False,
            )

            # Search with domain filter — should find code entry
            results = grimoire.recall(
                "database connection function",
                tag_filters={"domain": "code"},
            )

        assert len(results) >= 1
        for r in results:
            assert r["faceted_tags"].get("domain") == "code"

    def test_recall_multiple_tag_filters(self, grimoire):
        """Recall with multiple filters uses AND logic."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="class SecurityScanner: def scan_ports(self): pass",
                faceted_tags={
                    "domain": "code",
                    "content_type": "procedure",
                    "phase": "implementation",
                },
                check_duplicates=False,
            )
            grimoire.remember(
                content="Decided to use nmap for port scanning in Sentinel",
                faceted_tags={
                    "domain": "code",
                    "content_type": "decision",
                    "phase": "design",
                },
                check_duplicates=False,
            )

            # Filter: domain=code AND content_type=decision
            results = grimoire.recall(
                "port scanning",
                tag_filters={"domain": "code", "content_type": "decision"},
            )

        assert len(results) >= 1
        for r in results:
            assert r["faceted_tags"].get("domain") == "code"
            assert r["faceted_tags"].get("content_type") == "decision"

    def test_recall_no_filter_returns_all(self, grimoire):
        """Recall without tag_filters returns entries regardless of tags."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Shadow uses Ollama for model serving on localhost",
                faceted_tags={"domain": "ai_research"},
                check_duplicates=False,
            )
            grimoire.remember(
                content="Shadow runs Ollama on port 11434 by default",
                check_duplicates=False,
            )

            # No filter — should find both
            results = grimoire.recall("Ollama model serving")

        assert len(results) >= 1  # At least one match


# ---------------------------------------------------------------------------
# Test: Entities list round-trip
# ---------------------------------------------------------------------------

class TestEntitiesRoundTrip:
    def test_entities_stored_and_retrieved(self, grimoire):
        """Entities list survives storage → retrieval as a list of strings."""
        entities = ["python", "chromadb", "nomic-embed-text"]

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Shadow's embedding pipeline uses nomic-embed-text with ChromaDB",
                faceted_tags={"domain": "ai_research", "entities": entities},
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT metadata_json FROM memories WHERE id = ?", (mid,))
        meta = json.loads(cursor.fetchone()["metadata_json"])
        stored_entities = meta["faceted_tags"]["entities"]

        assert stored_entities == ["python", "chromadb", "nomic-embed-text"]

    def test_entities_string_normalised_to_list(self, grimoire):
        """Entities passed as comma-separated string are normalised to a list."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="RTX 5090 GPU with 32GB VRAM for local inference",
                faceted_tags={"domain": "hardware", "entities": "rtx5090, vram, gpu"},
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT metadata_json FROM memories WHERE id = ?", (mid,))
        meta = json.loads(cursor.fetchone()["metadata_json"])
        stored = meta["faceted_tags"]["entities"]

        assert isinstance(stored, list)
        assert "rtx5090" in stored
        assert "vram" in stored
        assert "gpu" in stored

    def test_entities_chromadb_comma_separated(self, grimoire):
        """Entities are stored comma-separated in ChromaDB metadata."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Phi4-mini handles local routing decisions",
                faceted_tags={"domain": "ai_research", "entities": ["phi4-mini", "ollama"]},
                check_duplicates=False,
            )

        result = grimoire.collection.get(ids=[mid], include=["metadatas"])
        assert result["metadatas"][0]["tag_entities"] == "phi4-mini,ollama"


# ---------------------------------------------------------------------------
# Test: Untagged entries still retrievable
# ---------------------------------------------------------------------------

class TestUntaggedEntries:
    def test_untagged_entry_still_found(self, grimoire):
        """Entries stored without faceted_tags are still returned by recall."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Shadow is a fully autonomous personal AI agent",
                faceted_tags=None,  # Will get auto-tagged
                check_duplicates=False,
            )

            results = grimoire.recall("autonomous AI agent")

        assert len(results) >= 1
        assert any(r["id"] == mid for r in results)

    def test_empty_faceted_tags_dict(self, grimoire):
        """Passing an empty dict for faceted_tags stores no tag dimensions."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Just a plain note with empty tags",
                faceted_tags={},
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT metadata_json FROM memories WHERE id = ?", (mid,))
        meta = json.loads(cursor.fetchone()["metadata_json"])
        # Empty faceted_tags dict — should not have the key at all or be empty
        assert meta.get("faceted_tags", {}) == {}


# ---------------------------------------------------------------------------
# Test: Static helper methods
# ---------------------------------------------------------------------------

class TestStaticHelpers:
    def test_validate_faceted_tags_valid(self):
        tags = {
            "domain": "code",
            "content_type": "procedure",
            "entities": ["python"],
            "phase": "testing",
            "temporal_relevance": "current",
        }
        result = Grimoire._validate_faceted_tags(tags)
        assert result["domain"] == "code"
        assert result["entities"] == ["python"]

    def test_validate_faceted_tags_none(self):
        assert Grimoire._validate_faceted_tags(None) == {}

    def test_validate_faceted_tags_empty(self):
        assert Grimoire._validate_faceted_tags({}) == {}

    def test_auto_tag_code(self):
        result = Grimoire._auto_tag("import os\nfrom pathlib import Path")
        assert result["domain"] == "code"

    def test_auto_tag_class(self):
        result = Grimoire._auto_tag("class MyRouter: pass")
        assert result["domain"] == "code"

    def test_auto_tag_bible_verse(self):
        result = Grimoire._auto_tag("Proverbs 3:5 says trust in the Lord")
        assert result["domain"] == "bible"

    def test_auto_tag_business(self):
        result = Grimoire._auto_tag("Need to send an invoice to the customer")
        assert result["domain"] == "business"

    def test_auto_tag_trim(self):
        result = Grimoire._auto_tag("Scheduled to trim the hedges on Friday")
        assert result["domain"] == "business"

    def test_auto_tag_generic(self):
        result = Grimoire._auto_tag("The sky is blue on a clear day")
        assert "domain" not in result
        assert result["content_type"] == "fact"

    def test_faceted_tags_to_chromadb(self):
        tags = {
            "domain": "code",
            "content_type": "fact",
            "entities": ["python", "sqlite"],
        }
        result = Grimoire._faceted_tags_to_chromadb(tags)
        assert result["tag_domain"] == "code"
        assert result["tag_content_type"] == "fact"
        assert result["tag_entities"] == "python,sqlite"

    def test_faceted_tags_to_chromadb_empty_entities(self):
        tags = {"domain": "general", "entities": []}
        result = Grimoire._faceted_tags_to_chromadb(tags)
        assert result["tag_entities"] == ""
        assert result["tag_domain"] == "general"
