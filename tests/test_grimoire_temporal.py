"""
Tests for Grimoire Temporal Validity (32C Item 5)
===================================================
Verifies time-aware metadata on Grimoire entries: valid_from, valid_until,
superseded_by, temporal ranking in recall, supersede() method, and
get_temporal_stats().

These tests mock Ollama embeddings so they run without a live server.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from modules.grimoire.grimoire import (
    Grimoire,
    SOURCE_CONVERSATION,
    SOURCE_USER_STATED,
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
# Test: remember() stores temporal metadata
# ---------------------------------------------------------------------------

class TestRememberTemporal:
    def test_valid_from_defaults_to_now(self, grimoire):
        """When valid_from is not provided, it defaults to approximately now."""
        before = datetime.now().isoformat()

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Shadow uses Ollama for local inference",
                check_duplicates=False,
            )

        after = datetime.now().isoformat()

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT valid_from FROM memories WHERE id = ?", (mid,))
        row = cursor.fetchone()
        assert row["valid_from"] is not None
        assert before <= row["valid_from"] <= after

    def test_valid_until_stored(self, grimoire):
        """Explicit valid_until is stored in the database."""
        expiry = (datetime.now() + timedelta(days=30)).isoformat()

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="GPU prices expected to drop by Q3 2026",
                valid_until=expiry,
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT valid_until FROM memories WHERE id = ?", (mid,))
        row = cursor.fetchone()
        assert row["valid_until"] == expiry

    def test_valid_until_null_by_default(self, grimoire):
        """When valid_until is not provided, it is NULL (never expires)."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Biblical values are central to Shadow's ethics",
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT valid_until FROM memories WHERE id = ?", (mid,))
        row = cursor.fetchone()
        assert row["valid_until"] is None

    def test_explicit_valid_from(self, grimoire):
        """Explicit valid_from is stored as-is."""
        custom_from = "2026-01-01T00:00:00"

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="New year resolution memory",
                valid_from=custom_from,
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT valid_from FROM memories WHERE id = ?", (mid,))
        row = cursor.fetchone()
        assert row["valid_from"] == custom_from

    def test_supersedes_links_old_to_new(self, grimoire):
        """When supersedes is set, the old entry's superseded_by points to new."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            old_id = grimoire.remember(
                content="Shadow uses Ollama 0.4.x",
                check_duplicates=False,
            )
            new_id = grimoire.remember(
                content="Shadow uses Ollama 0.5.x",
                supersedes=old_id,
                check_duplicates=False,
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT superseded_by FROM memories WHERE id = ?", (old_id,))
        row = cursor.fetchone()
        assert row["superseded_by"] == new_id


# ---------------------------------------------------------------------------
# Test: recall() temporal ranking
# ---------------------------------------------------------------------------

class TestRecallTemporal:
    def test_expired_entries_hidden_by_default(self, grimoire):
        """Expired entries are not returned when include_expired=False (default)."""
        past = (datetime.now() - timedelta(days=1)).isoformat()

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            expired_id = grimoire.remember(
                content="Flash sale ends tomorrow on RTX 5090",
                valid_until=past,
                check_duplicates=False,
            )
            active_id = grimoire.remember(
                content="RTX 5090 standard retail price is $1999",
                check_duplicates=False,
            )

            results = grimoire.recall("RTX 5090 price")

        result_ids = [r["id"] for r in results]
        assert active_id in result_ids
        assert expired_id not in result_ids

    def test_expired_entries_included_when_requested(self, grimoire):
        """include_expired=True returns expired entries with deprioritized scores."""
        past = (datetime.now() - timedelta(days=1)).isoformat()

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            expired_id = grimoire.remember(
                content="Temporary discount on GPU cooling fans",
                valid_until=past,
                check_duplicates=False,
            )

            results = grimoire.recall(
                "GPU cooling fan discount",
                include_expired=True,
            )

        result_ids = [r["id"] for r in results]
        assert expired_id in result_ids

        expired_result = next(r for r in results if r["id"] == expired_id)
        assert expired_result["temporal_status"] == "expired"

    def test_expired_entries_deprioritized(self, grimoire):
        """Expired entries get relevance * 0.5 compared to active entries."""
        past = (datetime.now() - timedelta(days=1)).isoformat()

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            # Use identical content so they get the same base relevance
            expired_id = grimoire.remember(
                content="Shadow hardware specifications and GPU details for inference",
                valid_until=past,
                check_duplicates=False,
            )
            active_id = grimoire.remember(
                content="Shadow hardware specifications and GPU info for inference",
                check_duplicates=False,
            )

            results = grimoire.recall(
                "Shadow hardware specifications and GPU details for inference",
                include_expired=True,
                n_results=10,
            )

        # Both should be returned
        expired_result = next((r for r in results if r["id"] == expired_id), None)
        active_result = next((r for r in results if r["id"] == active_id), None)

        assert expired_result is not None
        assert active_result is not None
        # Active entry should rank higher
        assert active_result["relevance"] > expired_result["relevance"]

    def test_superseded_entries_hidden_by_default(self, grimoire):
        """Superseded entries are not returned when include_superseded=False."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            old_id = grimoire.remember(
                content="Shadow runs on a single RTX 4090 GPU",
                check_duplicates=False,
            )
            new_id = grimoire.remember(
                content="Shadow runs on dual RTX 5090 GPUs",
                supersedes=old_id,
                check_duplicates=False,
            )

            results = grimoire.recall("Shadow GPU setup")

        result_ids = [r["id"] for r in results]
        assert new_id in result_ids
        assert old_id not in result_ids

    def test_superseded_entries_included_when_requested(self, grimoire):
        """include_superseded=True returns superseded entries."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            old_id = grimoire.remember(
                content="Shadow uses Python 3.12 for all modules",
                check_duplicates=False,
            )
            new_id = grimoire.remember(
                content="Shadow uses Python 3.14 for all modules",
                supersedes=old_id,
                check_duplicates=False,
            )

            results = grimoire.recall(
                "Shadow Python version",
                include_superseded=True,
            )

        result_ids = [r["id"] for r in results]
        assert old_id in result_ids
        superseded_result = next(r for r in results if r["id"] == old_id)
        assert superseded_result["temporal_status"] == "superseded"
        assert superseded_result["superseded_by"] == new_id

    def test_superseded_entries_deprioritized(self, grimoire):
        """Superseded entries get relevance * 0.3."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            old_id = grimoire.remember(
                content="Ollama model runtime configuration and setup guide",
                check_duplicates=False,
            )
            new_id = grimoire.remember(
                content="Ollama model runtime configuration and setup instructions",
                supersedes=old_id,
                check_duplicates=False,
            )

            results = grimoire.recall(
                "Ollama model runtime configuration and setup guide",
                include_superseded=True,
                n_results=10,
            )

        old_result = next((r for r in results if r["id"] == old_id), None)
        new_result = next((r for r in results if r["id"] == new_id), None)

        assert old_result is not None
        assert new_result is not None
        # New (active) entry should rank much higher than superseded
        assert new_result["relevance"] > old_result["relevance"]

    def test_active_entry_has_full_relevance(self, grimoire):
        """Active entries (not expired, not superseded) get temporal_status='active'."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Cerberus handles all safety checks for Shadow",
                check_duplicates=False,
            )

            results = grimoire.recall("Cerberus safety checks")

        assert len(results) >= 1
        result = next(r for r in results if r["id"] == mid)
        assert result["temporal_status"] == "active"


# ---------------------------------------------------------------------------
# Test: supersede() method
# ---------------------------------------------------------------------------

class TestSupersede:
    def test_supersede_creates_new_and_links(self, grimoire):
        """supersede() creates a new entry and sets superseded_by on old."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            old_id = grimoire.remember(
                content="Shadow's embedding model is nomic-embed-text v1",
                category="software",
                check_duplicates=False,
            )

            new_id = grimoire.supersede(
                old_id,
                "Shadow's embedding model is nomic-embed-text v1.5",
            )

        assert new_id != old_id

        cursor = grimoire.conn.cursor()

        # Old entry should point to new
        cursor.execute("SELECT superseded_by FROM memories WHERE id = ?", (old_id,))
        assert cursor.fetchone()["superseded_by"] == new_id

        # New entry should exist and be active
        cursor.execute(
            "SELECT is_active, category FROM memories WHERE id = ?", (new_id,)
        )
        new_row = cursor.fetchone()
        assert new_row["is_active"] == 1
        # Inherits category from old entry
        assert new_row["category"] == "software"

    def test_supersede_nonexistent_raises(self, grimoire):
        """supersede() raises ValueError for a nonexistent old_id."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            with pytest.raises(ValueError, match="Memory not found"):
                grimoire.supersede("nonexistent-uuid", "new content")

    def test_supersede_with_kwargs(self, grimoire):
        """supersede() passes extra kwargs to remember()."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            old_id = grimoire.remember(
                content="LMN scheduling notes for Q1",
                category="business",
                check_duplicates=False,
            )

            new_id = grimoire.supersede(
                old_id,
                "LMN scheduling notes for Q2",
                trust_level=TRUST_USER_STATED,
                tags=["lmn", "scheduling"],
            )

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT trust_level FROM memories WHERE id = ?", (new_id,))
        assert cursor.fetchone()["trust_level"] == TRUST_USER_STATED


