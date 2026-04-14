"""
Tests for Reaper query reformulation logic.
"""

import pytest
from unittest.mock import patch, MagicMock

from modules.reaper.reaper import (
    _simplify_query,
    _broaden_query,
    _results_relevant,
    _extract_search_query,
    _FILLER_WORDS,
    _MAX_QUERY_LENGTH,
)


# =============================================================================
# Unit tests for reformulation helpers
# =============================================================================

class TestSimplifyQuery:
    """Test filler word stripping."""

    def test_strips_filler_words(self):
        result = _simplify_query("what are the latest landscaping trends in Alabama")
        assert result == "landscaping trends alabama"

    def test_returns_none_when_no_filler(self):
        assert _simplify_query("landscaping trends Alabama") is None

    def test_returns_none_when_all_filler(self):
        assert _simplify_query("what is the") is None

    def test_preserves_core_words(self):
        result = _simplify_query("how to install python packages")
        assert "install" in result
        assert "python" in result
        assert "packages" in result


class TestBroadenQuery:
    """Test most-specific-term removal."""

    def test_removes_last_word(self):
        assert _broaden_query("landscaping trends Alabama") == "landscaping trends"

    def test_returns_none_for_single_word(self):
        assert _broaden_query("landscaping") is None

    def test_two_words_to_one(self):
        assert _broaden_query("python packages") == "python"


class TestResultsRelevant:
    """Test relevance checking."""

    def test_empty_results_not_relevant(self):
        assert _results_relevant([], "landscaping") is False

    def test_relevant_when_keyword_in_title(self):
        results = [{"title": "Top landscaping tips", "snippet": ""}]
        assert _results_relevant(results, "landscaping tips") is True

    def test_relevant_when_keyword_in_snippet(self):
        results = [{"title": "Article", "snippet": "Best landscaping practices"}]
        assert _results_relevant(results, "landscaping practices") is True

    def test_not_relevant_when_no_keyword_match(self):
        results = [{"title": "Cooking recipes", "snippet": "How to bake bread"}]
        assert _results_relevant(results, "landscaping trends Alabama") is False

    def test_short_words_ignored(self):
        """Words <= 2 chars are skipped during relevance check."""
        results = [{"title": "AI news", "snippet": "updates"}]
        # "AI" is only 2 chars, should be skipped; returns True since no evaluable keywords
        assert _results_relevant(results, "AI") is True


class TestExtractSearchQuery:
    """Test pre-search keyword extraction for long queries."""

    def test_short_query_unchanged(self):
        """Queries under the length threshold pass through unchanged."""
        q = "best mulch for landscaping"
        assert _extract_search_query(q) == q

    def test_exact_threshold_unchanged(self):
        """Query exactly at the threshold passes through."""
        q = "x" * _MAX_QUERY_LENGTH
        assert _extract_search_query(q) == q

    def test_long_benchmark_query_shortened(self):
        """Benchmark-style query with embedded context gets trimmed."""
        q = (
            "Given these search results about mulch types: 'Hardwood mulch "
            "decomposes slowly and is great for perennial beds' — What mulch "
            "should a landscaper recommend?"
        )
        result = _extract_search_query(q)
        assert len(result) <= _MAX_QUERY_LENGTH
        assert "mulch" in result.lower()

    def test_quoted_passage_removed(self):
        """Long quoted passages inside the query are stripped."""
        q = (
            "Based on this info: 'Cedar mulch repels insects and lasts for "
            "years in hot climates but costs more per cubic yard' — "
            "which mulch is cheapest?"
        )
        result = _extract_search_query(q)
        assert "repels insects" not in result
        assert len(result) <= _MAX_QUERY_LENGTH

    def test_given_preamble_stripped(self):
        """'Given ... :' preamble clauses are removed."""
        q = (
            "Given the following research data about irrigation efficiency: "
            "What irrigation method saves the most water for residential lawns?"
        )
        result = _extract_search_query(q)
        assert len(result) < len(q)
        assert "irrigation" in result.lower()

    def test_plain_long_question_gets_keywords(self):
        """A plain long question without context markers still gets shortened."""
        q = (
            "What are the very best and most popular types of ornamental "
            "grasses that landscapers should consider planting in the "
            "southeastern United States during the spring season?"
        )
        result = _extract_search_query(q)
        assert len(result) <= _MAX_QUERY_LENGTH
        # Should preserve substantive words
        assert "ornamental" in result.lower() or "grasses" in result.lower()

    def test_returns_string_not_none(self):
        """Always returns a string, never None."""
        q = "a" * 200
        result = _extract_search_query(q)
        assert isinstance(result, str)
        assert len(result) > 0


# =============================================================================
# Integration tests for Reaper.search reformulation
# =============================================================================

