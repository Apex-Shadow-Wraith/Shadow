"""Tests for the Monthly Benchmark Suite."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.shadow.benchmark_suite import BenchmarkSuite, _TASKS_FILE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator that returns canned responses."""
    orch = AsyncMock()

    async def fake_process(user_input, source="benchmark"):
        """Return plausible responses per task category."""
        lower = user_input.lower()
        if "fibonacci" in lower:
            return "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
        if "stack" in lower:
            return "class Stack:\n    def __init__(self):\n        self._items = []\n    def push(self, item):\n        self._items.append(item)\n    def pop(self):\n        return self._items.pop()\n    def peek(self):\n        return self._items[-1]"
        if "347 * 28" in lower or "347*28" in lower:
            return "347 * 28 = 9716"
        if "square root of 144" in lower:
            return "The square root of 144 is 12."
        if "who are you" in lower:
            return "I am Shadow, Master. Your autonomous AI agent."
        if "plain text" in lower:
            return "No, that's a terrible idea. You should hash passwords with bcrypt for security."
        if "agree with everything" in lower:
            return "No, Master. It's my duty to push back and be honest with you, even when you disagree."
        if "capital of australia" in lower:
            return "Canberra"
        if "divide_list" in lower:
            return "The bug is division by zero. If any number in the list is 0, it will raise a ZeroDivisionError."
        return "I don't know the answer to that, Master."

    orch.process_input = AsyncMock(side_effect=fake_process)
    return orch


@pytest.fixture
def suite(mock_orchestrator):
    """Create a BenchmarkSuite with mock orchestrator."""
    return BenchmarkSuite(mock_orchestrator, {"model_name": "test-model"})


@pytest.fixture
def temp_benchmarks_dir(tmp_path):
    """Provide a temporary benchmarks directory."""
    return tmp_path / "benchmarks"


# ---------------------------------------------------------------------------
# Test: load_benchmark_set
# ---------------------------------------------------------------------------

class TestLoadBenchmarkSet:
    """Tests for loading benchmark tasks."""

    def test_load_returns_50_tasks(self, suite):
        """Benchmark set should contain exactly 50 tasks."""
        tasks = suite.load_benchmark_set()
        assert len(tasks) == 50

    def test_all_tasks_have_required_fields(self, suite):
        """Every task must have id, input, expected_output_keywords, category, difficulty, rubric."""
        tasks = suite.load_benchmark_set()
        required = {"id", "input", "expected_output_keywords", "category", "difficulty", "rubric"}
        for task in tasks:
            missing = required - set(task.keys())
            assert not missing, f"Task {task.get('id', '?')} missing: {missing}"

    def test_tasks_have_unique_ids(self, suite):
        """All task IDs must be unique."""
        tasks = suite.load_benchmark_set()
        ids = [t["id"] for t in tasks]
        assert len(ids) == len(set(ids)), "Duplicate task IDs found"

    def test_tasks_cover_all_categories(self, suite):
        """Tasks should cover all 8 required categories."""
        tasks = suite.load_benchmark_set()
        categories = {t["category"] for t in tasks}
        expected_categories = {
            "code_generation", "code_review", "math_logic",
            "research_synthesis", "general_knowledge",
            "landscaping_business", "bible_study",
            "multi_step_reasoning", "personality_consistency",
        }
        assert expected_categories.issubset(categories), (
            f"Missing categories: {expected_categories - categories}"
        )

    def test_difficulty_in_range(self, suite):
        """Difficulty must be between 1 and 10."""
        tasks = suite.load_benchmark_set()
        for task in tasks:
            assert 1 <= task["difficulty"] <= 10, (
                f"Task {task['id']} has difficulty {task['difficulty']}"
            )

    def test_missing_file_raises(self, mock_orchestrator):
        """Loading from a nonexistent path should raise FileNotFoundError."""
        suite = BenchmarkSuite(mock_orchestrator)
        suite._tasks_file = Path("/nonexistent/benchmark_tasks.json")
        with pytest.raises(FileNotFoundError):
            suite.load_benchmark_set()


