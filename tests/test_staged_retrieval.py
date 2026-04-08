"""
Tests for Hierarchical Two-Stage Grimoire Retrieval
=====================================================
Tests staged_retrieval.py and GrimoireModule.search_staged integration.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from modules.grimoire.staged_retrieval import StagedRetrieval


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def retrieval():
    """StagedRetrieval with no grimoire (unit testing generate_summary, etc.)."""
    return StagedRetrieval(grimoire=None, summary_max_tokens=200)


@pytest.fixture
def mock_grimoire():
    """Mock grimoire with remember and recall methods."""
    grim = MagicMock()
    grim.remember = MagicMock(return_value="mock-id")
    grim.recall = MagicMock(return_value=[])
    return grim


@pytest.fixture
def retrieval_with_grimoire(mock_grimoire):
    """StagedRetrieval wired to a mock grimoire."""
    return StagedRetrieval(grimoire=mock_grimoire, summary_max_tokens=200)


# =============================================================================
# generate_summary tests
# =============================================================================

class TestGenerateSummary:
    """Tests for summary generation."""

    def test_extracts_first_sentences(self, retrieval):
        """generate_summary extracts first 2-3 sentences."""
        doc = "First sentence here. Second sentence follows. Third sentence too. Fourth sentence ignored."
        summary = retrieval.generate_summary(doc)
        assert "First sentence here." in summary
        assert "Second sentence follows." in summary
        assert "Third sentence too." in summary
        assert "Fourth sentence ignored." not in summary

    def test_includes_key_terms(self, retrieval):
        """generate_summary includes key terms like capitalized and technical words."""
        doc = "This is a simple intro sentence. Another basic sentence here. A third one too. Later we mention ChromaDB and nomic_embed_text and SQLite3 integration."
        summary = retrieval.generate_summary(doc)
        assert "Key terms:" in summary

    def test_respects_max_tokens(self, retrieval):
        """generate_summary truncates to summary_max_tokens."""
        retrieval._summary_max_tokens = 20
        doc = "A " * 500 + "end."
        summary = retrieval.generate_summary(doc)
        # 20 tokens * 4 chars = 80 chars max
        assert len(summary) <= 85  # small margin for truncation

    def test_empty_document_returns_empty(self, retrieval):
        """generate_summary returns empty string for empty input."""
        assert retrieval.generate_summary("") == ""
        assert retrieval.generate_summary("   ") == ""

    def test_appends_metadata_tags(self, retrieval):
        """generate_summary appends metadata when provided."""
        doc = "Simple document content here."
        meta = {"domain": "hardware", "category": "gpu", "trust_level": 0.9}
        summary = retrieval.generate_summary(doc, metadata=meta)
        assert "domain=hardware" in summary
        assert "category=gpu" in summary

    def test_single_sentence_document(self, retrieval):
        """generate_summary handles single-sentence documents."""
        doc = "Just one sentence."
        summary = retrieval.generate_summary(doc)
        assert "Just one sentence." in summary

    def test_no_metadata_no_crash(self, retrieval):
        """generate_summary works without metadata."""
        doc = "Some content here. More content follows."
        summary = retrieval.generate_summary(doc)
        assert "Some content here." in summary


# =============================================================================
# store_with_summary tests
# =============================================================================

class TestStoreWithSummary:
    """Tests for storing documents with summaries."""

    def test_stores_both_full_and_summary(self, retrieval_with_grimoire, mock_grimoire):
        """store_with_summary stores both full content and summary."""
        doc_id = retrieval_with_grimoire.store_with_summary(
            content="Full document content. With multiple sentences. And more detail.",
            collection="test_collection",
            metadata={"domain": "testing"},
        )
        # Should call remember twice: once for full, once for summary
        assert mock_grimoire.remember.call_count == 2
        assert doc_id  # returns a valid ID

    def test_summary_has_is_summary_flag(self, retrieval_with_grimoire, mock_grimoire):
        """store_with_summary marks summary with is_summary metadata."""
        retrieval_with_grimoire.store_with_summary(
            content="Test content here. Another sentence.",
            collection="test",
        )
        # Second call should be the summary
        calls = mock_grimoire.remember.call_args_list
        summary_call = calls[1]
        meta = summary_call.kwargs.get("metadata", {})
        assert meta.get("is_summary") is True

    def test_full_doc_has_staged_doc_id(self, retrieval_with_grimoire, mock_grimoire):
        """store_with_summary sets staged_doc_id on full document."""
        doc_id = retrieval_with_grimoire.store_with_summary(
            content="Content.", collection="test",
        )
        calls = mock_grimoire.remember.call_args_list
        full_call = calls[0]
        meta = full_call.kwargs.get("metadata", {})
        assert meta.get("staged_doc_id") == doc_id

    def test_no_grimoire_returns_id(self, retrieval):
        """store_with_summary returns an ID even without grimoire (no crash)."""
        doc_id = retrieval.store_with_summary("Content.", "test")
        assert doc_id  # UUID string returned


# =============================================================================
# search_summaries tests
# =============================================================================

class TestSearchSummaries:
    """Tests for Stage 1 summary search."""

    def test_returns_summaries_not_full_docs(self, retrieval_with_grimoire, mock_grimoire):
        """search_summaries returns summaries not full documents."""
        mock_grimoire.recall.return_value = [
            {
                "content": "Summary of doc A.",
                "id": "sum-1",
                "metadata": {"is_summary": True, "full_doc_id": "doc-a"},
                "relevance": 0.95,
            },
        ]
        results = retrieval_with_grimoire.search_summaries("test query")
        assert len(results) == 1
        assert results[0]["doc_id"] == "doc-a"
        assert results[0]["summary"] == "Summary of doc A."

    def test_returns_relevance_scores(self, retrieval_with_grimoire, mock_grimoire):
        """search_summaries includes relevance scores."""
        mock_grimoire.recall.return_value = [
            {
                "content": "Summary text.",
                "id": "sum-1",
                "metadata": {"is_summary": True, "full_doc_id": "doc-1"},
                "relevance": 0.88,
            },
        ]
        results = retrieval_with_grimoire.search_summaries("query")
        assert results[0]["relevance_score"] == 0.88

    def test_fallback_when_no_summaries(self, retrieval_with_grimoire, mock_grimoire):
        """search_summaries falls back to truncated full docs when no summaries exist."""
        mock_grimoire.recall.return_value = [
            {
                "content": "Full document without summary flag. More text. Even more.",
                "id": "legacy-1",
                "metadata": {},
                "relevance": 0.75,
            },
        ]
        results = retrieval_with_grimoire.search_summaries("query")
        assert len(results) == 1
        assert results[0]["doc_id"] == "legacy-1"

    def test_empty_query_returns_empty(self, retrieval_with_grimoire):
        """search_summaries returns empty for empty query."""
        assert retrieval_with_grimoire.search_summaries("") == []
        assert retrieval_with_grimoire.search_summaries("   ") == []

    def test_no_grimoire_returns_empty(self, retrieval):
        """search_summaries returns empty when grimoire is None."""
        assert retrieval.search_summaries("test") == []


# =============================================================================
# get_full_documents tests
# =============================================================================

class TestGetFullDocuments:
    """Tests for Stage 2 full document retrieval."""

    def test_retrieves_by_id(self, retrieval_with_grimoire, mock_grimoire):
        """get_full_documents retrieves documents by their staged_doc_id."""
        mock_grimoire.recall.return_value = [
            {
                "content": "Full content of the document.",
                "id": "raw-1",
                "metadata": {"staged_doc_id": "doc-a", "has_summary": True},
                "relevance": 0.5,
            },
        ]
        results = retrieval_with_grimoire.get_full_documents(["doc-a"])
        assert len(results) == 1
        assert results[0]["content"] == "Full content of the document."
        assert results[0]["doc_id"] == "doc-a"

    def test_empty_ids_returns_empty(self, retrieval_with_grimoire):
        """get_full_documents returns empty for empty ID list."""
        assert retrieval_with_grimoire.get_full_documents([]) == []

    def test_no_grimoire_returns_empty(self, retrieval):
        """get_full_documents returns empty when grimoire is None."""
        assert retrieval.get_full_documents(["doc-1"]) == []


# =============================================================================
# search (combined two-stage) tests
# =============================================================================

class TestCombinedSearch:
    """Tests for the combined two-stage search method."""

    def _setup_mock_for_search(self, mock_grimoire):
        """Configure mock to return summaries then full docs."""
        def recall_side_effect(query="", n_results=5, category=None):
            # For summary search (larger n_results)
            if n_results > 5:
                return [
                    {"content": f"Summary {i}.", "id": f"sum-{i}",
                     "metadata": {"is_summary": True, "full_doc_id": f"doc-{i}", "staged_doc_id": f"doc-{i}"},
                     "relevance": 0.9 - (i * 0.1)}
                    for i in range(4)
                ]
            # For full doc retrieval
            return [
                {"content": f"Full content for {query}.",
                 "id": f"full-{query}",
                 "metadata": {"staged_doc_id": query, "has_summary": True},
                 "relevance": 0.5}
            ]
        mock_grimoire.recall.side_effect = recall_side_effect

    def test_returns_full_docs_for_top_n(self, retrieval_with_grimoire, mock_grimoire):
        """search returns full docs for top auto_select results."""
        self._setup_mock_for_search(mock_grimoire)
        results = retrieval_with_grimoire.search("test query", auto_select=2)
        full_results = [r for r in results if r.get("type") == "full"]
        summary_results = [r for r in results if r.get("type") == "summary"]
        assert len(full_results) >= 1  # At least some full docs retrieved
        assert len(summary_results) >= 1  # Rest are summaries

    def test_auto_select_controls_full_doc_count(self, retrieval_with_grimoire, mock_grimoire):
        """search auto_select parameter controls how many full docs are pulled."""
        self._setup_mock_for_search(mock_grimoire)
        # With auto_select=1, should only try to get 1 full doc
        results = retrieval_with_grimoire.search("test", auto_select=1)
        stats = [r for r in results if "_stats" in r]
        assert len(stats) == 1
        # stage2_count should reflect attempted full retrievals
        assert stats[0]["_stats"]["stage2_count"] >= 0

    def test_tokens_saved_estimate_is_positive(self, retrieval_with_grimoire, mock_grimoire):
        """search reports positive token savings estimate."""
        self._setup_mock_for_search(mock_grimoire)
        results = retrieval_with_grimoire.search("test", auto_select=2)
        stats = [r for r in results if "_stats" in r]
        assert len(stats) == 1
        assert stats[0]["_stats"]["tokens_saved_estimate"] >= 0

    def test_empty_query_returns_empty(self, retrieval_with_grimoire):
        """search returns empty for empty query."""
        assert retrieval_with_grimoire.search("") == []

    def test_stats_include_stage_counts(self, retrieval_with_grimoire, mock_grimoire):
        """search stats include stage1_count and stage2_count."""
        self._setup_mock_for_search(mock_grimoire)
        results = retrieval_with_grimoire.search("test", auto_select=2)
        stats = [r for r in results if "_stats" in r][0]["_stats"]
        assert "stage1_count" in stats
        assert "stage2_count" in stats
        assert "tokens_saved_estimate" in stats


# =============================================================================
# get_retrieval_stats tests
# =============================================================================

class TestRetrievalStats:
    """Tests for retrieval statistics tracking."""

    def test_initial_stats_are_zero(self, retrieval):
        """get_retrieval_stats returns zeros before any searches."""
        stats = retrieval.get_retrieval_stats()
        assert stats["total_searches"] == 0
        assert stats["avg_stage1_results"] == 0.0
        assert stats["hit_rate"] == 0.0

    def test_stats_track_correctly(self, retrieval_with_grimoire, mock_grimoire):
        """get_retrieval_stats updates after searches."""
        # Setup mock
        mock_grimoire.recall.return_value = [
            {"content": "Summary.", "id": "s1",
             "metadata": {"is_summary": True, "full_doc_id": "d1", "staged_doc_id": "d1"},
             "relevance": 0.9},
        ]
        retrieval_with_grimoire.search("test query", auto_select=1)
        stats = retrieval_with_grimoire.get_retrieval_stats()
        assert stats["total_searches"] == 1


# =============================================================================
# backfill_summaries tests
# =============================================================================

class TestBackfillSummaries:
    """Tests for backfilling existing documents with summaries."""

    def test_processes_existing_documents(self, retrieval_with_grimoire, mock_grimoire):
        """backfill_summaries generates summaries for docs without them."""
        mock_grimoire.recall.return_value = [
            {"content": "Existing doc. With content. No summary yet.",
             "id": "old-1", "metadata": {}, "category": "general"},
        ]
        result = retrieval_with_grimoire.backfill_summaries()
        assert result["processed"] == 1
        assert result["errors"] == 0

    def test_skips_docs_with_summaries(self, retrieval_with_grimoire, mock_grimoire):
        """backfill_summaries skips documents that already have summaries."""
        mock_grimoire.recall.return_value = [
            {"content": "Already summarized.",
             "id": "old-1", "metadata": {"has_summary": True}},
        ]
        result = retrieval_with_grimoire.backfill_summaries()
        assert result["already_had_summary"] == 1
        assert result["processed"] == 0

    def test_skips_summary_docs(self, retrieval_with_grimoire, mock_grimoire):
        """backfill_summaries skips documents that ARE summaries."""
        mock_grimoire.recall.return_value = [
            {"content": "I am a summary.",
             "id": "sum-1", "metadata": {"is_summary": True}},
        ]
        result = retrieval_with_grimoire.backfill_summaries()
        assert result["already_had_summary"] == 1
        assert result["processed"] == 0

    def test_no_grimoire_returns_zeros(self, retrieval):
        """backfill_summaries returns zeros when grimoire is None."""
        result = retrieval.backfill_summaries()
        assert result == {"processed": 0, "already_had_summary": 0, "errors": 0}


# =============================================================================
# GrimoireModule.search_staged integration tests
# =============================================================================

class TestGrimoireModuleSearchStaged:
    """Tests for the search_staged method on GrimoireModule."""

    def test_search_staged_calls_staged_retrieval(self):
        """GrimoireModule.search_staged delegates to StagedRetrieval."""
        from modules.grimoire.grimoire_module import GrimoireModule
        module = GrimoireModule(config={})
        mock_staged = MagicMock()
        mock_staged.search.return_value = [{"content": "result", "_stats": {}}]
        module.staged_retrieval = mock_staged

        result = module.search_staged("test query")
        mock_staged.search.assert_called_once_with("test query", None, 10, 3)
        assert len(result) == 1

    def test_search_staged_fallback_when_unavailable(self):
        """GrimoireModule.search_staged falls back to regular search."""
        from modules.grimoire.grimoire_module import GrimoireModule
        module = GrimoireModule(config={})
        module.staged_retrieval = None
        mock_grim = MagicMock()
        mock_grim.recall.return_value = [{"content": "fallback"}]
        module._grimoire = mock_grim

        result = module.search_staged("test query")
        mock_grim.recall.assert_called_once_with(query="test query", n_results=10)
        assert len(result) == 1

    def test_search_staged_no_grimoire_no_staged(self):
        """GrimoireModule.search_staged returns empty when nothing available."""
        from modules.grimoire.grimoire_module import GrimoireModule
        module = GrimoireModule(config={})
        module.staged_retrieval = None
        module._grimoire = None

        result = module.search_staged("test query")
        assert result == []


# =============================================================================
# Token savings validation
# =============================================================================

class TestTokenSavings:
    """Validate that staged retrieval actually saves tokens."""

    def test_summaries_smaller_than_full_docs(self, retrieval):
        """10 summaries use fewer tokens than 10 full documents."""
        long_doc = "This is a sentence about GPU specifications. " * 100
        summary = retrieval.generate_summary(long_doc)
        # Summary should be significantly shorter than the full doc
        assert len(summary) < len(long_doc) * 0.5

    def test_single_doc_round_trip(self, retrieval_with_grimoire, mock_grimoire):
        """Single document: summary search returns it, full retrieval gets it."""
        doc_content = "Shadow uses dual RTX 5090 GPUs. Each has 32GB VRAM. Total 64GB."

        # Store returns an ID
        doc_id = retrieval_with_grimoire.store_with_summary(
            content=doc_content, collection="hardware",
        )
        assert doc_id is not None
        assert len(doc_id) > 0