class TestSearchReformulation:
    """Test that Reaper.search triggers reformulation correctly."""

    def _make_reaper(self):
        """Create a Reaper with mocked grimoire and no live backends."""
        from modules.reaper.reaper import Reaper
        mock_grimoire = MagicMock()
        with patch.object(Reaper, '__init__', lambda self, *a, **kw: None):
            reaper = Reaper.__new__(Reaper)
            reaper.grimoire = mock_grimoire
            reaper.searxng_available = False
            reaper.ddg_available = True
            reaper.bing_available = False
            reaper.data_dir = "data/research"
        return reaper

    def test_good_results_no_reformulation(self):
        """Results with keyword matches pass through without reformulation."""
        reaper = self._make_reaper()
        good_results = [
            {"title": "Landscaping trends 2026", "url": "https://example.com",
             "snippet": "Top landscaping trends", "engine": "duckduckgo",
             "source_eval": {}}
        ]
        with patch.object(reaper, '_search_once', return_value=good_results):
            results = reaper.search("landscaping trends")

        assert len(results) == 1
        assert results[0]["_reformulation"]["was_reformulated"] is False
        assert results[0]["_reformulation"]["original_query"] == "landscaping trends"

    def test_zero_results_triggers_reformulation(self):
        """Empty results trigger simplification retry."""
        reaper = self._make_reaper()
        good_results = [
            {"title": "Landscaping tips", "url": "https://example.com",
             "snippet": "landscaping advice", "engine": "duckduckgo",
             "source_eval": {}}
        ]
        # First call returns nothing, second returns results
        with patch.object(reaper, '_search_once', side_effect=[[], good_results]):
            results = reaper.search("what are the best landscaping tips")

        assert len(results) == 1
        assert results[0]["_reformulation"]["was_reformulated"] is True
        assert results[0]["_reformulation"]["original_query"] == "what are the best landscaping tips"

    def test_max_two_retries(self):
        """Reformulation attempts are capped at 2."""
        reaper = self._make_reaper()
        call_count = 0
        original_search_once = reaper._search_once.__func__ if hasattr(reaper._search_once, '__func__') else None

        def counting_search(query, max_results=10):
            nonlocal call_count
            call_count += 1
            return []

        with patch.object(reaper, '_search_once', side_effect=counting_search):
            results = reaper.search("what are the latest landscaping trends in Alabama")

        # Original + max 2 retries = at most 3 calls
        assert call_count <= 3

    def test_original_query_preserved_in_metadata(self):
        """Original query is always in reformulation metadata."""
        reaper = self._make_reaper()
        retry_results = [
            {"title": "Trends overview", "url": "https://example.com",
             "snippet": "trends data", "engine": "duckduckgo",
             "source_eval": {}}
        ]
        with patch.object(reaper, '_search_once', side_effect=[[], retry_results]):
            results = reaper.search("what are the latest landscaping trends in Alabama")

        meta = results[0]["_reformulation"]
        assert meta["original_query"] == "what are the latest landscaping trends in Alabama"
        assert meta["was_reformulated"] is True

    def test_long_query_extracted_before_first_search(self):
        """Long benchmark-style queries are shortened before the first search call."""
        reaper = self._make_reaper()
        good_results = [
            {"title": "Mulch guide for landscapers", "url": "https://example.com",
             "snippet": "mulch recommendations", "engine": "duckduckgo",
             "source_eval": {}}
        ]
        queries_searched = []

        def tracking_search(query, max_results=10):
            queries_searched.append(query)
            return good_results

        long_query = (
            "Given these search results about mulch types: 'Hardwood mulch "
            "decomposes slowly and is great for perennial beds' — What mulch "
            "should a landscaper recommend?"
        )
        with patch.object(reaper, '_search_once', side_effect=tracking_search):
            results = reaper.search(long_query)

        # The first search should NOT be the full 200+ char query
        assert len(queries_searched[0]) <= _MAX_QUERY_LENGTH
        assert "mulch" in queries_searched[0].lower()
        # Original query preserved in metadata
        assert results[0]["_reformulation"]["original_query"] == long_query

    def test_low_relevance_triggers_reformulation(self):
        """Results with no keyword overlap trigger reformulation."""
        reaper = self._make_reaper()
        irrelevant = [
            {"title": "Cooking recipes", "url": "https://example.com",
             "snippet": "How to bake", "engine": "duckduckgo",
             "source_eval": {}}
        ]
        relevant = [
            {"title": "Python install guide", "url": "https://example.com",
             "snippet": "Install python packages", "engine": "duckduckgo",
             "source_eval": {}}
        ]
        with patch.object(reaper, '_search_once', side_effect=[irrelevant, relevant]):
            results = reaper.search("how to install python packages")

        assert results[0]["_reformulation"]["was_reformulated"] is True