# ---------------------------------------------------------------------------
# Test: score_response
# ---------------------------------------------------------------------------

class TestScoreResponse:
    """Tests for the scoring system."""

    def test_score_returns_float_in_range(self, suite):
        """Score must be a float between 0.0 and 1.0."""
        task = {
            "id": "test",
            "input": "test",
            "expected_output_keywords": ["hello"],
            "category": "general_knowledge",
            "difficulty": 1,
            "rubric": {"type": "keyword", "required_keywords": ["hello"]},
        }
        score = suite.score_response("hello world", task)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_exact_answer_correct(self, suite):
        """Exact answer match should score 1.0."""
        task = {
            "id": "math",
            "input": "What is 2+2?",
            "expected_output_keywords": ["4"],
            "category": "math_logic",
            "difficulty": 1,
            "rubric": {"type": "exact_answer", "answer": "4"},
        }
        assert suite.score_response("The answer is 4.", task) == 1.0

    def test_exact_answer_incorrect(self, suite):
        """Wrong exact answer should score 0.0."""
        task = {
            "id": "math",
            "input": "What is 2+2?",
            "expected_output_keywords": ["4"],
            "category": "math_logic",
            "difficulty": 1,
            "rubric": {"type": "exact_answer", "answer": "4"},
        }
        assert suite.score_response("The answer is 5.", task) == 0.0

    def test_exact_answer_case_insensitive(self, suite):
        """Exact answer matching should be case-insensitive."""
        task = {
            "id": "geo",
            "input": "Capital?",
            "expected_output_keywords": ["Canberra"],
            "category": "general_knowledge",
            "difficulty": 1,
            "rubric": {"type": "exact_answer", "answer": "Canberra"},
        }
        assert suite.score_response("CANBERRA is the capital.", task) == 1.0

    def test_keyword_all_present(self, suite):
        """All required keywords present should get high score."""
        task = {
            "id": "kw",
            "input": "test",
            "expected_output_keywords": ["python", "fast"],
            "category": "general_knowledge",
            "difficulty": 1,
            "rubric": {
                "type": "keyword",
                "required_keywords": ["python", "fast"],
            },
        }
        score = suite.score_response("Python is fast and great", task)
        assert score == 1.0

    def test_keyword_none_present(self, suite):
        """No keywords present should score 0.0."""
        task = {
            "id": "kw",
            "input": "test",
            "expected_output_keywords": ["python"],
            "category": "general_knowledge",
            "difficulty": 1,
            "rubric": {
                "type": "keyword",
                "required_keywords": ["python", "fast"],
            },
        }
        score = suite.score_response("Nothing relevant here", task)
        assert score == 0.0

    def test_code_scoring_with_valid_code(self, suite):
        """Code response with def/class and keywords should score high."""
        task = {
            "id": "code",
            "input": "Write fibonacci",
            "expected_output_keywords": ["def", "fibonacci", "return"],
            "category": "code_generation",
            "difficulty": 1,
            "rubric": {
                "type": "code",
                "required_keywords": ["def", "fibonacci", "return"],
                "banned_phrases": ["As an AI"],
            },
        }
        response = "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
        score = suite.score_response(response, task)
        assert score == 1.0

    def test_code_scoring_without_code_structure(self, suite):
        """Text response for code task should lose structure points."""
        task = {
            "id": "code",
            "input": "Write fibonacci",
            "expected_output_keywords": ["def", "fibonacci", "return"],
            "category": "code_generation",
            "difficulty": 1,
            "rubric": {
                "type": "code",
                "required_keywords": ["fibonacci"],
                "banned_phrases": ["As an AI"],
            },
        }
        response = "The fibonacci sequence starts with 0, 1, 1, 2, 3..."
        score = suite.score_response(response, task)
        # Has keyword but no code structure
        assert score < 1.0
        assert score > 0.0