# ---------------------------------------------------------------------------
# Test: get_temporal_stats()
# ---------------------------------------------------------------------------

class TestTemporalStats:
    def test_all_active(self, grimoire):
        """Stats with only active entries."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(content="Active memory one", check_duplicates=False)
            grimoire.remember(content="Active memory two", check_duplicates=False)

        stats = grimoire.get_temporal_stats()
        assert stats["active_count"] == 2
        assert stats["expired_count"] == 0
        assert stats["superseded_count"] == 0
        assert stats["entries_expiring_soon"] == []

    def test_expired_count(self, grimoire):
        """Expired entries are counted correctly."""
        past = (datetime.now() - timedelta(days=1)).isoformat()

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            grimoire.remember(
                content="This deal expired yesterday",
                valid_until=past,
                check_duplicates=False,
            )
            grimoire.remember(content="This is still valid", check_duplicates=False)

        stats = grimoire.get_temporal_stats()
        assert stats["expired_count"] == 1
        assert stats["active_count"] == 1

    def test_superseded_count(self, grimoire):
        """Superseded entries are counted correctly."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            old_id = grimoire.remember(
                content="Old version info",
                check_duplicates=False,
            )
            grimoire.supersede(old_id, "New version info")

        stats = grimoire.get_temporal_stats()
        assert stats["superseded_count"] == 1
        # The new entry is active, old is superseded
        assert stats["active_count"] == 1

    def test_entries_expiring_soon(self, grimoire):
        """Entries expiring within 7 days appear in entries_expiring_soon."""
        soon = (datetime.now() + timedelta(days=3)).isoformat()
        far = (datetime.now() + timedelta(days=30)).isoformat()

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            soon_id = grimoire.remember(
                content="Expiring soon memory",
                valid_until=soon,
                check_duplicates=False,
            )
            grimoire.remember(
                content="Far future memory",
                valid_until=far,
                check_duplicates=False,
            )

        stats = grimoire.get_temporal_stats()
        expiring_ids = [e["id"] for e in stats["entries_expiring_soon"]]
        assert soon_id in expiring_ids
        assert len(stats["entries_expiring_soon"]) == 1


