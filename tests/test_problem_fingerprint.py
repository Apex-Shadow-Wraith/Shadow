"""Tests for Problem Fingerprinting — cross-domain solution transfer via structural shape."""

import pytest
from unittest.mock import MagicMock, patch

from modules.shadow.problem_fingerprint import (
    ProblemFingerprinter,
    ProblemFingerprint,
    PROBLEM_SHAPES,
    SHAPE_KEYWORDS,
)


@pytest.fixture
def fingerprinter():
    """Fingerprinter with no Grimoire."""
    return ProblemFingerprinter()


@pytest.fixture
def mock_grimoire():
    """Mock Grimoire for testing storage/retrieval."""
    grim = MagicMock()
    grim.remember.return_value = "test-doc-id-123"
    grim.recall.return_value = []
    return grim


@pytest.fixture
def fingerprinter_with_grimoire(mock_grimoire):
    """Fingerprinter with mock Grimoire."""
    return ProblemFingerprinter(grimoire=mock_grimoire)


# ── Fingerprinting: primary shape detection ──

class TestPrimaryShapeDetection:
    """Test that tasks are classified to the correct primary shape."""

    def test_optimization_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Optimize this function for speed")
        assert fp.primary_shape == "optimization"

    def test_transformation_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Convert JSON to CSV")
        assert fp.primary_shape == "transformation"

    def test_search_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Find all users matching criteria")
        assert fp.primary_shape == "search"

    def test_diagnosis_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Debug this error")
        assert fp.primary_shape == "diagnosis"

    def test_comparison_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Compare React vs Vue")
        assert fp.primary_shape == "comparison"

    def test_scheduling_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Schedule 5 jobs across 2 crews")
        assert fp.primary_shape == "scheduling"

    def test_verification_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Verify that all tests pass")
        assert fp.primary_shape == "verification"

    def test_repair_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Fix and repair the authentication patch")
        assert fp.primary_shape == "repair"

    def test_aggregation_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Summarize and combine these reports")
        assert fp.primary_shape == "aggregation"

    def test_decomposition_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Break down this monolith into microservices")
        assert fp.primary_shape == "decomposition"

    def test_classification_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Classify these emails into categories")
        assert fp.primary_shape == "classification"

    def test_generation_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Generate a new API client")
        assert fp.primary_shape == "generation"

    def test_mapping_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Map these database fields to the API response")
        assert fp.primary_shape == "mapping"

    def test_constraint_satisfaction_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Find a configuration that satisfies all constraint requirements")
        assert fp.primary_shape == "constraint_satisfaction"


# ── Multi-faceted tasks ──

class TestSecondaryShapes:
    """Test that multi-faceted tasks get primary + secondary shapes."""

    def test_multi_shape_task(self, fingerprinter):
        fp = fingerprinter.fingerprint("Find and optimize the slow database query")
        assert fp.primary_shape in ("search", "optimization")
        assert len(fp.secondary_shapes) >= 1

    def test_secondary_shapes_are_list(self, fingerprinter):
        fp = fingerprinter.fingerprint("Convert, compare, and verify the data format")
        assert isinstance(fp.secondary_shapes, list)
        assert len(fp.secondary_shapes) >= 1


# ── Input/output type detection ──

class TestIOTypeDetection:
    """Test input/output type detection."""

    def test_code_input_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Optimize this Python function and class")
        assert fp.input_type == "code"

    def test_data_input_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Convert this CSV table with rows and columns")
        assert fp.input_type == "data"

    def test_text_output_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Write an essay about distributed systems")
        assert fp.output_type == "text"

    def test_decision_output_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Should I choose React or Vue? Recommend one.")
        assert fp.output_type == "decision"


# ── Complexity indicators ──

class TestComplexityIndicators:
    """Test complexity indicator detection."""

    def test_multi_step_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("First parse the data, then transform it, after that validate")
        assert "multi-step" in fp.complexity_indicators

    def test_iterative_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Repeat the optimization loop until convergence")
        assert "iterative" in fp.complexity_indicators

    def test_recursive_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Solve each recursive sub-problem independently")
        assert "recursive" in fp.complexity_indicators

    def test_parallel_detected(self, fingerprinter):
        fp = fingerprinter.fingerprint("Process these tasks in parallel simultaneously")
        assert "parallel" in fp.complexity_indicators


# ── Fingerprint hash ──

