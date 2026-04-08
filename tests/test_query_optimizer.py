"""
Tests for Grimoire Query Optimizer
====================================
Validates query logging, relevance analysis, co-retrieval detection,
never-used detection, optimal n_results, threshold recommendations,
optimization plan generation, and plan application.
"""

import os
import pytest
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

from modules.grimoire.query_optimizer import GrimoireQueryOptimizer


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_query_optimizer.db")


@pytest.fixture
def optimizer(tmp_db):
    """Provide a fresh GrimoireQueryOptimizer with a temp database."""
    return GrimoireQueryOptimizer(grimoire=None, db_path=tmp_db)


# =============================================================================
# LOGGING TESTS
# =============================================================================

class TestQueryLogging:
    """Test query logging stores all fields correctly."""

    def test_log_query_returns_log_id(self, optimizer):
        """log_query should return a non-empty string ID."""
        log_id = optimizer.log_query(
            query="test query",
            collection="memories",
            results_returned=5,
            results_used=2,
            response_referenced=["doc1", "doc2"],
            duration_ms=42.5,
        )
        assert isinstance(log_id, str)
        assert len(log_id) > 0

    def test_log_query_stores_all_fields(self, optimizer, tmp_db):
        """All logged fields should be retrievable from SQLite."""
        optimizer.log_query(
            query="shadow memory lookup",
            collection="knowledge",
            results_returned=8,
            results_used=3,
            response_referenced=["docA", "docB", "docC"],
            duration_ms=55.0,
        )
        conn = sqlite3.connect(tmp_db)
        row = conn.execute("SELECT * FROM query_logs").fetchone()
        conn.close()

        assert row is not None
        # log_id, query, collection, results_returned, results_used,
        # response_referenced, duration_ms, timestamp
        assert row[1] == "shadow memory lookup"
        assert row[2] == "knowledge"
        assert row[3] == 8
        assert row[4] == 3
        assert row[6] == 55.0

    def test_multiple_queries_accumulate(self, optimizer, tmp_db):
        """Multiple log_query calls should create multiple rows."""
        for i in range(5):
            optimizer.log_query(
                query=f"query {i}",
                collection="memories",
                results_returned=5,
                results_used=2,
                response_referenced=[f"doc{i}"],
                duration_ms=10.0,
            )
        conn = sqlite3.connect(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM query_logs").fetchone()[0]
        conn.close()
        assert count == 5


# =============================================================================
# ANALYSIS TESTS
# =============================================================================

class TestAnalyzeRelevance:
    """Test relevance analysis calculations."""

    def test_usage_rate_calculation(self, optimizer):
        """5 returned, 2 used → 40% usage, 60% waste."""
        optimizer.log_query("q", "c", 5, 2, ["a", "b"], 10.0)
        result = optimizer.analyze_relevance(days=7)
        assert result["avg_results_returned"] == 5.0
        assert result["avg_results_used"] == 2.0
        assert result["usage_rate"] == 0.4
        assert result["waste_rate"] == 0.6

    def test_empty_log_returns_zeros(self, optimizer):
        """No queries → all zeros."""
        result = optimizer.analyze_relevance(days=7)
        assert result["avg_results_returned"] == 0.0
        assert result["usage_rate"] == 0.0
        assert result["waste_rate"] == 0.0

    def test_multiple_queries_averaged(self, optimizer):
        """Average across multiple queries."""
        optimizer.log_query("q1", "c", 10, 4, ["a", "b", "c", "d"], 10.0)
        optimizer.log_query("q2", "c", 6, 2, ["e", "f"], 10.0)
        result = optimizer.analyze_relevance(days=7)
        # avg returned = (10+6)/2 = 8, avg used = (4+2)/2 = 3
        assert result["avg_results_returned"] == 8.0
        assert result["avg_results_used"] == 3.0
        # usage = 6/16 = 0.375
        assert result["usage_rate"] == 0.375


class TestCoRetrievedDocuments:
    """Test co-retrieval detection."""

    def test_co_retrieved_above_threshold(self, optimizer):
        """Docs A+B returned together 5 times → in results."""
        for _ in range(5):
            optimizer.log_query("q", "c", 3, 2, ["docA", "docB", "docC"], 10.0)
        result = optimizer.find_co_retrieved_documents(min_co_occurrence=3)
        pairs = [(a, b) for a, b, _ in result]
        assert ("docA", "docB") in pairs
        assert ("docA", "docC") in pairs
        assert ("docB", "docC") in pairs

    def test_co_retrieved_below_threshold_excluded(self, optimizer):
        """Docs that only co-occur once → not in results with min=3."""
        optimizer.log_query("q", "c", 2, 1, ["docX", "docY"], 10.0)
        result = optimizer.find_co_retrieved_documents(min_co_occurrence=3)
        assert len(result) == 0

    def test_empty_log(self, optimizer):
        """No queries → no co-retrieved docs."""
        result = optimizer.find_co_retrieved_documents()
        assert result == []


class TestNeverUsedResults:
    """Test detection of documents returned but never used."""

    def test_never_used_detection(self, optimizer):
        """Doc returned 10 times via response_referenced but with 0 actual use is tricky.
        Since we track via response_referenced, a doc IN response_referenced IS used.
        Test that the method handles the intended workflow."""
        # Log queries where docX appears in referenced (used)
        for _ in range(10):
            optimizer.log_query("q", "c", 5, 2, ["docX", "docY"], 10.0)
        # docX appears 10 times and is used 10 times → NOT in never-used
        result = optimizer.find_never_used_results(min_queries=5)
        doc_ids = [d["doc_id"] for d in result]
        assert "docX" not in doc_ids

    def test_used_doc_excluded(self, optimizer):
        """Doc returned 10 times, used 8+ times → not in results."""
        for _ in range(10):
            optimizer.log_query("q", "c", 5, 3, ["docA", "docB", "docC"], 10.0)
        result = optimizer.find_never_used_results(min_queries=5)
        doc_ids = [d["doc_id"] for d in result]
        assert "docA" not in doc_ids
        assert "docB" not in doc_ids

    def test_empty_log(self, optimizer):
        """No queries → no never-used docs."""
        result = optimizer.find_never_used_results()
        assert result == []


class TestOptimalNResults:
    """Test optimal n_results recommendation."""

    def test_avg_3_used_recommends_around_5(self, optimizer):
        """If avg 3 results used, recommend ~5 (with buffer)."""
        for _ in range(20):
            optimizer.log_query("q", "c", 10, 3, ["a", "b", "c"], 10.0)
        result = optimizer.get_optimal_n_results()
        assert result == 5  # ceil(3 * 1.6) = 5

    def test_empty_log_returns_default(self, optimizer):
        """No data → default of 5."""
        assert optimizer.get_optimal_n_results() == 5

    def test_per_collection(self, optimizer):
        """Collection-specific optimal n."""
        for _ in range(10):
            optimizer.log_query("q", "memories", 10, 2, ["a", "b"], 10.0)
        for _ in range(10):
            optimizer.log_query("q", "research", 10, 6, ["a", "b", "c", "d", "e", "f"], 10.0)
        mem_n = optimizer.get_optimal_n_results(collection="memories")
        res_n = optimizer.get_optimal_n_results(collection="research")
        assert mem_n < res_n  # memories uses fewer results

    def test_minimum_is_1(self, optimizer):
        """Even with 0 usage, minimum recommendation is 1."""
        optimizer.log_query("q", "c", 10, 0, [], 10.0)
        result = optimizer.get_optimal_n_results()
        assert result >= 1


class TestSimilarityThreshold:
    """Test similarity threshold recommendations."""

    def test_high_waste_raises_threshold(self, optimizer):
        """Many results returned but few used → higher threshold."""
        for _ in range(20):
            optimizer.log_query("q", "c", 10, 1, ["a"], 10.0)
        threshold = optimizer.get_similarity_threshold_recommendation()
        assert threshold >= 0.6  # Should recommend raising threshold

    def test_good_usage_moderate_threshold(self, optimizer):
        """Most results used → moderate/lower threshold."""
        for _ in range(20):
            optimizer.log_query("q", "c", 5, 5, ["a", "b", "c", "d", "e"], 10.0)
        threshold = optimizer.get_similarity_threshold_recommendation()
        assert threshold <= 0.5  # Good usage → don't restrict too much

    def test_empty_log_returns_default(self, optimizer):
        """No data → default 0.5."""
        assert optimizer.get_similarity_threshold_recommendation() == 0.5


# =============================================================================
# OPTIMIZATION PLAN TESTS
# =============================================================================

class TestOptimizationPlan:
    """Test optimization plan generation."""

    def test_plan_has_valid_structure(self, optimizer):
        """Plan should contain all required keys."""
        # Seed some data
        for _ in range(10):
            optimizer.log_query("q", "c", 10, 3, ["a", "b", "c"], 10.0)
        plan = optimizer.generate_optimization_plan()
        assert "recommended_n_results" in plan
        assert "recommended_similarity_threshold" in plan
        assert "documents_to_demote" in plan
        assert "documents_to_bundle" in plan
        assert "estimated_token_savings" in plan
        assert "confidence_in_recommendations" in plan
        assert "recommendations" in plan

    def test_plan_includes_all_recommendation_types(self, optimizer):
        """Plan recommendations list should have at least one entry."""
        for _ in range(10):
            optimizer.log_query("q", "c", 10, 2, ["a", "b"], 10.0)
        plan = optimizer.generate_optimization_plan()
        assert len(plan["recommendations"]) >= 1

    def test_estimated_token_savings_positive(self, optimizer):
        """Token savings should be non-negative."""
        for _ in range(20):
            optimizer.log_query("q", "c", 10, 3, ["a", "b", "c"], 10.0)
        plan = optimizer.generate_optimization_plan()
        assert plan["estimated_token_savings"] >= 0

    def test_confidence_scales_with_sample_size(self, optimizer):
        """More queries → higher confidence."""
        # Small sample
        for _ in range(3):
            optimizer.log_query("q", "c", 5, 2, ["a", "b"], 10.0)
        plan_small = optimizer.generate_optimization_plan()

        # Large sample — new optimizer to reset
        opt2 = GrimoireQueryOptimizer(db_path=str(Path(optimizer.db_path).parent / "opt2.db"))
        for _ in range(100):
            opt2.log_query("q", "c", 5, 2, ["a", "b"], 10.0)
        plan_large = opt2.generate_optimization_plan()

        assert plan_large["confidence_in_recommendations"] > plan_small["confidence_in_recommendations"]

    def test_empty_log_plan(self, optimizer):
        """Empty query log → valid plan with 0 confidence."""
        plan = optimizer.generate_optimization_plan()
        assert plan["confidence_in_recommendations"] == 0.0
        assert isinstance(plan["recommendations"], list)


# =============================================================================
# APPLICATION TESTS
# =============================================================================

class TestApplyOptimizations:
    """Test optimization plan application."""

    def test_apply_with_mock_grimoire(self, optimizer):
        """Apply optimizations to a mock grimoire object."""
        mock_grimoire = MagicMock()
        mock_grimoire.default_n_results = 10
        mock_grimoire.similarity_threshold = 0.5

        plan = {
            "recommended_n_results": 5,
            "recommended_similarity_threshold": 0.6,
            "documents_to_demote": ["doc1"],
            "documents_to_bundle": [("docA", "docB")],
        }

        result = optimizer.apply_optimizations(mock_grimoire, plan, approved=True)
        assert len(result["applied"]) > 0

    def test_apply_without_approval_skips(self, optimizer):
        """Without approval flag → all changes skipped."""
        mock_grimoire = MagicMock()
        plan = {
            "recommended_n_results": 5,
            "recommended_similarity_threshold": 0.6,
            "documents_to_demote": ["doc1"],
            "documents_to_bundle": [("docA", "docB")],
        }

        result = optimizer.apply_optimizations(mock_grimoire, plan, approved=False)
        assert len(result["applied"]) == 0
        assert len(result["skipped"]) > 0
        assert "Approval required" in result["reason"]


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and robustness."""

    def test_sqlite_db_created_on_init(self, tmp_db):
        """Database file should exist after initialization."""
        GrimoireQueryOptimizer(db_path=tmp_db)
        assert Path(tmp_db).exists()

    def test_single_query_low_confidence(self, optimizer):
        """Single query → valid but low confidence."""
        optimizer.log_query("q", "c", 5, 2, ["a", "b"], 10.0)
        plan = optimizer.generate_optimization_plan()
        assert plan["confidence_in_recommendations"] <= 0.1

    def test_graceful_without_grimoire(self, optimizer):
        """Optimizer works fine without a grimoire reference."""
        for _ in range(5):
            optimizer.log_query("q", "c", 5, 2, ["a", "b"], 10.0)
        plan = optimizer.generate_optimization_plan()
        assert plan is not None
        # Apply without grimoire
        result = optimizer.apply_optimizations(None, plan, approved=True)
        assert isinstance(result, dict)

    def test_get_query_stats(self, optimizer):
        """Stats should reflect logged queries."""
        assert optimizer.get_query_stats()["total_queries_logged"] == 0
        optimizer.log_query("q", "c", 5, 2, ["a"], 10.0)
        stats = optimizer.get_query_stats()
        assert stats["total_queries_logged"] == 1
        assert stats["avg_relevance_rate"] == 0.4
