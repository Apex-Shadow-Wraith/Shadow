"""
Tests for Autonomous Benchmark Generator
==========================================
Generation from mastery, discovery, and weakness. Execution, retirement,
filtering, stats, edge cases, and graceful degradation.
"""

import pytest
from pathlib import Path

from modules.shadow.benchmark_generator import BenchmarkGenerator, GeneratedBenchmark


@pytest.fixture
def gen(tmp_path: Path) -> BenchmarkGenerator:
    """BenchmarkGenerator with a mock generate_fn."""

    def mock_generate(prompt: str) -> dict:
        return {
            "task_description": f"Generated from: {prompt[:40]}",
            "evaluation_criteria": {"accuracy": "Must be correct", "completeness": "Full output"},
            "expected_output_hints": "Check for correctness",
        }

    return BenchmarkGenerator(
        generate_fn=mock_generate,
        db_path=str(tmp_path / "test_benchmarks.db"),
    )


@pytest.fixture
def gen_no_fn(tmp_path: Path) -> BenchmarkGenerator:
    """BenchmarkGenerator with no generate_fn (graceful degradation)."""
    return BenchmarkGenerator(
        generate_fn=None,
        db_path=str(tmp_path / "test_benchmarks_nofn.db"),
    )


# --- Generation from mastery ---

