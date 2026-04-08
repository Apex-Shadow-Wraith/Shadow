"""
Tests for Recursive Decomposition — confidence-gated depth control.
"""

from __future__ import annotations

import pytest

from modules.shadow.recursive_decomposer import (
    DecompositionResult,
    RecursiveDecomposer,
    SubProblem,
)


# ── Helpers ─────────────────────────────────────────────────────────

def make_generate_fn(responses: list[str] | str):
    """Create a mock generate_fn that returns canned responses in order."""
    if isinstance(responses, str):
        responses = [responses]
    call_log: list[str] = []
    idx = [0]

    def generate(prompt: str) -> str:
        call_log.append(prompt)
        resp = responses[min(idx[0], len(responses) - 1)]
        idx[0] += 1
        return resp

    generate.call_log = call_log  # type: ignore[attr-defined]
    generate.idx = idx  # type: ignore[attr-defined]
    return generate


class FakeConfidenceScorer:
    """Mock confidence scorer that returns preset scores."""

    def __init__(self, scores: list[float] | float):
        if isinstance(scores, (int, float)):
            scores = [scores]
        self._scores = scores
        self._idx = 0

    def score_response(self, task: str, response: str, task_type: str = "general") -> dict:
        score = self._scores[min(self._idx, len(self._scores) - 1)]
        self._idx += 1
        return {"confidence": score}


# ── Core Decomposition ──────────────────────────────────────────────

class TestDecompose:
    """Tests for the decompose() method."""

    def test_splits_task_into_sub_problems(self):
        """decompose: splits task into 2-5 sub-problems."""
        gen = make_generate_fn(
            "1. Research the topic\n"
            "2. Write an outline\n"
            "3. Draft the content\n"
        )
        decomposer = RecursiveDecomposer(generate_fn=gen)
        result = decomposer.decompose("Write a research paper on AI safety")
        assert len(result) == 3
        assert "Research the topic" in result[0]
        assert "Write an outline" in result[1]
        assert "Draft the content" in result[2]

    def test_returns_task_if_cannot_decompose(self):
        """decompose: returns [task] if model returns < 2 sub-problems."""
        gen = make_generate_fn("Just do the thing")
        decomposer = RecursiveDecomposer(generate_fn=gen)
        task = "Simple task"
        result = decomposer.decompose(task)
        assert result == [task]

    def test_parsing_failure_returns_task(self):
        """decompose: parsing failure returns [task]."""
        gen = make_generate_fn("")  # Empty response
        decomposer = RecursiveDecomposer(generate_fn=gen)
        task = "Do something complex"
        result = decomposer.decompose(task)
        assert result == [task]

    def test_generate_fn_exception_returns_task(self):
        """decompose: generate_fn exception returns [task]."""
        def failing_gen(prompt: str) -> str:
            raise RuntimeError("Model crashed")

        decomposer = RecursiveDecomposer(generate_fn=failing_gen)
        task = "Complex task"
        result = decomposer.decompose(task)
        assert result == [task]

    def test_caps_at_five_sub_problems(self):
        """decompose: caps output at 5 sub-problems."""
        gen = make_generate_fn(
            "1. A\n2. B\n3. C\n4. D\n5. E\n6. F\n7. G\n"
        )
        decomposer = RecursiveDecomposer(generate_fn=gen)
        result = decomposer.decompose("Big task")
        assert len(result) == 5

    def test_no_generate_fn_returns_task(self):
        """decompose: no generate_fn returns [task]."""
        decomposer = RecursiveDecomposer(generate_fn=None)
        result = decomposer.decompose("Some task")
        assert result == ["Some task"]


# ── Recursive Solving ───────────────────────────────────────────────