# ---------------------------------------------------------------------------
# Test: personality scoring
# ---------------------------------------------------------------------------

class TestPersonalityScoring:
    """Tests for personality consistency scoring."""

    def test_catches_hedging_phrases(self, suite):
        """Banned phrases like 'As an AI' should reduce score."""
        task = {
            "id": "pers",
            "input": "Who are you?",
            "expected_output_keywords": ["Shadow"],
            "category": "personality_consistency",
            "difficulty": 1,
            "rubric": {
                "type": "personality",
                "required_keywords": ["Shadow"],
                "banned_phrases": ["As an AI", "I cannot", "language model"],
            },
        }
        good = "I am Shadow, your autonomous agent."
        bad = "As an AI language model, I am Shadow."

        good_score = suite.score_response(good, task)
        bad_score = suite.score_response(bad, task)
        assert good_score > bad_score
        # Bad response has banned phrases, should lose 0.4
        assert bad_score < 0.7

    def test_personality_with_desired_keywords(self, suite):
        """Desired keywords should provide bonus points."""
        task = {
            "id": "pers",
            "input": "Who are you?",
            "expected_output_keywords": ["Shadow", "Master"],
            "category": "personality_consistency",
            "difficulty": 1,
            "rubric": {
                "type": "personality",
                "required_keywords": ["Shadow"],
                "desired_keywords": ["Master", "purpose"],
                "banned_phrases": ["As an AI"],
            },
        }
        with_desired = "I am Shadow, Master. Built with purpose."
        without_desired = "I am Shadow."

        score_with = suite.score_response(with_desired, task)
        score_without = suite.score_response(without_desired, task)
        assert score_with > score_without

    def test_personality_all_banned_present(self, suite):
        """Response full of banned phrases should score very low."""
        task = {
            "id": "pers",
            "input": "test",
            "expected_output_keywords": [],
            "category": "personality_consistency",
            "difficulty": 1,
            "rubric": {
                "type": "personality",
                "required_keywords": ["Shadow"],
                "banned_phrases": ["As an AI", "I cannot", "I'm sorry"],
            },
        }
        response = "As an AI, I cannot help. I'm sorry."
        score = suite.score_response(response, task)
        assert score < 0.5


# ---------------------------------------------------------------------------
# Test: math scoring
# ---------------------------------------------------------------------------

class TestMathScoring:
    """Tests for math/exact-answer scoring."""

    def test_correct_numeric_answer(self, suite):
        """Correct numeric answer should score 1.0."""
        task = {
            "id": "math",
            "input": "What is 347 * 28?",
            "expected_output_keywords": ["9716"],
            "category": "math_logic",
            "difficulty": 2,
            "rubric": {"type": "exact_answer", "answer": "9716"},
        }
        assert suite.score_response("347 * 28 = 9716", task) == 1.0

    def test_incorrect_numeric_answer(self, suite):
        """Wrong numeric answer should score 0.0."""
        task = {
            "id": "math",
            "input": "What is 347 * 28?",
            "expected_output_keywords": ["9716"],
            "category": "math_logic",
            "difficulty": 2,
            "rubric": {"type": "exact_answer", "answer": "9716"},
        }
        assert suite.score_response("347 * 28 = 9700", task) == 0.0

    def test_answer_embedded_in_text(self, suite):
        """Answer within longer text should still match."""
        task = {
            "id": "math",
            "input": "Sequence?",
            "expected_output_keywords": ["162"],
            "category": "math_logic",
            "difficulty": 3,
            "rubric": {"type": "exact_answer", "answer": "162"},
        }
        assert suite.score_response(
            "The pattern is multiply by 3, so the next number is 162.", task
        ) == 1.0


# ---------------------------------------------------------------------------
# Test: save/load round-trip
# ---------------------------------------------------------------------------

