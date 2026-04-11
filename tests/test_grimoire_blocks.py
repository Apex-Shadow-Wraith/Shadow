"""
Tests for Grimoire Content Block Support
==========================================
Verifies structured content block storage and retrieval
as specified in the Unified Architecture doc Part IV.

These tests mock Ollama embeddings so they run without a live server.
"""

import json
import sqlite3
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from modules.grimoire.grimoire import (
    Grimoire,
    SOURCE_CONVERSATION,
    SOURCE_SYSTEM,
    TRUST_CONVERSATION,
    TRUST_USER_STATED,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _fake_embedding(text):
    """Deterministic fake embedding — 768-dim vector derived from text hash."""
    import hashlib
    h = hashlib.sha256(text.encode()).hexdigest()
    # Generate 768 floats from the hash (repeating as needed)
    nums = [int(h[i:i+2], 16) / 255.0 for i in range(0, len(h), 2)]
    return (nums * 24)[:768]  # 768 dimensions like nomic-embed-text


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
# Test: Store entry with multiple block types, retrieve, verify structure
# ---------------------------------------------------------------------------

class TestContentBlockStorage:
    def test_store_and_retrieve_blocks(self, grimoire):
        """Store an entry with multiple block types, recall it, verify structure."""
        blocks = [
            {"type": "text", "content": "Here's how to connect to the database:"},
            {"type": "code", "content": "conn = sqlite3.connect('shadow.db')", "language": "python"},
            {"type": "tool_use", "content": "Called database_query tool", "tool_name": "database_query"},
            {"type": "tool_result", "content": "Query returned 42 rows"},
            {"type": "error", "content": "Warning: table already exists"},
        ]

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            memory_id = grimoire.remember(
                content="Database connection tutorial with code example",
                source=SOURCE_CONVERSATION,
                category="tutorials",
                trust_level=TRUST_CONVERSATION,
                content_blocks=blocks,
                check_duplicates=False
            )

        # Verify stored in SQLite directly
        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT content_blocks FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        assert row is not None
        stored_blocks = json.loads(row["content_blocks"])
        assert len(stored_blocks) == 5
        assert stored_blocks[0]["type"] == "text"
        assert stored_blocks[1]["type"] == "code"
        assert stored_blocks[1]["language"] == "python"
        assert stored_blocks[2]["type"] == "tool_use"
        assert stored_blocks[3]["type"] == "tool_result"
        assert stored_blocks[4]["type"] == "error"

    def test_recall_returns_content_blocks(self, grimoire):
        """recall() should return content_blocks in the result dict."""
        blocks = [
            {"type": "text", "content": "Shadow uses Ollama for inference"},
            {"type": "code", "content": "ollama serve", "language": "bash"},
        ]

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Shadow uses Ollama for local inference",
                source=SOURCE_CONVERSATION,
                category="architecture",
                content_blocks=blocks,
                check_duplicates=False
            )

            results = grimoire.recall("what does Shadow use for inference?", n_results=5)

        assert len(results) >= 1
        result = results[0]
        assert "content_blocks" in result
        assert len(result["content_blocks"]) == 2
        assert result["content_blocks"][0]["type"] == "text"
        assert result["content_blocks"][1]["type"] == "code"
        assert result["content_blocks"][1]["language"] == "bash"

    def test_block_order_preserved(self, grimoire):
        """Content blocks must maintain their insertion order."""
        blocks = [
            {"type": "plan", "content": "Step 1: Research"},
            {"type": "approval", "content": "User approved the plan"},
            {"type": "text", "content": "Executing research phase"},
            {"type": "tool_use", "content": "web_search('AI safety')"},
            {"type": "tool_result", "content": "Found 15 results"},
            {"type": "correction", "content": "User corrected search scope"},
        ]

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            memory_id = grimoire.remember(
                content="Research pipeline execution",
                source=SOURCE_CONVERSATION,
                content_blocks=blocks,
                check_duplicates=False
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT content_blocks FROM memories WHERE id = ?", (memory_id,))
        stored = json.loads(cursor.fetchone()["content_blocks"])
        assert [b["type"] for b in stored] == [
            "plan", "approval", "text", "tool_use", "tool_result", "correction"
        ]


# ---------------------------------------------------------------------------
# Test: Search by block type returns correct entries
# ---------------------------------------------------------------------------

class TestBlockSearch:
    def test_search_by_code_blocks(self, grimoire):
        """memory_block_search('code') should return only entries with code blocks."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            # Entry with code blocks
            grimoire.remember(
                content="Python list comprehension example",
                source=SOURCE_CONVERSATION,
                content_blocks=[
                    {"type": "text", "content": "List comprehensions are concise"},
                    {"type": "code", "content": "[x*2 for x in range(10)]", "language": "python"},
                ],
                check_duplicates=False
            )

            # Entry without code blocks
            grimoire.remember(
                content="Shadow was created by Patrick",
                source=SOURCE_CONVERSATION,
                content_blocks=[
                    {"type": "text", "content": "Shadow was created by Patrick"},
                ],
                check_duplicates=False
            )

            # Entry with no content_blocks at all (legacy)
            grimoire.remember(
                content="Legacy memory with no blocks",
                source=SOURCE_CONVERSATION,
                check_duplicates=False
            )

        results = grimoire.memory_block_search("code")
        assert len(results) == 1
        assert results[0]["content"] == "Python list comprehension example"
        assert len(results[0]["matching_blocks"]) == 1
        assert results[0]["matching_blocks"][0]["language"] == "python"

    def test_search_by_error_blocks(self, grimoire):
        """memory_block_search('error') finds entries containing error blocks."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Failed deployment attempt",
                source=SOURCE_SYSTEM,
                content_blocks=[
                    {"type": "text", "content": "Attempted to deploy v2.1"},
                    {"type": "error", "content": "ConnectionError: timeout after 30s"},
                ],
                check_duplicates=False
            )
            grimoire.remember(
                content="Successful deployment",
                source=SOURCE_SYSTEM,
                content_blocks=[
                    {"type": "text", "content": "Deployed v2.2 successfully"},
                ],
                check_duplicates=False
            )

        results = grimoire.memory_block_search("error")
        assert len(results) == 1
        assert "Failed deployment" in results[0]["content"]

    def test_search_invalid_block_type_raises(self, grimoire):
        """memory_block_search with invalid type should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid block type"):
            grimoire.memory_block_search("invalid_type")

    def test_search_returns_empty_for_no_matches(self, grimoire):
        """memory_block_search returns empty list when no entries have that block type."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Just text here",
                source=SOURCE_CONVERSATION,
                content_blocks=[{"type": "text", "content": "Hello"}],
                check_duplicates=False
            )

        results = grimoire.memory_block_search("plan")
        assert results == []


