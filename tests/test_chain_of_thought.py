"""
Tests for Chain-of-Thought Scaffolding
========================================
Verifies the multi-step reasoning pipeline, complexity estimation,
early exit, custom pipelines, and stats tracking.
"""

from __future__ import annotations

import pytest

from modules.shadow.chain_of_thought import ChainOfThought, ChainResult, ReasoningStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_generate(prompt: str, system_prompt: str = None) -> str:
    """Simple mock that echoes back a summary of the prompt."""
    return f"Response to: {prompt[:80]}"


def _failing_generate(prompt: str, system_prompt: str = None) -> str:
    """Generate function that always raises."""
    raise RuntimeError("Model unavailable")


def _counting_generate():
    """Returns a generate function that counts calls."""
    calls = []

    def gen(prompt: str, system_prompt: str = None) -> str:
        calls.append(prompt)
        return f"Step {len(calls)} output"

    gen.calls = calls
    return gen


class _MockConfidenceScorer:
    """Scorer that returns a fixed confidence value."""

    def __init__(self, value: float = 0.5):
        self.value = value

    def score(self, task: str, response: str) -> float:
        return self.value


class _SteppedConfidenceScorer:
    """Scorer that returns increasing confidence per call."""

    def __init__(self, values: list[float]):
        self._values = list(values)
        self._idx = 0

    def score(self, task: str, response: str) -> float:
        val = self._values[self._idx] if self._idx < len(self._values) else 0.5
        self._idx += 1
        return val


# ---------------------------------------------------------------------------
# Tests — Complex (4-step) pipeline
# ---------------------------------------------------------------------------

