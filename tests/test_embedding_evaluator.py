"""
Tests for Embedding Evaluator — Retrieval Quality Metrics
==========================================================
Covers eval set construction, metric computation, model comparison,
JSONL export, and benchmark storage.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.grimoire.embedding_evaluator import EmbeddingEvaluator


# --- Fixtures ---

def _make_mock_grimoire(memories=None):
    """Create a mock Grimoire with controllable recall() and remember()."""
    grimoire = MagicMock()
    grimoire.embed_model = "nomic-embed-text"

    # Default memories in SQLite
    if memories is None:
        memories = [
            {
                "id": "mem-code-001",
                "content": "def reverse_list(items): return items[::-1]",
                "category": "code",
                "source": "conversation",
                "trust_level": 0.5,
            },
            {
                "id": "mem-bible-001",
                "content": "John 3:16 — For God so loved the world",
                "category": "bible",
                "source": "user_stated",
                "trust_level": 0.9,
            },
            {
                "id": "mem-tech-001",
                "content": "GPU: RTX 5090 with 32GB VRAM",
                "category": "hardware",
                "source": "conversation",
                "trust_level": 0.5,
            },
            {
                "id": "mem-biz-001",
                "content": "Client estimate for spring mulch job at $2,400",
                "category": "business",
                "source": "user_stated",
                "trust_level": 0.9,
            },
        ]

    # Mock the SQLite cursor
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        # sqlite3.Row-like dicts
        {k: m[k] for k in ("id", "content", "category", "source", "trust_level")}
        for m in memories
    ]
    grimoire.conn.cursor.return_value = cursor

    # Default recall() returns matching memory at rank 1
    def _recall(query, n_results=5):
        # Return all memories with fake relevance scores
        results = []
        for m in memories:
            results.append({
                "id": m["id"],
                "content": m["content"],
                "category": m["category"],
                "relevance": 0.85,
            })
        return results[:n_results]

    grimoire.recall.side_effect = _recall

    # remember() returns a fake ID
    grimoire.remember.return_value = "bench-001"

    return grimoire, memories


@pytest.fixture
def mock_grimoire():
    """Grimoire mock with 4 diverse memories."""
    grimoire, memories = _make_mock_grimoire()
    return grimoire


@pytest.fixture
def evaluator(mock_grimoire):
    """EmbeddingEvaluator with mocked Grimoire."""
    return EmbeddingEvaluator(mock_grimoire)


@pytest.fixture
def eval_set(evaluator):
    """Pre-built eval set for reuse."""
    return evaluator.build_eval_set()


# --- build_eval_set tests ---

class TestBuildEvalSet:
    def test_returns_list(self, evaluator):
        result = evaluator.build_eval_set()
        assert isinstance(result, list)

    def test_generates_positive_and_negative_pairs(self, evaluator):
        result = evaluator.build_eval_set()
        labels = {e["label"] for e in result}
        assert "positive" in labels
        assert "negative" in labels

    def test_each_pair_has_required_keys(self, evaluator):
        result = evaluator.build_eval_set()
        for pair in result:
            assert "query" in pair
            assert "expected_id" in pair
            assert "label" in pair
            assert "category" in pair

    def test_positive_queries_have_content(self, evaluator):
        result = evaluator.build_eval_set()
        positives = [e for e in result if e["label"] == "positive"]
        for p in positives:
            assert len(p["query"]) > 0

    def test_negative_queries_differ_from_category(self, evaluator):
        """Negative queries should come from a different category."""
        result = evaluator.build_eval_set()
        negatives = [e for e in result if e["label"] == "negative"]
        # At minimum, negatives should exist when we have multiple categories
        assert len(negatives) > 0

    def test_empty_grimoire_returns_empty(self):
        grimoire, _ = _make_mock_grimoire(memories=[])
        grimoire.conn.cursor.return_value.fetchall.return_value = []
        ev = EmbeddingEvaluator(grimoire)
        result = ev.build_eval_set()
        assert result == []

    def test_code_memory_generates_code_query(self, evaluator):
        result = evaluator.build_eval_set()
        code_positives = [
            e for e in result
            if e["label"] == "positive" and e["category"] == "code"
        ]
        assert len(code_positives) > 0
        # Should reference the function name
        assert "reverse_list" in code_positives[0]["query"]

    def test_bible_memory_generates_verse_query(self, evaluator):
        result = evaluator.build_eval_set()
        bible_positives = [
            e for e in result
            if e["label"] == "positive" and e["category"] == "bible"
        ]
        assert len(bible_positives) > 0
        query = bible_positives[0]["query"]
        # Should reference the verse
        assert "3:16" in query or "love" in query.lower()


# --- run_eval tests ---

class TestRunEval:
    def test_returns_all_required_metrics(self, evaluator, eval_set):
        result = evaluator.run_eval(eval_set)
        assert "metrics" in result
        metrics = result["metrics"]
        assert "recall_at_1" in metrics
        assert "recall_at_5" in metrics
        assert "recall_at_10" in metrics
        assert "mrr" in metrics
        assert "avg_similarity_score" in metrics

    def test_returns_failures_list(self, evaluator, eval_set):
        result = evaluator.run_eval(eval_set)
        assert "failures" in result
        assert isinstance(result["failures"], list)

    def test_returns_total_count(self, evaluator, eval_set):
        result = evaluator.run_eval(eval_set)
        assert "total" in result
        assert result["total"] > 0

    def test_returns_timestamp(self, evaluator, eval_set):
        result = evaluator.run_eval(eval_set)
        assert "timestamp" in result

    def test_metrics_between_0_and_1(self, evaluator, eval_set):
        result = evaluator.run_eval(eval_set)
        for key, value in result["metrics"].items():
            assert 0.0 <= value <= 1.0, f"{key} = {value} is out of [0, 1]"

    def test_perfect_recall_when_all_found(self, mock_grimoire):
        """When recall() always returns the expected doc at rank 1."""
        # Make recall return specific memory based on query
        grimoire, memories = _make_mock_grimoire()

        def _perfect_recall(query, n_results=5):
            # Always return all memories — expected one will be in there
            return [
                {"id": m["id"], "content": m["content"],
                 "category": m["category"], "relevance": 0.95}
                for m in memories
            ][:n_results]

        grimoire.recall.side_effect = _perfect_recall
        ev = EmbeddingEvaluator(grimoire)
        result = ev.run_eval()
        # All positives should hit since all memories are returned
        assert result["metrics"]["recall_at_10"] == 1.0

    def test_zero_metrics_when_nothing_found(self):
        """When recall() never returns the expected doc."""
        grimoire, _ = _make_mock_grimoire()

        def _empty_recall(query, n_results=5):
            return [
                {"id": "wrong-id", "content": "unrelated",
                 "category": "other", "relevance": 0.1}
            ]

        grimoire.recall.side_effect = _empty_recall
        ev = EmbeddingEvaluator(grimoire)
        result = ev.run_eval()
        assert result["metrics"]["recall_at_1"] == 0.0
        assert result["metrics"]["recall_at_10"] == 0.0
        assert result["metrics"]["mrr"] == 0.0
        assert len(result["failures"]) == result["total"]

    def test_auto_builds_eval_set_when_none(self, evaluator):
        """run_eval(None) should call build_eval_set() internally."""
        result = evaluator.run_eval(None)
        assert result["total"] > 0

    def test_empty_eval_set_returns_zero_metrics(self, evaluator):
        result = evaluator.run_eval([])
        assert result["total"] == 0
        assert result["metrics"]["mrr"] == 0.0


# --- compare_models tests ---

class TestCompareModels:
    def test_returns_side_by_side_results(self, evaluator, eval_set):
        result = evaluator.compare_models(
            "nomic-embed-text", "mxbai-embed-large", eval_set
        )
        assert "model_a" in result
        assert "model_b" in result
        assert result["model_a"]["name"] == "nomic-embed-text"
        assert result["model_b"]["name"] == "mxbai-embed-large"

    def test_returns_metrics_for_both(self, evaluator, eval_set):
        result = evaluator.compare_models(
            "nomic-embed-text", "mxbai-embed-large", eval_set
        )
        for model_key in ("model_a", "model_b"):
            metrics = result[model_key]["metrics"]
            assert "recall_at_1" in metrics
            assert "mrr" in metrics

    def test_returns_winner(self, evaluator, eval_set):
        result = evaluator.compare_models(
            "nomic-embed-text", "mxbai-embed-large", eval_set
        )
        assert "winner" in result
        assert result["winner"] in ("nomic-embed-text", "mxbai-embed-large")

    def test_returns_delta(self, evaluator, eval_set):
        result = evaluator.compare_models(
            "nomic-embed-text", "mxbai-embed-large", eval_set
        )
        assert "delta" in result
        for key in ("recall_at_1", "recall_at_5", "recall_at_10", "mrr",
                     "avg_similarity_score"):
            assert key in result["delta"]

    def test_restores_original_model(self, mock_grimoire, eval_set):
        ev = EmbeddingEvaluator(mock_grimoire)
        original = mock_grimoire.embed_model
        ev.compare_models("model-a", "model-b", eval_set)
        assert mock_grimoire.embed_model == original

    def test_delta_values_are_numeric(self, evaluator, eval_set):
        result = evaluator.compare_models(
            "nomic-embed-text", "mxbai-embed-large", eval_set
        )
        for key, val in result["delta"].items():
            assert isinstance(val, (int, float)), f"delta[{key}] is not numeric"

    def test_metrics_between_0_and_1_for_both(self, evaluator, eval_set):
        result = evaluator.compare_models(
            "nomic-embed-text", "mxbai-embed-large", eval_set
        )
        for model_key in ("model_a", "model_b"):
            for key, val in result[model_key]["metrics"].items():
                assert 0.0 <= val <= 1.0, (
                    f"{model_key}.{key} = {val} out of range"
                )


# --- export_training_pairs tests ---

class TestExportTrainingPairs:
    def test_creates_jsonl_file(self, evaluator, tmp_path):
        out = str(tmp_path / "pairs.jsonl")
        count = evaluator.export_training_pairs(out)
        assert Path(out).exists()
        assert count > 0

    def test_jsonl_format_valid(self, evaluator, tmp_path):
        out = str(tmp_path / "pairs.jsonl")
        evaluator.export_training_pairs(out)
        with open(out, encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                assert "query" in obj
                assert "positive" in obj
                assert "negative" in obj

    def test_returns_count_of_pairs(self, evaluator, tmp_path):
        out = str(tmp_path / "pairs.jsonl")
        count = evaluator.export_training_pairs(out)
        with open(out, encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        assert count == len(lines)

    def test_empty_grimoire_exports_zero(self, tmp_path):
        grimoire, _ = _make_mock_grimoire(memories=[])
        grimoire.conn.cursor.return_value.fetchall.return_value = []
        ev = EmbeddingEvaluator(grimoire)
        out = str(tmp_path / "empty.jsonl")
        count = ev.export_training_pairs(out)
        assert count == 0

    def test_creates_parent_directories(self, evaluator, tmp_path):
        out = str(tmp_path / "nested" / "deep" / "pairs.jsonl")
        evaluator.export_training_pairs(out)
        assert Path(out).exists()

    def test_positive_and_negative_differ(self, evaluator, tmp_path):
        out = str(tmp_path / "pairs.jsonl")
        evaluator.export_training_pairs(out)
        with open(out, encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                assert obj["positive"] != obj["negative"]


# --- store_benchmark tests ---

class TestStoreBenchmark:
    def test_stores_to_grimoire(self, evaluator, mock_grimoire):
        results = evaluator.run_eval()
        memory_id = evaluator.store_benchmark(results)
        assert memory_id is not None
        mock_grimoire.remember.assert_called_once()

    def test_uses_correct_category(self, evaluator, mock_grimoire):
        results = evaluator.run_eval()
        evaluator.store_benchmark(results)
        call_kwargs = mock_grimoire.remember.call_args
        assert call_kwargs[1]["category"] == "embedding_benchmarks"

    def test_uses_correct_tags(self, evaluator, mock_grimoire):
        results = evaluator.run_eval()
        evaluator.store_benchmark(results)
        call_kwargs = mock_grimoire.remember.call_args
        tags = call_kwargs[1]["tags"]
        assert "benchmark" in tags
        assert "embeddings" in tags

    def test_stored_content_is_valid_json(self, evaluator, mock_grimoire):
        results = evaluator.run_eval()
        evaluator.store_benchmark(results)
        call_kwargs = mock_grimoire.remember.call_args
        content = call_kwargs[1]["content"]
        parsed = json.loads(content)
        assert "metrics" in parsed
        assert "total" in parsed


# --- format_report tests ---

class TestFormatReport:
    def test_format_report_contains_metrics(self, evaluator):
        results = evaluator.run_eval()
        report = evaluator.format_report(results)
        assert "Recall@1" in report
        assert "Recall@5" in report
        assert "MRR" in report

    def test_format_comparison_contains_both_models(self, evaluator, eval_set):
        comparison = evaluator.compare_models(
            "nomic-embed-text", "mxbai-embed-large", eval_set
        )
        report = evaluator.format_comparison(comparison)
        assert "nomic-embed-text" in report
        assert "mxbai-embed-large" in report
        assert "Winner" in report


# --- Query extraction edge cases ---

class TestQueryExtraction:
    def test_generic_fallback_for_unknown_category(self):
        grimoire, _ = _make_mock_grimoire(memories=[
            {
                "id": "mem-misc-001",
                "content": "This is a random memory about something interesting and worth remembering",
                "category": "miscellaneous",
                "source": "conversation",
                "trust_level": 0.5,
            },
        ])
        ev = EmbeddingEvaluator(grimoire)
        result = ev.build_eval_set()
        positives = [e for e in result if e["label"] == "positive"]
        assert len(positives) == 1
        assert len(positives[0]["query"]) > 0

    def test_class_name_extraction(self):
        grimoire, _ = _make_mock_grimoire(memories=[
            {
                "id": "mem-class-001",
                "content": "class EmbeddingRouter handles domain routing",
                "category": "code",
                "source": "conversation",
                "trust_level": 0.5,
            },
        ])
        ev = EmbeddingEvaluator(grimoire)
        result = ev.build_eval_set()
        positives = [e for e in result if e["label"] == "positive"]
        assert "EmbeddingRouter" in positives[0]["query"]

    def test_hardware_spec_extraction(self):
        grimoire, _ = _make_mock_grimoire(memories=[
            {
                "id": "mem-hw-001",
                "content": "RAM 64GB DDR5 installed in dual channel",
                "category": "hardware",
                "source": "conversation",
                "trust_level": 0.5,
            },
        ])
        ev = EmbeddingEvaluator(grimoire)
        result = ev.build_eval_set()
        positives = [e for e in result if e["label"] == "positive"]
        assert len(positives) == 1
        assert "RAM" in positives[0]["query"]