# ---------------------------------------------------------------------------
# Test: Legacy entries without content_blocks still work
# ---------------------------------------------------------------------------

class TestLegacyCompatibility:
    def test_legacy_entry_recall_returns_text_block(self, grimoire):
        """Entries stored without content_blocks should return a single text block on recall."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="This is a legacy-style memory with no blocks",
                source=SOURCE_CONVERSATION,
                category="testing",
                check_duplicates=False
            )

            results = grimoire.recall("legacy memory", n_results=5)

        assert len(results) >= 1
        result = results[0]
        assert "content_blocks" in result
        assert len(result["content_blocks"]) == 1
        assert result["content_blocks"][0]["type"] == "text"
        assert result["content_blocks"][0]["content"] == result["content"]

    def test_legacy_entry_not_in_block_search(self, grimoire):
        """Legacy entries (NULL content_blocks) should not appear in block searches."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Legacy memory",
                source=SOURCE_CONVERSATION,
                check_duplicates=False
            )

        results = grimoire.memory_block_search("text")
        assert len(results) == 0

    def test_null_content_blocks_in_sqlite(self, grimoire):
        """Entries without content_blocks should have NULL in the database column."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            memory_id = grimoire.remember(
                content="No blocks provided",
                source=SOURCE_CONVERSATION,
                check_duplicates=False
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT content_blocks FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        assert row["content_blocks"] is None


# ---------------------------------------------------------------------------
# Test: Empty content_blocks handled gracefully
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_list_content_blocks(self, grimoire):
        """Passing an empty list for content_blocks stores '[]' and recall handles it."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            memory_id = grimoire.remember(
                content="Memory with empty blocks list",
                source=SOURCE_CONVERSATION,
                content_blocks=[],
                check_duplicates=False
            )

            results = grimoire.recall("empty blocks", n_results=5)

        assert len(results) >= 1
        # Empty list is stored as JSON "[]"
        assert results[0]["content_blocks"] == []

    def test_none_content_blocks_same_as_omitted(self, grimoire):
        """Explicitly passing None should behave the same as omitting content_blocks."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            memory_id = grimoire.remember(
                content="Explicit None blocks",
                source=SOURCE_CONVERSATION,
                content_blocks=None,
                check_duplicates=False
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT content_blocks FROM memories WHERE id = ?", (memory_id,))
        assert cursor.fetchone()["content_blocks"] is None

    def test_mixed_blocks_and_legacy_in_recall(self, grimoire):
        """Recalling multiple results — some with blocks, some without — works correctly."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="Memory alpha with blocks",
                source=SOURCE_CONVERSATION,
                content_blocks=[
                    {"type": "text", "content": "Alpha content"},
                    {"type": "code", "content": "print('alpha')"},
                ],
                check_duplicates=False
            )
            grimoire.remember(
                content="Memory beta without blocks",
                source=SOURCE_CONVERSATION,
                check_duplicates=False
            )

            results = grimoire.recall("memory", n_results=10)

        # Every result should have content_blocks regardless of how it was stored
        for result in results:
            assert "content_blocks" in result
            assert isinstance(result["content_blocks"], list)
            assert len(result["content_blocks"]) >= 1

    def test_content_blocks_with_all_valid_types(self, grimoire):
        """All 8 valid block types can be stored and retrieved."""
        all_types = ["text", "code", "tool_use", "tool_result",
                     "error", "plan", "approval", "correction"]
        blocks = [{"type": t, "content": f"Content for {t}"} for t in all_types]

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            memory_id = grimoire.remember(
                content="Memory with all block types",
                source=SOURCE_CONVERSATION,
                content_blocks=blocks,
                check_duplicates=False
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT content_blocks FROM memories WHERE id = ?", (memory_id,))
        stored = json.loads(cursor.fetchone()["content_blocks"])
        assert len(stored) == 8
        assert [b["type"] for b in stored] == all_types

        # Each type should be searchable
        for block_type in all_types:
            results = grimoire.memory_block_search(block_type)
            assert len(results) >= 1, f"Block type '{block_type}' not found in search"


# ---------------------------------------------------------------------------
# Test: remember() actually increases DB count (Session 34 bug fix)
# ---------------------------------------------------------------------------

class TestRememberDBCount:
    def test_remember_increases_chromadb_count(self, grimoire):
        """remember() must increase ChromaDB collection count by 1."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            before = grimoire.collection.count()
            grimoire.remember(
                content="Test memory for DB count verification",
                source=SOURCE_CONVERSATION,
                category="testing",
                check_duplicates=False,
            )
            after = grimoire.collection.count()

        assert after == before + 1, (
            f"ChromaDB count did not increase: before={before}, after={after}"
        )

    def test_remember_increases_sqlite_count(self, grimoire):
        """remember() must insert exactly one row into SQLite memories table."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            cursor = grimoire.conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM memories")
            before = cursor.fetchone()["cnt"]

            grimoire.remember(
                content="Test memory for SQLite count verification",
                source=SOURCE_CONVERSATION,
                category="testing",
                check_duplicates=False,
            )

            cursor.execute("SELECT COUNT(*) as cnt FROM memories")
            after = cursor.fetchone()["cnt"]

        assert after == before + 1, (
            f"SQLite count did not increase: before={before}, after={after}"
        )

    def test_remember_returns_valid_uuid(self, grimoire):
        """remember() must return a valid UUID string."""
        import uuid as uuid_mod
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            memory_id = grimoire.remember(
                content="Test memory for UUID validation",
                source=SOURCE_CONVERSATION,
                check_duplicates=False,
            )

        # Should not raise ValueError
        parsed = uuid_mod.UUID(memory_id)
        assert str(parsed) == memory_id

    def test_remember_embedding_failure_raises(self, grimoire):
        """remember() must propagate embedding errors, not swallow them."""
        with patch.object(grimoire, '_get_embedding',
                          side_effect=RuntimeError("Ollama not running")):
            with pytest.raises(RuntimeError, match="Ollama not running"):
                grimoire.remember(
                    content="This should fail",
                    source=SOURCE_CONVERSATION,
                    check_duplicates=False,
                )