class TestComplexPipeline:
    """All 4 steps execute in order for complex tasks."""

    def test_four_steps_execute_in_order(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        result = cot.reason("Design a distributed cache system", complexity="complex")

        assert result.total_steps == 4
        assert [s.step_name for s in result.steps] == [
            "understand", "plan", "execute", "verify"
        ]
        for i, step in enumerate(result.steps, 1):
            assert step.step_number == i

    def test_each_step_receives_previous_output(self):
        gen = _counting_generate()
        cot = ChainOfThought(generate_fn=gen)
        result = cot.reason("Analyze this algorithm", complexity="complex")

        # Step 2 prompt should contain Step 1's output
        assert "Step 1 output" in result.steps[1].prompt
        # Step 3 prompt should contain Step 2's output
        assert "Step 2 output" in result.steps[2].prompt
        # Step 4 prompt should contain Step 3's output
        assert "Step 3 output" in result.steps[3].prompt

    def test_final_output_is_last_step_response(self):
        gen = _counting_generate()
        cot = ChainOfThought(generate_fn=gen)
        result = cot.reason("Complex task", complexity="complex")

        assert result.final_output == result.steps[-1].response
        assert result.final_output == "Step 4 output"


# ---------------------------------------------------------------------------
# Tests — Simple (1-step) pipeline
# ---------------------------------------------------------------------------

class TestSimplePipeline:
    """Only 1 step for simple tasks."""

    def test_single_step_only(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        result = cot.reason("What time is it?", complexity="simple")

        assert result.total_steps == 1
        assert result.steps[0].step_name == "execute"

    def test_simple_auto_detected(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        result = cot.reason("Hello", complexity="auto")

        assert result.total_steps == 1


# ---------------------------------------------------------------------------
# Tests — Moderate (2-step) pipeline
# ---------------------------------------------------------------------------

class TestModeratePipeline:
    """2 steps: understand + execute."""

    def test_two_steps(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        result = cot.reason("Explain how DNS works", complexity="moderate")

        assert result.total_steps == 2
        assert [s.step_name for s in result.steps] == ["understand", "execute"]

    def test_moderate_passes_understanding_to_execute(self):
        gen = _counting_generate()
        cot = ChainOfThought(generate_fn=gen)
        result = cot.reason("Some moderate task", complexity="moderate")

        # Step 2 should reference Step 1 output
        assert "Step 1 output" in result.steps[1].prompt


# ---------------------------------------------------------------------------
# Tests — Auto complexity detection
# ---------------------------------------------------------------------------

class TestEstimateComplexity:
    """Complexity auto-detection from task text."""

    def test_short_simple_question(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        assert cot.estimate_complexity("What is 2+2?") == "simple"

    def test_long_task_is_complex(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        long_task = "Please " + " ".join(["word"] * 250)
        assert cot.estimate_complexity(long_task) == "complex"

    def test_code_keywords_trigger_complex(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        assert cot.estimate_complexity("Write a function to sort a list") == "complex"

    def test_analysis_keyword_triggers_complex(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        assert cot.estimate_complexity("Analyze the performance of this query") == "complex"

    def test_medium_question_is_moderate(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        # 50-200 words, no complex keywords
        medium = "Explain the concept of " + " ".join(["something"] * 60)
        assert cot.estimate_complexity(medium) == "moderate"

    def test_auto_routes_correctly(self):
        gen = _counting_generate()
        cot = ChainOfThought(generate_fn=gen)

        # Complex task via auto
        result = cot.reason(
            "Design and implement a distributed caching algorithm",
            complexity="auto",
        )
        assert result.total_steps == 4  # complex

        # Simple task via auto
        result2 = cot.reason("Hi", complexity="auto")
        assert result2.total_steps == 1  # simple


# ---------------------------------------------------------------------------
# Tests — Early exit
# ---------------------------------------------------------------------------

class TestEarlyExit:
    """High confidence after a step can skip remaining steps."""

    def test_early_exit_skips_remaining_steps(self):
        # Confidence: step1=0.5, step2=0.95 (above threshold) → skip 3,4
        scorer = _SteppedConfidenceScorer([0.5, 0.95, 0.5, 0.5])
        cot = ChainOfThought(generate_fn=_mock_generate, confidence_scorer=scorer)
        result = cot.reason("Complex analysis task", complexity="complex")

        assert result.total_steps == 2
        assert result.used_shortcut is True

    def test_step1_never_skipped(self):
        # Even if step1 has high confidence, it should NOT trigger early exit
        scorer = _SteppedConfidenceScorer([0.99, 0.3, 0.3, 0.3])
        cot = ChainOfThought(generate_fn=_mock_generate, confidence_scorer=scorer)
        result = cot.reason("Complex task here", complexity="complex")

        # Step 1 should not cause early exit (step_number=1)
        assert result.total_steps >= 2

    def test_used_shortcut_false_when_no_early_exit(self):
        scorer = _MockConfidenceScorer(0.5)
        cot = ChainOfThought(generate_fn=_mock_generate, confidence_scorer=scorer)
        result = cot.reason("Complex task", complexity="complex")

        assert result.total_steps == 4
        assert result.used_shortcut is False

    def test_used_shortcut_set_correctly(self):
        # High confidence at step 3 → skip step 4
        scorer = _SteppedConfidenceScorer([0.3, 0.3, 0.95, 0.3])
        cot = ChainOfThought(generate_fn=_mock_generate, confidence_scorer=scorer)
        result = cot.reason("Complex task", complexity="complex")

        assert result.used_shortcut is True
        assert result.total_steps == 3


# ---------------------------------------------------------------------------
# Tests — ChainResult properties
# ---------------------------------------------------------------------------

class TestChainResult:
    """Result dataclass has correct metadata."""

    def test_correct_step_count_and_durations(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        result = cot.reason("Some task", complexity="complex")

        assert result.total_steps == 4
        assert result.total_duration > 0
        for step in result.steps:
            assert step.duration_seconds >= 0

    def test_task_stored_in_result(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        result = cot.reason("My specific task")

        assert result.task == "My specific task"

    def test_tokens_estimated_per_step(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        result = cot.reason("Calculate something", complexity="complex")

        for step in result.steps:
            assert step.tokens_estimated > 0


# ---------------------------------------------------------------------------
# Tests — Custom pipeline
# ---------------------------------------------------------------------------

class TestCustomPipeline:
    """reason_custom with user-defined steps."""

    def test_custom_three_steps(self):
        gen = _counting_generate()
        cot = ChainOfThought(generate_fn=gen)

        custom_steps = [
            {"name": "gather", "prompt_template": "Gather info about {task}"},
            {"name": "synthesize", "prompt_template": "Synthesize: {previous_output}"},
            {"name": "format", "prompt_template": "Format: {previous_output}"},
        ]
        result = cot.reason_custom("Research topic", custom_steps)

        assert result.total_steps == 3
        assert [s.step_name for s in result.steps] == ["gather", "synthesize", "format"]

    def test_custom_empty_steps_returns_error(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        result = cot.reason_custom("Task", steps=[])

        assert "Error" in result.final_output
        assert result.total_steps == 0

    def test_custom_previous_output_substitution(self):
        gen = _counting_generate()
        cot = ChainOfThought(generate_fn=gen)

        custom_steps = [
            {"name": "first", "prompt_template": "Start: {task}"},
            {"name": "second", "prompt_template": "Continue from: {previous_output}"},
        ]
        result = cot.reason_custom("My task", custom_steps)

        assert "Step 1 output" in result.steps[1].prompt


# ---------------------------------------------------------------------------
# Tests — Generate function behavior
# ---------------------------------------------------------------------------

class TestGenerateFunction:
    """Model call behavior and error handling."""

    def test_generate_called_once_per_step(self):
        gen = _counting_generate()
        cot = ChainOfThought(generate_fn=gen)
        cot.reason("Some task", complexity="complex")

        assert len(gen.calls) == 4

    def test_generate_failure_stops_chain(self):
        call_count = [0]

        def failing_on_step3(prompt, system_prompt=None):
            call_count[0] += 1
            if call_count[0] == 3:
                raise RuntimeError("Step 3 exploded")
            return f"Output {call_count[0]}"

        cot = ChainOfThought(generate_fn=failing_on_step3)
        result = cot.reason("Task", complexity="complex")

        # Should have 3 steps: 2 successful + 1 failed
        assert result.total_steps == 3
        assert "Error" in result.steps[2].response
        assert result.final_output == result.steps[-1].response

    def test_none_generate_fn_returns_error(self):
        cot = ChainOfThought(generate_fn=None)
        result = cot.reason("Some task")

        assert "Error" in result.final_output
        assert result.total_steps == 0


# ---------------------------------------------------------------------------
# Tests — Context handling
# ---------------------------------------------------------------------------

class TestContextHandling:
    """Context string properly passed through."""

    def test_context_in_step1_prompt(self):
        gen = _counting_generate()
        cot = ChainOfThought(generate_fn=gen)
        cot.reason("My task", context="Important background info", complexity="complex")

        assert "Important background info" in gen.calls[0]

    def test_empty_context_no_error(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        result = cot.reason("Task", context="")

        assert result.total_steps >= 1


# ---------------------------------------------------------------------------
# Tests — Stats tracking
# ---------------------------------------------------------------------------

class TestReasoningStats:
    """get_reasoning_stats returns valid data."""

    def test_stats_empty_history(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        stats = cot.get_reasoning_stats()

        assert stats["total_reasoning_sessions"] == 0
        assert stats["avg_steps_used"] == 0.0

    def test_stats_after_multiple_calls(self):
        cot = ChainOfThought(generate_fn=_mock_generate)
        cot.reason("Simple task", complexity="simple")
        cot.reason("Complex task", complexity="complex")
        cot.reason("Moderate task", complexity="moderate")

        stats = cot.get_reasoning_stats()

        assert stats["total_reasoning_sessions"] == 3
        assert stats["avg_steps_used"] > 0
        assert stats["avg_duration_per_step"] > 0
        assert stats["complexity_distribution"]["simple"] == 1
        assert stats["complexity_distribution"]["complex"] == 1
        assert stats["complexity_distribution"]["moderate"] == 1

    def test_shortcut_rate_tracked(self):
        scorer = _SteppedConfidenceScorer([0.5, 0.95])
        cot = ChainOfThought(generate_fn=_mock_generate, confidence_scorer=scorer)
        cot.reason("Complex task", complexity="complex")

        stats = cot.get_reasoning_stats()
        assert stats["shortcut_rate"] == 1.0  # 1 out of 1 used shortcut