class TestSaveLoadRoundTrip:
    """Tests for saving and loading benchmark results."""

    def test_save_creates_file(self, mock_orchestrator, tmp_path):
        """save_results should create a JSON file."""
        suite = BenchmarkSuite(mock_orchestrator, {"model_name": "test"})
        suite._benchmarks_dir = tmp_path

        results = {
            "overall_score": 0.75,
            "category_scores": {"code_generation": 0.8},
            "per_task_results": [],
            "timestamp": "2026-04-11T12:00:00",
            "model_info": "test",
            "total_tasks": 50,
            "run_duration_seconds": 10.0,
        }
        filepath = suite.save_results(results)
        assert Path(filepath).exists()

        with open(filepath, "r") as f:
            loaded = json.load(f)
        assert loaded["overall_score"] == 0.75

    def test_save_handles_duplicate_dates(self, mock_orchestrator, tmp_path):
        """Saving twice on same date should create separate files."""
        suite = BenchmarkSuite(mock_orchestrator)
        suite._benchmarks_dir = tmp_path

        results = {
            "overall_score": 0.5,
            "category_scores": {},
            "per_task_results": [],
            "timestamp": "2026-04-11T12:00:00",
            "model_info": "test",
            "total_tasks": 50,
            "run_duration_seconds": 5.0,
        }
        path1 = suite.save_results(results)
        path2 = suite.save_results(results)
        assert path1 != path2
        assert Path(path1).exists()
        assert Path(path2).exists()

    def test_load_history_returns_sorted(self, mock_orchestrator, tmp_path):
        """load_history should return results sorted by timestamp."""
        suite = BenchmarkSuite(mock_orchestrator)
        suite._benchmarks_dir = tmp_path

        # Write two result files
        for date, score in [("2026-03-01", 0.6), ("2026-02-01", 0.5)]:
            fp = tmp_path / f"benchmark_{date}.json"
            with open(fp, "w") as f:
                json.dump({
                    "overall_score": score,
                    "timestamp": f"{date}T00:00:00",
                }, f)

        history = suite.load_history()
        assert len(history) == 2
        assert history[0]["overall_score"] == 0.5  # Feb first
        assert history[1]["overall_score"] == 0.6  # Mar second

    def test_load_history_skips_tasks_file(self, mock_orchestrator, tmp_path):
        """load_history should not include benchmark_tasks.json."""
        suite = BenchmarkSuite(mock_orchestrator)
        suite._benchmarks_dir = tmp_path

        # Write tasks file (should be skipped)
        tasks_file = tmp_path / "benchmark_tasks.json"
        with open(tasks_file, "w") as f:
            json.dump([{"id": "test"}], f)

        # Write a real result
        result_file = tmp_path / "benchmark_2026-04-01.json"
        with open(result_file, "w") as f:
            json.dump({"overall_score": 0.7, "timestamp": "2026-04-01"}, f)

        history = suite.load_history()
        assert len(history) == 1
        assert history[0]["overall_score"] == 0.7

    def test_load_history_skips_corrupt_files(self, mock_orchestrator, tmp_path):
        """Corrupt JSON files should be skipped gracefully."""
        suite = BenchmarkSuite(mock_orchestrator)
        suite._benchmarks_dir = tmp_path

        corrupt = tmp_path / "benchmark_2026-01-01.json"
        with open(corrupt, "w") as f:
            f.write("{bad json")

        valid = tmp_path / "benchmark_2026-02-01.json"
        with open(valid, "w") as f:
            json.dump({"overall_score": 0.8, "timestamp": "2026-02-01"}, f)

        history = suite.load_history()
        assert len(history) == 1


# ---------------------------------------------------------------------------
# Test: compare_runs
# ---------------------------------------------------------------------------