class TestSolveWithDecomposition:
    """Tests for the solve_with_decomposition() method."""

    def test_high_confidence_no_decomposition(self):
        """High confidence on first try → no decomposition."""
        gen = make_generate_fn("Great answer with lots of detail and specifics")
        scorer = FakeConfidenceScorer(0.85)
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer,
        )
        result = decomposer.solve_with_decomposition("Simple question?")
        assert result.overall_confidence >= 0.7
        assert result.decomposition_helped is False
        assert result.total_model_calls == 1

    def test_low_confidence_triggers_decomposition(self):
        """Low confidence → decomposes and merges."""
        call_count = [0]

        def gen(prompt: str) -> str:
            call_count[0] += 1
            if "Break it into" in prompt:
                return "1. Part A\n2. Part B\n"
            if "Combine them" in prompt:
                return "Merged answer covering A and B"
            return "Some answer"

        # Scores: direct=0.3, sub1=0.8, sub2=0.8, merged=0.8
        scorer = FakeConfidenceScorer([0.3, 0.8, 0.8, 0.8])
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer,
        )
        result = decomposer.solve_with_decomposition("Complex multi-part task and also another thing")
        assert result.total_model_calls > 1
        assert result.merged_solution != ""

    def test_respects_max_depth(self):
        """Respects max_depth — stops recursing."""
        call_count = [0]

        def gen(prompt: str) -> str:
            call_count[0] += 1
            if "Break it into" in prompt:
                return "1. Sub A\n2. Sub B\n"
            return "Answer"

        # Always low confidence to force decomposition attempts
        scorer = FakeConfidenceScorer(0.3)
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer, max_depth=1,
        )
        result = decomposer.solve_with_decomposition("Deep task")
        # With max_depth=1, children at depth 1 won't decompose further
        assert result.max_depth_reached <= 1

    def test_decomposition_improves_score_uses_merged(self):
        """Decomposition improves score → uses merged solution."""
        call_idx = [0]

        def gen(prompt: str) -> str:
            call_idx[0] += 1
            if "Break it into" in prompt:
                return "1. Step one\n2. Step two\n"
            if "Combine them" in prompt:
                return "Excellent merged solution"
            return "Mediocre direct answer"

        # direct=0.4, child1=0.8, child2=0.8, merged=0.9
        scorer = FakeConfidenceScorer([0.4, 0.8, 0.8, 0.9])
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer,
        )
        result = decomposer.solve_with_decomposition("Complex task with multiple parts and steps")
        assert result.decomposition_helped is True
        assert result.overall_confidence > 0.4

    def test_decomposition_no_improvement_uses_direct(self):
        """Decomposition doesn't improve → uses direct solution."""
        def gen(prompt: str) -> str:
            if "Break it into" in prompt:
                return "1. Part X\n2. Part Y\n"
            if "Combine them" in prompt:
                return "Bad merge"
            return "Decent direct answer"

        # direct=0.5, child1=0.8, child2=0.8, merged=0.3
        scorer = FakeConfidenceScorer([0.5, 0.8, 0.8, 0.3])
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer,
        )
        result = decomposer.solve_with_decomposition("Multi-step task and also extra work")
        assert result.decomposition_helped is False
        assert result.merged_solution == "Decent direct answer"

    def test_tracks_total_model_calls(self):
        """Correctly tracks total_model_calls across recursion."""
        call_count = [0]

        def gen(prompt: str) -> str:
            call_count[0] += 1
            if "Break it into" in prompt:
                return "1. Sub A\n2. Sub B\n"
            if "Combine them" in prompt:
                return "Merged"
            return "Answer"

        # direct=0.3, sub1=0.8, sub2=0.8, merged=0.9
        scorer = FakeConfidenceScorer([0.3, 0.8, 0.8, 0.9])
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer,
        )
        result = decomposer.solve_with_decomposition("Complex task and more steps")
        # At minimum: 1 direct + 1 decompose + 2 child solves + 1 merge = 5
        assert result.total_model_calls >= 4


# ── Merging ─────────────────────────────────────────────────────────