class TestGenerateFromMastery:
    def test_creates_valid_benchmark(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("code_review", 5)
        assert isinstance(bm, GeneratedBenchmark)
        assert bm.domain == "code_review"
        assert bm.difficulty == 6  # current_level + 1
        assert bm.generated_from == "mastery"
        assert bm.status == "active"
        assert bm.times_run == 0
        assert bm.avg_score == 0.0

    def test_difficulty_capped_at_10(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("math", 10)
        assert bm.difficulty == 10

    def test_task_description_populated(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("python", 3)
        assert len(bm.task_description) > 0

    def test_persisted_to_db(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("research", 2)
        loaded = gen.get_benchmark_by_id(bm.benchmark_id)
        assert loaded is not None
        assert loaded.domain == "research"
        assert loaded.difficulty == 3


# --- Generation from discovery ---

class TestGenerateFromDiscovery:
    def test_creates_benchmark_from_discovery(self, gen: BenchmarkGenerator):
        discovery = {
            "description": "Can summarize legal documents",
            "domain": "legal",
            "difficulty": 7,
        }
        bm = gen.generate_from_discovery(discovery)
        assert bm.domain == "legal"
        assert bm.difficulty == 7
        assert bm.generated_from == "discovery"

    def test_defaults_for_missing_fields(self, gen: BenchmarkGenerator):
        discovery = {"description": "New capability found"}
        bm = gen.generate_from_discovery(discovery)
        assert bm.domain == "general"
        assert bm.difficulty == 5


# --- Generation from weakness ---

class TestGenerateFromWeakness:
    def test_creates_targeted_benchmark(self, gen: BenchmarkGenerator):
        failures = [
            {"description": "Failed date parsing", "domain": "temporal", "count": 5},
            {"description": "Wrong timezone conversion", "domain": "temporal", "count": 3},
        ]
        bm = gen.generate_from_weakness(failures)
        assert bm.domain == "temporal"
        assert bm.generated_from == "gap"
        assert bm.status == "active"

    def test_difficulty_scales_with_failure_count(self, gen: BenchmarkGenerator):
        failures = [{"description": f"fail {i}"} for i in range(7)]
        bm = gen.generate_from_weakness(failures)
        assert bm.difficulty == 7

    def test_empty_patterns_graceful(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_weakness([])
        assert bm.domain == "general"
        assert bm.generated_from == "gap"
        assert bm.status == "active"


# --- Run benchmark ---

class TestRunBenchmark:
    def test_executes_and_scores(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("logic", 4)

        def mock_executor(task: str) -> dict:
            return {"score": 0.85, "notes": "Good result"}

        result = gen.run_benchmark(bm, mock_executor)
        assert result["score"] == 0.85
        assert result["passed"] is True
        assert result["duration"] >= 0
        assert "Good result" in result["evaluation_notes"]

    def test_updates_stats_after_run(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("math", 2)

        def executor(task: str) -> dict:
            return {"score": 0.6}

        gen.run_benchmark(bm, executor)
        assert bm.times_run == 1
        assert bm.avg_score == pytest.approx(0.6)

        gen.run_benchmark(bm, executor)
        assert bm.times_run == 2
        assert bm.avg_score == pytest.approx(0.6)

    def test_failed_execution_returns_zero(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("code", 1)

        def bad_executor(task: str) -> dict:
            raise RuntimeError("Executor crashed")

        result = gen.run_benchmark(bm, bad_executor)
        assert result["score"] == 0.0
        assert result["passed"] is False
        assert "Execution error" in result["evaluation_notes"]

    def test_score_clamped_to_0_1(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("test", 1)

        def high_scorer(task: str) -> dict:
            return {"score": 5.0}

        result = gen.run_benchmark(bm, high_scorer)
        assert result["score"] == 1.0


# --- Retire benchmark ---

class TestRetireBenchmark:
    def test_retire_active_benchmark(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("writing", 3)
        assert gen.retire_benchmark(bm.benchmark_id) is True
        loaded = gen.get_benchmark_by_id(bm.benchmark_id)
        assert loaded.status == "retired"

    def test_retire_nonexistent_returns_false(self, gen: BenchmarkGenerator):
        assert gen.retire_benchmark("nonexistent-id") is False

    def test_retire_already_retired_returns_false(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("test", 1)
        gen.retire_benchmark(bm.benchmark_id)
        assert gen.retire_benchmark(bm.benchmark_id) is False


# --- Get active benchmarks ---

class TestGetActiveBenchmarks:
    def test_returns_active_only(self, gen: BenchmarkGenerator):
        bm1 = gen.generate_from_mastery("a", 1)
        bm2 = gen.generate_from_mastery("b", 2)
        gen.retire_benchmark(bm1.benchmark_id)

        active = gen.get_active_benchmarks()
        assert len(active) == 1
        assert active[0].benchmark_id == bm2.benchmark_id

    def test_filter_by_domain(self, gen: BenchmarkGenerator):
        gen.generate_from_mastery("python", 1)
        gen.generate_from_mastery("python", 3)
        gen.generate_from_mastery("math", 2)

        python_bms = gen.get_active_benchmarks(domain="python")
        assert len(python_bms) == 2
        assert all(b.domain == "python" for b in python_bms)


# --- Stats ---

class TestGetGeneratorStats:
    def test_stats_accurate(self, gen: BenchmarkGenerator):
        gen.generate_from_mastery("a", 1)
        gen.generate_from_mastery("b", 2)
        bm3 = gen.generate_from_discovery({"description": "test"})
        gen.retire_benchmark(bm3.benchmark_id)

        stats = gen.get_generator_stats()
        assert stats["total_generated"] == 3
        assert stats["active"] == 2
        assert stats["retired"] == 1
        assert stats["deferred"] == 0
        assert stats["by_source"]["mastery"] == 2
        assert stats["by_source"]["discovery"] == 1
        assert stats["by_source"]["gap"] == 0

    def test_empty_stats(self, gen: BenchmarkGenerator):
        stats = gen.get_generator_stats()
        assert stats["total_generated"] == 0
        assert stats["active"] == 0


# --- Graceful degradation ---

class TestGracefulDegradation:
    def test_no_generate_fn_returns_placeholder(self, gen_no_fn: BenchmarkGenerator):
        bm = gen_no_fn.generate_from_mastery("test", 3)
        assert isinstance(bm, GeneratedBenchmark)
        assert bm.status == "active"
        assert len(bm.task_description) > 0

    def test_generate_fn_returns_string(self, tmp_path: Path):
        gen = BenchmarkGenerator(
            generate_fn=lambda p: "Just a plain string response",
            db_path=str(tmp_path / "test.db"),
        )
        bm = gen.generate_from_mastery("test", 1)
        assert bm.task_description == "Just a plain string response"


# --- Required fields ---

class TestRequiredFields:
    def test_all_fields_present(self, gen: BenchmarkGenerator):
        bm = gen.generate_from_mastery("domain", 5)
        assert bm.benchmark_id
        assert bm.domain == "domain"
        assert bm.difficulty == 6
        assert isinstance(bm.task_description, str)
        assert isinstance(bm.evaluation_criteria, dict)
        assert isinstance(bm.expected_output_hints, str)
        assert bm.generated_from in {"mastery", "discovery", "gap"}
        assert bm.created_at > 0
        assert bm.times_run == 0
        assert bm.avg_score == 0.0
        assert bm.status in {"active", "retired", "deferred"}