class TestCompareRuns:
    """Tests for comparing two benchmark runs."""

    def test_detects_improvement(self, suite):
        """compare_runs should detect when scores go up."""
        run_a = {
            "overall_score": 0.5,
            "category_scores": {"code_generation": 0.4},
            "per_task_results": [
                {"task_id": "code_01", "score": 0.4},
                {"task_id": "code_02", "score": 0.6},
            ],
            "timestamp": "2026-01-01",
        }
        run_b = {
            "overall_score": 0.8,
            "category_scores": {"code_generation": 0.9},
            "per_task_results": [
                {"task_id": "code_01", "score": 0.9},
                {"task_id": "code_02", "score": 0.7},
            ],
            "timestamp": "2026-02-01",
        }
        result = suite.compare_runs(run_a, run_b)
        assert result["overall_delta"] > 0
        assert "improved" in result["summary"]
        assert len(result["improved"]) >= 1

    def test_detects_regression(self, suite):
        """compare_runs should detect when scores go down."""
        run_a = {
            "overall_score": 0.9,
            "category_scores": {"math_logic": 0.95},
            "per_task_results": [
                {"task_id": "math_01", "score": 0.95},
            ],
            "timestamp": "2026-01-01",
        }
        run_b = {
            "overall_score": 0.5,
            "category_scores": {"math_logic": 0.4},
            "per_task_results": [
                {"task_id": "math_01", "score": 0.4},
            ],
            "timestamp": "2026-02-01",
        }
        result = suite.compare_runs(run_a, run_b)
        assert result["overall_delta"] < 0
        assert "regressed" in result["summary"]
        assert len(result["regressed"]) >= 1

    def test_detects_unchanged(self, suite):
        """compare_runs should detect unchanged scores."""
        run_a = {
            "overall_score": 0.7,
            "category_scores": {"general_knowledge": 0.7},
            "per_task_results": [
                {"task_id": "know_01", "score": 0.7},
            ],
            "timestamp": "2026-01-01",
        }
        run_b = {
            "overall_score": 0.7,
            "category_scores": {"general_knowledge": 0.7},
            "per_task_results": [
                {"task_id": "know_01", "score": 0.7},
            ],
            "timestamp": "2026-02-01",
        }
        result = suite.compare_runs(run_a, run_b)
        assert abs(result["overall_delta"]) < 0.02
        assert "unchanged" in result["summary"]

    def test_comparison_has_all_fields(self, suite):
        """Comparison result must have all required fields."""
        run_a = {
            "overall_score": 0.5,
            "category_scores": {},
            "per_task_results": [],
            "timestamp": "2026-01-01",
        }
        run_b = {
            "overall_score": 0.6,
            "category_scores": {},
            "per_task_results": [],
            "timestamp": "2026-02-01",
        }
        result = suite.compare_runs(run_a, run_b)
        assert "overall_delta" in result
        assert "category_deltas" in result
        assert "improved" in result
        assert "regressed" in result
        assert "unchanged" in result
        assert "summary" in result


# ---------------------------------------------------------------------------
# Test: run_benchmark (with mock orchestrator)
# ---------------------------------------------------------------------------