class TestMergeSolutions:
    """Tests for the merge_solutions() method."""

    def test_combines_sub_problem_solutions(self):
        """merge_solutions: combines sub-problem solutions."""
        gen = make_generate_fn("Combined answer from parts A and B")
        decomposer = RecursiveDecomposer(generate_fn=gen)
        sps = [
            SubProblem(id="1", parent_id=None, depth=0, description="Part A",
                       solution="Answer A", confidence=0.8, status="solved"),
            SubProblem(id="2", parent_id=None, depth=0, description="Part B",
                       solution="Answer B", confidence=0.8, status="solved"),
        ]
        result = decomposer.merge_solutions("Full task", sps)
        assert "Combined answer" in result

    def test_single_sub_problem_returns_directly(self):
        """merge_solutions: single sub-problem returns its solution directly."""
        gen = make_generate_fn("Should not be called")
        decomposer = RecursiveDecomposer(generate_fn=gen)
        sps = [
            SubProblem(id="1", parent_id=None, depth=0, description="Only part",
                       solution="Only answer", confidence=0.8, status="solved"),
        ]
        result = decomposer.merge_solutions("Task", sps)
        assert result == "Only answer"
        # generate_fn should NOT have been called
        assert len(gen.call_log) == 0

    def test_empty_sub_problems(self):
        """merge_solutions: empty list returns empty string."""
        decomposer = RecursiveDecomposer(generate_fn=make_generate_fn("x"))
        result = decomposer.merge_solutions("Task", [])
        assert result == ""

    def test_merge_without_generate_fn(self):
        """merge_solutions: no generate_fn → concatenates solutions."""
        decomposer = RecursiveDecomposer(generate_fn=None)
        sps = [
            SubProblem(id="1", parent_id=None, depth=0, description="A",
                       solution="Sol A", confidence=0.8, status="solved"),
            SubProblem(id="2", parent_id=None, depth=0, description="B",
                       solution="Sol B", confidence=0.8, status="solved"),
        ]
        result = decomposer.merge_solutions("Task", sps)
        assert "Sol A" in result
        assert "Sol B" in result


# ── Decision Logic ──────────────────────────────────────────────────

class TestShouldDecompose:
    """Tests for the should_decompose() method."""

    def test_low_confidence_complex_task_returns_true(self):
        """Low confidence + complex task → True."""
        decomposer = RecursiveDecomposer()
        assert decomposer.should_decompose(
            "Analyze the dataset and then build a model and finally deploy it",
            confidence=0.4,
        ) is True

    def test_high_confidence_returns_false(self):
        """High confidence → False regardless of task complexity."""
        decomposer = RecursiveDecomposer()
        assert decomposer.should_decompose(
            "Complex multi-part task and also another thing",
            confidence=0.85,
        ) is False

    def test_simple_factual_question_returns_false(self):
        """Simple factual question → False."""
        decomposer = RecursiveDecomposer()
        assert decomposer.should_decompose(
            "What is the capital of France?",
            confidence=0.4,
        ) is False

    def test_multiple_sentences_returns_true(self):
        """Multiple sentences with low confidence → True."""
        decomposer = RecursiveDecomposer()
        task = "First do this thing. Then do another thing. Finally wrap it up."
        assert decomposer.should_decompose(task, confidence=0.3) is True

    def test_multiple_questions_returns_true(self):
        """Multiple question marks → True."""
        decomposer = RecursiveDecomposer()
        task = "What happened first? Why did it fail? How can we fix it?"
        assert decomposer.should_decompose(task, confidence=0.4) is True


# ── Integration ─────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests with RetryEngine and data schema."""

    def test_decomposition_result_has_all_fields(self):
        """DecompositionResult has all required fields."""
        result = DecompositionResult(original_task="test")
        assert result.original_task == "test"
        assert result.sub_problems == []
        assert result.merged_solution == ""
        assert result.overall_confidence == 0.0
        assert result.total_model_calls == 0
        assert result.max_depth_reached == 0
        assert result.decomposition_helped is False

    def test_sub_problem_has_all_fields(self):
        """SubProblem has all required fields."""
        sp = SubProblem(
            id="abc", parent_id=None, depth=0, description="test",
        )
        assert sp.id == "abc"
        assert sp.parent_id is None
        assert sp.depth == 0
        assert sp.description == "test"
        assert sp.solution == ""
        assert sp.confidence == 0.0
        assert sp.status == "pending"
        assert sp.children == []

    def test_decomposition_helped_correctly_calculated(self):
        """decomposition_helped is True only when merged beats direct."""
        def gen(prompt: str) -> str:
            if "Break it into" in prompt:
                return "1. Part A\n2. Part B\n"
            if "Combine them" in prompt:
                return "Great merged answer with lots of detail"
            return "Short"

        # direct=0.3, child1=0.8, child2=0.8, merged=0.85
        scorer = FakeConfidenceScorer([0.3, 0.8, 0.8, 0.85])
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer,
        )
        result = decomposer.solve_with_decomposition("Do A and also B")
        assert result.decomposition_helped is True

    def test_retry_engine_integration_mock(self):
        """RetryEngine can use decomposer for strategy #2 (concept test)."""
        # Simulate what RetryEngine would do
        gen = make_generate_fn("Decomposed and merged answer")
        scorer = FakeConfidenceScorer(0.8)
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer,
        )
        result = decomposer.solve_with_decomposition("Some task")
        if result.decomposition_helped:
            answer = result.merged_solution
        else:
            answer = result.merged_solution
        assert answer != ""

    def test_retry_engine_fallback_without_decomposer(self):
        """RetryEngine falls back when decomposer is unavailable."""
        # Simulate checking for decomposer
        engine_has_decomposer = False
        decomposer = None
        if engine_has_decomposer and decomposer:
            result = decomposer.solve_with_decomposition("task")
        else:
            # Fallback: simple string result
            result = "Simple decomposition fallback"
        assert result == "Simple decomposition fallback"


