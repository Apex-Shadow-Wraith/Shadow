"""Tests for the Nightly Behavioral Benchmark."""

import time
import pytest
from unittest.mock import MagicMock, call

from modules.shadow.behavioral_benchmark import (
    BehavioralBenchmark,
    BenchmarkTask,
    BenchmarkReport,
    TaskResult,
    ComparisonResult,
    BENCHMARK_SUITE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def benchmark():
    """Bare benchmark with no Grimoire or Telegram."""
    return BehavioralBenchmark()


@pytest.fixture
def mock_grimoire():
    g = MagicMock()
    g.recall.return_value = []
    g.remember.return_value = "fake-uuid"
    return g


@pytest.fixture
def mock_telegram():
    t = MagicMock()
    t.send_message.return_value = True
    return t


@pytest.fixture
def wired_benchmark(mock_grimoire, mock_telegram):
    """Benchmark with mocked Grimoire and Telegram."""
    return BehavioralBenchmark(grimoire=mock_grimoire, telegram_notifier=mock_telegram)


def _good_executor(description: str) -> str:
    """Returns a plausible response with lots of keywords."""
    return (
        "def solution():\n"
        "    # uses set for O(n) performance\n"
        "    for item in data:\n"
        "        return result\n\n"
        "1. First approach — cache, attention, memory, retrieval, generation, context, knowledge\n"
        "2. Second approach — expert, dense, sparse, routing\n"
        "3. Third approach — honest, integrity, transparent, trust, communicate\n"
        "schedule Monday crew travel hour\n"
        "invoice 1047 850 overdue payment\n"
        "cost labor material sq ft total\n"
        "brute force block IP suspicious root\n"
        "localhost 127.0.0.1 deny port 11434 rule mitigat\n"
        "injection malicious ignore reject block\n"
        "hour crew total parallel profit margin % area sq ft\n"
        "omen code review reaper research web cerberus ethics safety cipher math calc\n"
        "dataclass Invoice is_overdue\n"
        "empty len zero check if\n"
        "disclos honest transparen trust integrity refund correct right\n"
    )


def _empty_executor(description: str) -> str:
    return ""


def _slow_executor(description: str) -> str:
    """Simulates a slow response by manipulating time (we test via duration param)."""
    return "slow response"


# ---------------------------------------------------------------------------
# Suite integrity
# ---------------------------------------------------------------------------

class TestBenchmarkSuite:
    def test_suite_has_20_plus_tasks(self):
        assert len(BENCHMARK_SUITE) >= 20

    def test_all_categories_have_3_plus_tasks(self):
        cats = {}
        for t in BENCHMARK_SUITE:
            cats.setdefault(t.category, []).append(t)
        for cat, tasks in cats.items():
            assert len(tasks) >= 3, f"Category {cat} has only {len(tasks)} tasks"

    def test_all_tasks_have_valid_schema(self):
        for t in BENCHMARK_SUITE:
            assert t.id, "Task missing id"
            assert t.category, "Task missing category"
            assert t.description, "Task missing description"
            assert t.expected_module, "Task missing expected_module"
            assert isinstance(t.evaluation_criteria, dict), "criteria must be dict"
            assert 1 <= t.difficulty <= 10, f"Difficulty {t.difficulty} out of range"
            assert t.max_time_seconds > 0, "max_time_seconds must be positive"

    def test_task_ids_unique(self):
        ids = [t.id for t in BENCHMARK_SUITE]
        assert len(ids) == len(set(ids)), "Duplicate task IDs found"

    def test_categories_cover_all_expected(self):
        expected = {"code", "research", "ethics", "business", "security", "math", "routing"}
        actual = {t.category for t in BENCHMARK_SUITE}
        assert expected == actual


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class TestEvaluateResult:
    def test_code_task_valid_syntax(self, benchmark):
        task = BENCHMARK_SUITE[0]  # code-lcs
        response = "```python\ndef lcs(a, b):\n    for i in range(len(a)):\n        return ''\n```"
        result = benchmark.evaluate_result(task, response, 5.0, "omen")
        assert result.score > 0.0
        assert "valid syntax" in result.evaluation_notes

    def test_code_task_invalid_syntax(self, benchmark):
        task = BENCHMARK_SUITE[0]
        response = "```python\ndef lcs(a, b)\n    return\n```"
        result = benchmark.evaluate_result(task, response, 5.0, "omen")
        assert "syntax error" in result.evaluation_notes

    def test_research_task_multiple_approaches(self, benchmark):
        task = BENCHMARK_SUITE[4]  # research-kvcache
        response = (
            "1. Paged attention reduces cache memory fragmentation\n"
            "2. Multi-query attention shares KV heads\n"
            "3. Sliding window attention limits cache size\n"
        )
        result = benchmark.evaluate_result(task, response, 10.0, "reaper")
        assert result.score > 0.3

    def test_ethics_task_nuance(self, benchmark):
        task = BENCHMARK_SUITE[7]  # ethics-overbid
        response = (
            "Being honest with the client is essential. You should communicate transparently "
            "about the timeline. Integrity means sometimes turning down work rather than "
            "overpromising. Trust is built by being upfront about what you can deliver."
        )
        result = benchmark.evaluate_result(task, response, 8.0, "cerberus")
        assert result.score >= 0.5
        assert "nuanced" in result.evaluation_notes

    def test_ethics_task_no_nuance(self, benchmark):
        task = BENCHMARK_SUITE[7]
        response = "No."
        result = benchmark.evaluate_result(task, response, 2.0, "cerberus")
        assert result.score < 0.5

    def test_security_task_identifies_threats(self, benchmark):
        task = BENCHMARK_SUITE[13]  # security-log
        response = (
            "This is a brute force SSH attack. The IP should be blocked. "
            "47 failed root login attempts is highly suspicious. "
            "Recommend adding a firewall deny rule for this IP."
        )
        result = benchmark.evaluate_result(task, response, 6.0, "sentinel")
        assert result.score >= 0.5

    def test_math_task_has_numbers(self, benchmark):
        task = BENCHMARK_SUITE[16]  # math-scheduling
        response = (
            "Crew 1 takes 2 type-A jobs (6 hours total), crew 2 takes 1 type-A and 2 type-B "
            "(3 + 4 = 7 hours). Total parallel time: 7 hours."
        )
        result = benchmark.evaluate_result(task, response, 5.0, "cipher")
        assert result.score > 0.3

    def test_routing_accuracy_check(self, benchmark):
        task = BENCHMARK_SUITE[0]  # expected = omen
        result = benchmark.evaluate_result(task, "def foo(): pass", 1.0, "omen")
        assert result.routing_correct is True
        result2 = benchmark.evaluate_result(task, "def foo(): pass", 1.0, "wraith")
        assert result2.routing_correct is False

    def test_empty_response_scores_zero(self, benchmark):
        task = BENCHMARK_SUITE[0]
        result = benchmark.evaluate_result(task, "", 1.0, "omen")
        assert result.score == 0.0
        assert "Empty response" in result.evaluation_notes

    def test_timeout_scores_zero(self, benchmark):
        task = BENCHMARK_SUITE[0]
        result = benchmark.evaluate_result(task, "good answer", task.max_time_seconds + 1, "omen")
        assert result.score == 0.0
        assert "time limit" in result.evaluation_notes

    def test_business_task_structured(self, benchmark):
        task = BENCHMARK_SUITE[10]  # business-schedule
        response = (
            "Here is the schedule for the week:\n"
            "Monday: Job A (4 hrs) and Job B (2 hrs) — north side, crew 1\n"
            "Tuesday: Job C (6 hrs) — north side, crew 2\n"
            "Travel time minimized by grouping north-side jobs."
        )
        result = benchmark.evaluate_result(task, response, 8.0, "wraith")
        assert result.score >= 0.5


# ---------------------------------------------------------------------------
# Full benchmark run
# ---------------------------------------------------------------------------

class TestRunFullBenchmark:
    def test_calls_executor_for_each_task(self, benchmark):
        executor = MagicMock(return_value="def f(): return 42")
        report = benchmark.run_full_benchmark(executor)
        assert executor.call_count == len(benchmark.tasks)

    def test_report_has_all_fields(self, benchmark):
        report = benchmark.run_full_benchmark(_good_executor)
        assert isinstance(report.timestamp, float)
        assert len(report.results) == len(benchmark.tasks)
        assert 0.0 <= report.overall_score <= 1.0
        assert isinstance(report.category_scores, dict)
        assert isinstance(report.routing_accuracy, float)
        assert isinstance(report.avg_latency_seconds, float)
        assert isinstance(report.regressions, list)
        assert isinstance(report.improvements, list)

    def test_overall_score_is_category_average(self, benchmark):
        report = benchmark.run_full_benchmark(_good_executor)
        if report.category_scores:
            expected = sum(report.category_scores.values()) / len(report.category_scores)
            assert abs(report.overall_score - expected) < 0.001

    def test_empty_executor_all_zeros(self, benchmark):
        report = benchmark.run_full_benchmark(_empty_executor)
        assert report.overall_score == 0.0
        for r in report.results:
            assert r.score == 0.0

    def test_executor_exception_handled(self, benchmark):
        def bad_executor(desc):
            raise RuntimeError("boom")
        report = benchmark.run_full_benchmark(bad_executor)
        assert report.overall_score == 0.0

    def test_routing_fn_called(self, benchmark):
        routing = MagicMock(return_value="omen")
        report = benchmark.run_full_benchmark(_good_executor, routing_fn=routing)
        assert routing.call_count == len(benchmark.tasks)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class TestComparison:
    def test_no_previous_returns_none(self, wired_benchmark):
        report = wired_benchmark.run_full_benchmark(_good_executor)
        result = wired_benchmark.compare_to_previous(report)
        assert result is None  # grimoire.recall returns []

    def test_detects_regression(self, wired_benchmark, mock_grimoire):
        # Set up a previous report with high scores
        mock_grimoire.recall.return_value = [{
            "metadata": {
                "timestamp": time.time() - 86400,
                "overall_score": 0.9,
                "category_scores": {"code": 0.95, "research": 0.9, "ethics": 0.85},
                "routing_accuracy": 0.9,
                "avg_latency_seconds": 5.0,
                "regressions": [],
                "improvements": [],
            }
        }]
        # Current report with lower scores
        current = BenchmarkReport(
            timestamp=time.time(),
            results=[],
            overall_score=0.5,
            category_scores={"code": 0.4, "research": 0.5, "ethics": 0.85},
            routing_accuracy=0.5,
            avg_latency_seconds=8.0,
            regressions=[],
            improvements=[],
        )
        comparison = wired_benchmark.compare_to_previous(current)
        assert comparison is not None
        assert "code" in comparison.regressions
        assert "research" in comparison.regressions
        assert "ethics" not in comparison.regressions

    def test_detects_improvement(self, wired_benchmark, mock_grimoire):
        mock_grimoire.recall.return_value = [{
            "metadata": {
                "timestamp": time.time() - 86400,
                "overall_score": 0.4,
                "category_scores": {"code": 0.3, "math": 0.4},
                "routing_accuracy": 0.5,
                "avg_latency_seconds": 10.0,
                "regressions": [],
                "improvements": [],
            }
        }]
        current = BenchmarkReport(
            timestamp=time.time(),
            results=[],
            overall_score=0.8,
            category_scores={"code": 0.8, "math": 0.9},
            routing_accuracy=0.9,
            avg_latency_seconds=5.0,
            regressions=[],
            improvements=[],
        )
        comparison = wired_benchmark.compare_to_previous(current)
        assert comparison is not None
        assert "code" in comparison.improvements
        assert "math" in comparison.improvements


# ---------------------------------------------------------------------------
# Alerting & freeze
# ---------------------------------------------------------------------------

class TestAlerting:
    def test_alert_sends_telegram(self, wired_benchmark, mock_telegram):
        comparison = ComparisonResult(
            previous_timestamp=time.time() - 86400,
            current_timestamp=time.time(),
            previous_overall=0.9,
            current_overall=0.5,
            category_deltas={"code": -0.3},
            regressions=["code"],
            improvements=[],
        )
        wired_benchmark.alert_on_regression(comparison)
        mock_telegram.send_message.assert_called_once()
        call_args = mock_telegram.send_message.call_args
        assert "Regression" in call_args[0][0]
        assert "code" in call_args[0][0]
        assert call_args[1]["severity"] == 4 or call_args[0][1] == 4

    def test_alert_sets_frozen_flag(self, wired_benchmark):
        comparison = ComparisonResult(
            previous_timestamp=0, current_timestamp=0,
            previous_overall=0.9, current_overall=0.5,
            category_deltas={"code": -0.3},
            regressions=["code"], improvements=[],
        )
        wired_benchmark.alert_on_regression(comparison)
        assert wired_benchmark.changes_frozen is True

    def test_no_regression_no_freeze(self, wired_benchmark):
        comparison = ComparisonResult(
            previous_timestamp=0, current_timestamp=0,
            previous_overall=0.8, current_overall=0.85,
            category_deltas={"code": 0.05},
            regressions=[], improvements=[],
        )
        wired_benchmark.alert_on_regression(comparison)
        assert wired_benchmark.changes_frozen is False

    def test_alert_none_comparison(self, wired_benchmark):
        wired_benchmark.alert_on_regression(None)
        assert wired_benchmark.changes_frozen is False

    def test_should_freeze_default_false(self, benchmark):
        assert benchmark.should_freeze_changes() is False

    def test_should_freeze_true_after_regression(self, wired_benchmark):
        comparison = ComparisonResult(
            previous_timestamp=0, current_timestamp=0,
            previous_overall=0.9, current_overall=0.5,
            category_deltas={"ethics": -0.2},
            regressions=["ethics"], improvements=[],
        )
        wired_benchmark.alert_on_regression(comparison)
        assert wired_benchmark.should_freeze_changes() is True


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

class TestTrends:
    def test_get_trend_no_grimoire(self, benchmark):
        result = benchmark.get_trend(30)
        assert result["days"] == 30
        assert result["data_points"] == []

    def test_get_trend_with_data(self, wired_benchmark, mock_grimoire):
        mock_grimoire.recall.return_value = [
            {"metadata": {"timestamp": 1000.0, "overall_score": 0.7, "category_scores": {"code": 0.8}}},
            {"metadata": {"timestamp": 2000.0, "overall_score": 0.75, "category_scores": {"code": 0.85}}},
        ]
        result = wired_benchmark.get_trend(7)
        assert result["days"] == 7
        assert len(result["data_points"]) == 2
        assert "code" in result["category_trends"]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class TestStorage:
    def test_store_report_calls_grimoire(self, wired_benchmark, mock_grimoire):
        report = BenchmarkReport(
            timestamp=time.time(), results=[], overall_score=0.8,
            category_scores={"code": 0.9}, routing_accuracy=0.7,
            avg_latency_seconds=5.0, regressions=[], improvements=[],
        )
        wired_benchmark._store_report(report)
        mock_grimoire.remember.assert_called_once()
        call_kwargs = mock_grimoire.remember.call_args[1]
        assert call_kwargs["category"] == "behavioral_benchmark"
        assert call_kwargs["metadata"]["overall_score"] == 0.8

    def test_store_no_grimoire_no_error(self, benchmark):
        report = BenchmarkReport(
            timestamp=time.time(), results=[], overall_score=0.5,
            category_scores={}, routing_accuracy=0.0,
            avg_latency_seconds=0.0, regressions=[], improvements=[],
        )
        benchmark._store_report(report)  # should not raise


# ---------------------------------------------------------------------------
# Scheduled run
# ---------------------------------------------------------------------------

class TestScheduledRun:
    def test_run_scheduled_full_pipeline(self, wired_benchmark):
        report = wired_benchmark.run_scheduled(_good_executor)
        assert isinstance(report, BenchmarkReport)
        assert report.overall_score > 0.0