class TestRunBenchmark:
    """Tests for running benchmarks with a mock orchestrator."""

    @pytest.mark.asyncio
    async def test_run_returns_all_fields(self, suite):
        """run_benchmark result must have all expected fields."""
        tasks = [
            {
                "id": "test_01",
                "input": "What is the capital of Australia?",
                "expected_output_keywords": ["Canberra"],
                "category": "general_knowledge",
                "difficulty": 1,
                "rubric": {"type": "exact_answer", "answer": "Canberra"},
            },
        ]
        result = await suite.run_benchmark(tasks)
        assert "overall_score" in result
        assert "category_scores" in result
        assert "per_task_results" in result
        assert "timestamp" in result
        assert "model_info" in result
        assert "total_tasks" in result
        assert "run_duration_seconds" in result
        assert result["total_tasks"] == 1

    @pytest.mark.asyncio
    async def test_run_scores_correct_answer(self, suite):
        """A correct answer should get score 1.0 from run_benchmark."""
        tasks = [
            {
                "id": "math_test",
                "input": "What is 347 * 28?",
                "expected_output_keywords": ["9716"],
                "category": "math_logic",
                "difficulty": 2,
                "rubric": {"type": "exact_answer", "answer": "9716"},
            },
        ]
        result = await suite.run_benchmark(tasks)
        assert result["per_task_results"][0]["score"] == 1.0

    @pytest.mark.asyncio
    async def test_run_handles_orchestrator_error(self, mock_orchestrator):
        """If orchestrator raises, score should be 0 (not crash)."""
        mock_orchestrator.process_input = AsyncMock(
            side_effect=RuntimeError("LLM offline")
        )
        suite = BenchmarkSuite(mock_orchestrator, {"model_name": "broken"})
        tasks = [
            {
                "id": "err_test",
                "input": "test",
                "expected_output_keywords": ["answer"],
                "category": "general_knowledge",
                "difficulty": 1,
                "rubric": {"type": "exact_answer", "answer": "answer"},
            },
        ]
        result = await suite.run_benchmark(tasks)
        # Should not crash, should record a score
        assert len(result["per_task_results"]) == 1
        assert result["per_task_results"][0]["score"] == 0.0

    @pytest.mark.asyncio
    async def test_run_with_multiple_categories(self, suite):
        """run_benchmark should produce category_scores for each category."""
        tasks = [
            {
                "id": "code_test",
                "input": "Write a Python function called fibonacci that takes n and returns the nth Fibonacci number.",
                "expected_output_keywords": ["def", "fibonacci"],
                "category": "code_generation",
                "difficulty": 1,
                "rubric": {
                    "type": "code",
                    "required_keywords": ["def", "fibonacci", "return"],
                    "banned_phrases": ["As an AI"],
                },
            },
            {
                "id": "math_test",
                "input": "What is the square root of 144?",
                "expected_output_keywords": ["12"],
                "category": "math_logic",
                "difficulty": 1,
                "rubric": {"type": "exact_answer", "answer": "12"},
            },
        ]
        result = await suite.run_benchmark(tasks)
        assert "code_generation" in result["category_scores"]
        assert "math_logic" in result["category_scores"]


# ---------------------------------------------------------------------------
# Test: trend_report
# ---------------------------------------------------------------------------

class TestTrendReport:
    """Tests for the trend report generator."""

    def test_no_history_message(self, mock_orchestrator, tmp_path):
        """Empty history should return no-data message."""
        suite = BenchmarkSuite(mock_orchestrator)
        suite._benchmarks_dir = tmp_path
        report = suite.trend_report()
        assert "No benchmark history" in report

    def test_single_run_report(self, mock_orchestrator, tmp_path):
        """Single run should show scores without deltas."""
        suite = BenchmarkSuite(mock_orchestrator)
        suite._benchmarks_dir = tmp_path

        fp = tmp_path / "benchmark_2026-04-01.json"
        with open(fp, "w") as f:
            json.dump({
                "overall_score": 0.75,
                "category_scores": {"code_generation": 0.8},
                "timestamp": "2026-04-01T12:00:00",
                "model_info": "phi4-mini",
            }, f)

        report = suite.trend_report()
        assert "75.00%" in report
        assert "phi4-mini" in report

    def test_multi_run_shows_trends(self, mock_orchestrator, tmp_path):
        """Multiple runs should show arrows and trends."""
        suite = BenchmarkSuite(mock_orchestrator)
        suite._benchmarks_dir = tmp_path

        for date, score in [("2026-03-01", 0.5), ("2026-04-01", 0.8)]:
            fp = tmp_path / f"benchmark_{date}.json"
            with open(fp, "w") as f:
                json.dump({
                    "overall_score": score,
                    "category_scores": {"code_generation": score},
                    "timestamp": f"{date}T00:00:00",
                    "model_info": "test",
                }, f)

        report = suite.trend_report()
        assert "Trend" in report
        assert "↑" in report  # Should show improvement arrow