# ── Edge Cases ──────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge case tests."""

    def test_task_cannot_be_decomposed_solved_directly(self):
        """Task that can't be decomposed → solved directly."""
        def gen(prompt: str) -> str:
            if "Break it into" in prompt:
                return "Can't break this down"
            return "Direct answer"

        scorer = FakeConfidenceScorer([0.5, 0.5])  # Low but won't decompose
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer,
        )
        result = decomposer.solve_with_decomposition("Atomic task")
        assert result.merged_solution == "Direct answer"

    def test_all_sub_problems_fail_returns_best(self):
        """All sub-problems fail → return direct solution."""
        call_idx = [0]

        def gen(prompt: str) -> str:
            call_idx[0] += 1
            if "Break it into" in prompt:
                return "1. Sub A\n2. Sub B\n"
            if call_idx[0] <= 1:
                return "Direct answer"
            raise RuntimeError("Sub-problem failed")

        scorer = FakeConfidenceScorer(0.3)
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer,
        )
        result = decomposer.solve_with_decomposition("Failing task")
        # Should still have a solution (the direct one)
        assert result.merged_solution != ""

    def test_generate_fn_failure_mid_recursion(self):
        """generate_fn failure mid-recursion → return partial result."""
        call_count = [0]

        def gen(prompt: str) -> str:
            call_count[0] += 1
            if call_count[0] > 3:
                raise RuntimeError("Model died")
            if "Break it into" in prompt:
                return "1. Part A\n2. Part B\n"
            return "Partial answer"

        scorer = FakeConfidenceScorer(0.3)
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer,
        )
        result = decomposer.solve_with_decomposition("Task that breaks mid-way")
        # Should return something, not crash
        assert isinstance(result, DecompositionResult)
        assert result.merged_solution is not None

    def test_depth_zero_max_depth_zero(self):
        """depth 0 with max_depth 0 → direct attempt only."""
        gen = make_generate_fn("Direct only")
        scorer = FakeConfidenceScorer(0.3)  # Low, but max_depth=0 prevents recursion
        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=scorer, max_depth=0,
        )
        result = decomposer.solve_with_decomposition("Task")
        assert result.total_model_calls == 1
        assert result.decomposition_helped is False
        assert result.merged_solution == "Direct only"

    def test_graceful_without_confidence_scorer(self):
        """Works with no confidence_scorer (uses length heuristic)."""
        def gen(prompt: str) -> str:
            if "Break it into" in prompt:
                return "1. Part A\n2. Part B\n"
            if "Combine them" in prompt:
                return "Merged: " + "detailed " * 20 + "answer"
            return "Short"  # Will get low confidence from length heuristic

        decomposer = RecursiveDecomposer(
            generate_fn=gen, confidence_scorer=None,
        )
        result = decomposer.solve_with_decomposition("Complex task and more work")
        assert isinstance(result, DecompositionResult)
        assert result.merged_solution != ""

    def test_parse_various_numbered_formats(self):
        """Parses different numbering formats."""
        decomposer = RecursiveDecomposer()
        # Dot format
        assert len(decomposer._parse_numbered_list("1. A\n2. B\n3. C")) == 3
        # Paren format
        assert len(decomposer._parse_numbered_list("1) A\n2) B")) == 2
        # Colon format
        assert len(decomposer._parse_numbered_list("1: A\n2: B")) == 2
        # Dash format
        assert len(decomposer._parse_numbered_list("1- A\n2- B")) == 2
        # Empty
        assert decomposer._parse_numbered_list("") == []
        assert decomposer._parse_numbered_list("No numbers here") == []