class TestFingerprintHash:
    """Test fingerprint hash properties."""

    def test_same_shape_same_hash(self, fingerprinter):
        """Same primary shape + same indicators/constraints → same hash."""
        fp1 = fingerprinter.fingerprint("Optimize this for efficiency")
        fp2 = fingerprinter.fingerprint("Optimize that for efficiency")
        assert fp1.fingerprint_hash == fp2.fingerprint_hash

    def test_different_shape_different_hash(self, fingerprinter):
        fp1 = fingerprinter.fingerprint("Optimize this function for speed")
        fp2 = fingerprinter.fingerprint("Convert JSON to CSV format")
        assert fp1.fingerprint_hash != fp2.fingerprint_hash

    def test_hash_is_deterministic(self, fingerprinter):
        fp1 = fingerprinter.fingerprint("Debug this error in the code")
        fp2 = fingerprinter.fingerprint("Debug this error in the code")
        assert fp1.fingerprint_hash == fp2.fingerprint_hash

    def test_hash_is_nonempty_string(self, fingerprinter):
        fp = fingerprinter.fingerprint("Do something")
        assert isinstance(fp.fingerprint_hash, str)
        assert len(fp.fingerprint_hash) > 0


# ── Grimoire integration: find_similar_solutions ──

class TestFindSimilarSolutions:
    """Test searching for solutions with matching fingerprints."""

    def test_returns_empty_without_grimoire(self, fingerprinter):
        fp = fingerprinter.fingerprint("Optimize something")
        results = fingerprinter.find_similar_solutions(fp)
        assert results == []

    def test_cross_domain_match(self, fingerprinter_with_grimoire, mock_grimoire):
        """Optimization in CUDA should match optimization in database."""
        mock_grimoire.recall.return_value = [
            {
                "id": "cuda-opt-1",
                "content": "CUDA memory coalescing optimization",
                "metadata": {
                    "primary_shape": "optimization",
                    "fingerprint_hash": "abc123",
                    "domain": "gpu",
                },
                "trust_level": 0.9,
                "relevance": 0.85,
            }
        ]
        fp = fingerprinter_with_grimoire.fingerprint("Optimize database index for faster queries")
        results = fingerprinter_with_grimoire.find_similar_solutions(fp)
        assert len(results) >= 1
        assert results[0]["id"] == "cuda-opt-1"

    def test_respects_n_results(self, fingerprinter_with_grimoire, mock_grimoire):
        mock_grimoire.recall.return_value = [
            {"id": f"sol-{i}", "content": f"Solution {i}", "metadata": {}} for i in range(10)
        ]
        fp = fingerprinter_with_grimoire.fingerprint("Find something")
        results = fingerprinter_with_grimoire.find_similar_solutions(fp, n_results=3)
        assert len(results) <= 3

    def test_handles_grimoire_error(self, fingerprinter_with_grimoire, mock_grimoire):
        mock_grimoire.recall.side_effect = Exception("DB error")
        fp = fingerprinter_with_grimoire.fingerprint("Optimize something")
        results = fingerprinter_with_grimoire.find_similar_solutions(fp)
        assert results == []


# ── Grimoire integration: store_with_fingerprint ──

class TestStoreWithFingerprint:
    """Test storing solutions with fingerprint metadata."""

    def test_stores_with_correct_metadata(self, fingerprinter_with_grimoire, mock_grimoire):
        fp = fingerprinter_with_grimoire.fingerprint("Optimize database queries")
        doc_id = fingerprinter_with_grimoire.store_with_fingerprint(
            solution="Use covering indexes to avoid table scans",
            task="Optimize database queries",
            fingerprint=fp,
        )
        assert doc_id == "test-doc-id-123"
        mock_grimoire.remember.assert_called_once()
        call_kwargs = mock_grimoire.remember.call_args[1]
        assert call_kwargs["category"] == "fingerprinted_solution"
        assert call_kwargs["metadata"]["primary_shape"] == "optimization"
        assert call_kwargs["metadata"]["fingerprint_hash"] == fp.fingerprint_hash
        assert "fingerprinted" in call_kwargs["tags"]

    def test_returns_empty_without_grimoire(self, fingerprinter):
        fp = fingerprinter.fingerprint("Something")
        doc_id = fingerprinter.store_with_fingerprint("solution", "task", fp)
        assert doc_id == ""

    def test_uses_override_grimoire(self, fingerprinter):
        override = MagicMock()
        override.remember.return_value = "override-id"
        fp = fingerprinter.fingerprint("Something")
        doc_id = fingerprinter.store_with_fingerprint("solution", "task", fp, grimoire=override)
        assert doc_id == "override-id"
        override.remember.assert_called_once()

    def test_handles_store_error(self, fingerprinter_with_grimoire, mock_grimoire):
        mock_grimoire.remember.side_effect = Exception("Write error")
        fp = fingerprinter_with_grimoire.fingerprint("Something")
        doc_id = fingerprinter_with_grimoire.store_with_fingerprint("solution", "task", fp)
        assert doc_id == ""