# ---------------------------------------------------------------------------
# Test: Expired entries are NEVER deleted (perfect recall preserved)
# ---------------------------------------------------------------------------

class TestPerfectRecall:
    def test_expired_entries_still_in_db(self, grimoire):
        """Expired entries remain in SQLite — they are never hard-deleted."""
        past = (datetime.now() - timedelta(days=30)).isoformat()

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Old seasonal pricing from last month",
                valid_until=past,
                check_duplicates=False,
            )

        # Verify the entry is still in the database
        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (mid,))
        row = cursor.fetchone()
        assert row is not None
        assert row["content"] == "Old seasonal pricing from last month"
        assert row["is_active"] == 1  # NOT soft-deleted, just expired

    def test_superseded_entries_still_in_db(self, grimoire):
        """Superseded entries remain in SQLite — they are never hard-deleted."""
        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            old_id = grimoire.remember(
                content="Original architecture notes v1",
                check_duplicates=False,
            )
            grimoire.supersede(old_id, "Updated architecture notes v2")

        cursor = grimoire.conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (old_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["content"] == "Original architecture notes v1"
        assert row["is_active"] == 1  # Still active in DB, just superseded

    def test_expired_retrievable_with_include_flag(self, grimoire):
        """Expired entries can always be retrieved with include_expired=True."""
        past = (datetime.now() - timedelta(days=365)).isoformat()

        with patch.object(grimoire, '_get_embedding', side_effect=_fake_embedding):
            mid = grimoire.remember(
                content="Very old memory from a year ago about GPU benchmarks",
                valid_until=past,
                check_duplicates=False,
            )

            # Without flag — should NOT appear
            results_default = grimoire.recall("GPU benchmarks")
            assert mid not in [r["id"] for r in results_default]

            # With flag — SHOULD appear
            results_explicit = grimoire.recall(
                "GPU benchmarks",
                include_expired=True,
            )
            assert mid in [r["id"] for r in results_explicit]