# ── get_cross_domain_matches ──

class TestCrossDomainMatches:
    """Test the convenience method for cross-domain solution discovery."""

    def test_filters_to_different_domain(self, fingerprinter_with_grimoire, mock_grimoire):
        mock_grimoire.recall.return_value = [
            {
                "id": "gpu-sol",
                "content": "GPU optimization via memory coalescing",
                "metadata": {"primary_shape": "optimization", "domain": "gpu"},
                "relevance": 0.9,
            },
            {
                "id": "db-sol",
                "content": "Database optimization via indexing",
                "metadata": {"primary_shape": "optimization", "domain": "database"},
                "relevance": 0.8,
            },
        ]
        # Task is about database, so GPU match is cross-domain
        results = fingerprinter_with_grimoire.get_cross_domain_matches(
            "Optimize this database query for faster retrieval"
        )
        domains = [r["metadata"]["domain"] for r in results]
        # Should NOT include database (same domain)
        assert "database" not in domains
        # Should include gpu (cross-domain)
        assert "gpu" in domains

    def test_includes_adaptation_hint(self, fingerprinter_with_grimoire, mock_grimoire):
        mock_grimoire.recall.return_value = [
            {
                "id": "net-sol",
                "content": "Network packet scheduling with priority queues",
                "metadata": {"primary_shape": "scheduling", "domain": "networking"},
                "relevance": 0.9,
            },
        ]
        results = fingerprinter_with_grimoire.get_cross_domain_matches(
            "Schedule 5 landscaping jobs across 2 crews this week"
        )
        if results:
            assert "adaptation_hint" in results[0]
            assert "scheduling" in results[0]["adaptation_hint"]


# ── Edge cases ──

class TestEdgeCases:
    """Test edge cases and graceful degradation."""

    def test_no_matching_keywords_defaults_to_generation(self, fingerprinter):
        fp = fingerprinter.fingerprint("xyzzy plugh")
        assert fp.primary_shape == "generation"

    def test_very_short_task(self, fingerprinter):
        fp = fingerprinter.fingerprint("hi")
        assert isinstance(fp, ProblemFingerprint)
        assert fp.primary_shape in PROBLEM_SHAPES

    def test_empty_task(self, fingerprinter):
        fp = fingerprinter.fingerprint("")
        assert isinstance(fp, ProblemFingerprint)
        assert fp.primary_shape == "generation"
        assert fp.fingerprint_hash != ""

    def test_none_task_handled(self, fingerprinter):
        fp = fingerprinter.fingerprint(None)
        assert isinstance(fp, ProblemFingerprint)
        assert fp.primary_shape == "generation"

    def test_whitespace_only_task(self, fingerprinter):
        fp = fingerprinter.fingerprint("   ")
        assert isinstance(fp, ProblemFingerprint)
        assert fp.primary_shape == "generation"

    def test_get_fingerprint_stats_without_grimoire(self, fingerprinter):
        stats = fingerprinter.get_fingerprint_stats()
        assert isinstance(stats, dict)
        assert "shape_distribution" in stats
        assert "total_fingerprinted" in stats
        assert stats["total_fingerprinted"] == 0

    def test_get_fingerprint_stats_with_data(self, fingerprinter_with_grimoire, mock_grimoire):
        mock_grimoire.recall.return_value = [
            {
                "id": "sol-1",
                "content": "Solution 1",
                "metadata": {"primary_shape": "optimization", "domain": "database"},
            },
            {
                "id": "sol-2",
                "content": "Solution 2",
                "metadata": {"primary_shape": "optimization", "domain": "gpu"},
            },
        ]
        stats = fingerprinter_with_grimoire.get_fingerprint_stats()
        assert stats["total_fingerprinted"] == 2
        assert stats["shape_distribution"]["optimization"] == 2

    def test_graceful_grimoire_unavailable_for_stats(self, fingerprinter_with_grimoire, mock_grimoire):
        mock_grimoire.recall.side_effect = Exception("Connection failed")
        stats = fingerprinter_with_grimoire.get_fingerprint_stats()
        assert stats["total_fingerprinted"] == 0

    def test_constraint_detection(self, fingerprinter):
        fp = fingerprinter.fingerprint("Optimize memory usage within the time deadline with exact accuracy")
        assert "memory" in fp.constraints
        assert "time" in fp.constraints
        assert "accuracy" in fp.constraints

    def test_domain_detection(self, fingerprinter):
        fp = fingerprinter.fingerprint("Optimize this CUDA GPU kernel for better VRAM usage")
        assert fp.domain == "gpu"
