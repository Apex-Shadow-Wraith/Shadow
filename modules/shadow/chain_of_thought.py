"""
Chain-of-Thought Scaffolding — Structured Multi-Step Reasoning
================================================================
Breaks complex reasoning into explicit sequential steps, each a separate
LLM call. A 26B model doing 4 focused steps outperforms the same model
doing 1 unfocused pass.

Default 4-step pipeline:
  1. Understand — parse what's being asked
  2. Plan — choose approach and identify pitfalls
  3. Execute — produce the solution
  4. Verify — check correctness and edge cases

Supports early exit (confidence >= 0.9), custom pipelines, and
complexity-based step selection (simple=1, moderate=2, complex=4).

Feeds into: Omen (code tasks), Cipher (math), Growth Engine (stats).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("shadow.chain_of_thought")

# Keywords that suggest complex reasoning is needed
_COMPLEX_KEYWORDS = frozenset({
    "compare", "analyze", "design", "architect", "optimize",
    "implement", "refactor", "debug", "algorithm", "calculate",
    "prove", "derive", "evaluate", "synthesize", "trade-off",
    "multi-step", "pipeline", "workflow", "migration",
})

_CODE_KEYWORDS = frozenset({
    "code", "function", "class", "module", "api", "endpoint",
    "database", "query", "sql", "script", "test", "bug", "error",
    "exception", "stack trace", "regex", "parse",
})


@dataclass
class ReasoningStep:
    """A single step in the chain-of-thought pipeline."""

    step_number: int
    step_name: str  # "understand", "plan", "execute", "verify"
    prompt: str  # what was sent to the model
    response: str  # model's output
    confidence: float  # score from confidence_scorer if available
    duration_seconds: float
    tokens_estimated: int


@dataclass
class ChainResult:
    """Complete result of a chain-of-thought reasoning pass."""

    task: str
    steps: list[ReasoningStep] = field(default_factory=list)
    final_output: str = ""
    total_duration: float = 0.0
    total_steps: int = 0
    used_shortcut: bool = False


class ChainOfThought:
    """Break complex reasoning into explicit sequential steps.

    Each step is a SEPARATE model call — the whole point is focused
    attention per step, not one giant prompt.
    """

    # Confidence threshold for early exit
    EARLY_EXIT_THRESHOLD = 0.9

    def __init__(
        self,
        generate_fn: Callable | None = None,
        confidence_scorer: Any = None,
    ) -> None:
        """Initialize the chain-of-thought scaffolding.

        Args:
            generate_fn: Callable(prompt, system_prompt=None) -> str.
                         Calls the model for each reasoning step.
            confidence_scorer: Optional scorer that provides a score()
                               method returning a float 0.0-1.0.
        """
        self._generate_fn = generate_fn
        self._confidence_scorer = confidence_scorer
        self._history: list[ChainResult] = []

    def reason(
        self,
        task: str,
        context: str = "",
        complexity: str = "auto",
    ) -> ChainResult:
        """Main entry point for chain-of-thought reasoning.

        Args:
            task: The task/question to reason about.
            context: Additional context to provide.
            complexity: "simple", "moderate", "complex", or "auto".

        Returns:
            ChainResult with all steps and final output.
        """
        if self._generate_fn is None:
            result = ChainResult(task=task)
            result.final_output = "Error: no generate_fn provided"
            self._history.append(result)
            return result

        if complexity == "auto":
            complexity = self.estimate_complexity(task)

        if complexity == "simple":
            steps = self._build_simple_steps(task, context)
        elif complexity == "moderate":
            steps = self._build_moderate_steps(task, context)
        else:
            steps = self._build_complex_steps(task, context)

        return self._execute_pipeline(task, steps)

    def reason_custom(
        self,
        task: str,
        steps: list[dict],
        context: str = "",
    ) -> ChainResult:
        """Run a custom step pipeline for domain-specific reasoning.

        Args:
            task: The task/question to reason about.
            steps: List of dicts with 'name' and 'prompt_template' keys.
                   Templates can reference {task}, {context}, {previous_output}.
            context: Additional context to provide.

        Returns:
            ChainResult with all steps and final output.
        """
        if not steps:
            result = ChainResult(task=task)
            result.final_output = "Error: empty steps list"
            self._history.append(result)
            return result

        if self._generate_fn is None:
            result = ChainResult(task=task)
            result.final_output = "Error: no generate_fn provided"
            self._history.append(result)
            return result

        pipeline = []
        for i, step_def in enumerate(steps):
            pipeline.append({
                "step_number": i + 1,
                "step_name": step_def.get("name", f"step_{i + 1}"),
                "prompt_template": step_def["prompt_template"],
                "task": task,
                "context": context,
            })

        return self._execute_pipeline(task, pipeline)

    def estimate_complexity(self, task: str) -> str:
        """Estimate task complexity from text characteristics.

        Args:
            task: The task text to analyze.

        Returns:
            "simple", "moderate", or "complex".
        """
        words = task.split()
        word_count = len(words)
        task_lower = task.lower()

        # Short, single-question tasks are simple
        if word_count < 50:
            has_complex = any(kw in task_lower for kw in _COMPLEX_KEYWORDS)
            has_code = any(kw in task_lower for kw in _CODE_KEYWORDS)
            if not has_complex and not has_code:
                return "simple"

        # Long tasks or those with complex/code keywords are complex
        if word_count > 200:
            return "complex"

        if any(kw in task_lower for kw in _COMPLEX_KEYWORDS):
            return "complex"

        if any(kw in task_lower for kw in _CODE_KEYWORDS):
            return "complex"

        return "moderate"

    def get_reasoning_stats(self) -> dict:
        """Return statistics from reasoning history.

        Returns:
            Dict with avg_steps_used, avg_duration_per_step,
            shortcut_rate, complexity_distribution.
        """
        if not self._history:
            return {
                "avg_steps_used": 0.0,
                "avg_duration_per_step": 0.0,
                "shortcut_rate": 0.0,
                "complexity_distribution": {"simple": 0, "moderate": 0, "complex": 0},
                "total_reasoning_sessions": 0,
            }

        total_steps = sum(r.total_steps for r in self._history)
        total_duration = sum(r.total_duration for r in self._history)
        shortcuts = sum(1 for r in self._history if r.used_shortcut)

        # Estimate complexity distribution from step counts
        distribution = {"simple": 0, "moderate": 0, "complex": 0}
        for r in self._history:
            if r.total_steps <= 1:
                distribution["simple"] += 1
            elif r.total_steps <= 2:
                distribution["moderate"] += 1
            else:
                distribution["complex"] += 1

        avg_steps = total_steps / len(self._history) if self._history else 0.0
        avg_duration = total_duration / total_steps if total_steps > 0 else 0.0

        return {
            "avg_steps_used": avg_steps,
            "avg_duration_per_step": avg_duration,
            "shortcut_rate": shortcuts / len(self._history) if self._history else 0.0,
            "complexity_distribution": distribution,
            "total_reasoning_sessions": len(self._history),
        }

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _build_simple_steps(self, task: str, context: str) -> list[dict]:
        """Build a 1-step pipeline (direct attempt)."""
        prompt = f"Answer this task directly and completely.\n\nTask: {task}"
        if context:
            prompt += f"\nContext: {context}"

        return [{
            "step_number": 1,
            "step_name": "execute",
            "prompt_template": prompt,
            "task": task,
            "context": context,
        }]

    def _build_moderate_steps(self, task: str, context: str) -> list[dict]:
        """Build a 2-step pipeline (understand + execute)."""
        step1_prompt = (
            "Read this task carefully. State: (1) What is being asked. "
            "(2) What the input/constraints are. (3) What a successful "
            "output looks like. Do NOT solve it yet.\n\n"
            f"Task: {task}"
        )
        if context:
            step1_prompt += f"\nContext: {context}"

        step2_template = (
            "Execute this task based on your understanding:\n\n"
            f"Task: {task}\n"
            "Understanding: {previous_output}\n\n"
            "Provide the complete solution."
        )

        return [
            {
                "step_number": 1,
                "step_name": "understand",
                "prompt_template": step1_prompt,
                "task": task,
                "context": context,
            },
            {
                "step_number": 2,
                "step_name": "execute",
                "prompt_template": step2_template,
                "task": task,
                "context": context,
            },
        ]

    def _build_complex_steps(self, task: str, context: str) -> list[dict]:
        """Build the full 4-step pipeline."""
        step1_prompt = (
            "Read this task carefully. State: (1) What is being asked. "
            "(2) What the input/constraints are. (3) What a successful "
            "output looks like. Do NOT solve it yet.\n\n"
            f"Task: {task}"
        )
        if context:
            step1_prompt += f"\nContext: {context}"

        step2_template = (
            "Given this understanding of the task:\n"
            "{previous_output}\n\n"
            "Propose your approach. List the specific steps you'll take. "
            "Identify potential pitfalls. Choose between available strategies. "
            "Do NOT implement yet."
        )

        step3_template = (
            "Execute this plan to solve the original task:\n\n"
            f"Task: {task}\n"
            "Plan: {previous_output}\n\n"
            "Provide the complete solution."
        )

        step4_template = (
            "Review this solution for correctness:\n\n"
            f"Original task: {task}\n"
            "Solution: {previous_output}\n\n"
            "Check for: logical errors, missing edge cases, incorrect "
            "assumptions. If issues found, provide corrected version. "
            "If correct, confirm and summarize."
        )

        return [
            {
                "step_number": 1,
                "step_name": "understand",
                "prompt_template": step1_prompt,
                "task": task,
                "context": context,
            },
            {
                "step_number": 2,
                "step_name": "plan",
                "prompt_template": step2_template,
                "task": task,
                "context": context,
            },
            {
                "step_number": 3,
                "step_name": "execute",
                "prompt_template": step3_template,
                "task": task,
                "context": context,
            },
            {
                "step_number": 4,
                "step_name": "verify",
                "prompt_template": step4_template,
                "task": task,
                "context": context,
            },
        ]

    def _execute_pipeline(
        self,
        task: str,
        steps: list[dict],
    ) -> ChainResult:
        """Execute a sequence of reasoning steps.

        Each step is a separate model call. Previous step's output is
        injected into the next step's prompt via {previous_output}.
        """
        result = ChainResult(task=task)
        start_time = time.time()
        previous_output = ""

        for step_def in steps:
            step_start = time.time()

            # Build prompt — substitute {previous_output}
            prompt = step_def["prompt_template"]
            if "{previous_output}" in prompt:
                prompt = prompt.replace("{previous_output}", previous_output)
            if "{task}" in prompt:
                prompt = prompt.replace("{task}", task)
            if "{context}" in prompt:
                prompt = prompt.replace("{context}", step_def.get("context", ""))

            # Call the model
            try:
                response = self._generate_fn(prompt)
            except Exception as e:
                logger.error(
                    "Chain step %d (%s) failed: %s",
                    step_def["step_number"],
                    step_def["step_name"],
                    e,
                )
                # Record the failed step and stop
                step_duration = time.time() - step_start
                failed_step = ReasoningStep(
                    step_number=step_def["step_number"],
                    step_name=step_def["step_name"],
                    prompt=prompt,
                    response=f"Error: {e}",
                    confidence=0.0,
                    duration_seconds=step_duration,
                    tokens_estimated=self._estimate_tokens(prompt),
                )
                result.steps.append(failed_step)
                break

            step_duration = time.time() - step_start

            # Score confidence if scorer is available
            confidence = 0.0
            if self._confidence_scorer is not None:
                try:
                    confidence = self._confidence_scorer.score(task, response)
                except Exception as e:
                    logger.warning("Confidence scoring failed: %s", e)

            step = ReasoningStep(
                step_number=step_def["step_number"],
                step_name=step_def["step_name"],
                prompt=prompt,
                response=response,
                confidence=confidence,
                duration_seconds=step_duration,
                tokens_estimated=self._estimate_tokens(prompt + response),
            )
            result.steps.append(step)
            previous_output = response

            # Early exit check — never skip Step 1
            if (
                step_def["step_number"] > 1
                and confidence >= self.EARLY_EXIT_THRESHOLD
                and step_def != steps[-1]
            ):
                logger.info(
                    "Early exit at step %d (%s) — confidence %.2f >= %.2f",
                    step_def["step_number"],
                    step_def["step_name"],
                    confidence,
                    self.EARLY_EXIT_THRESHOLD,
                )
                result.used_shortcut = True
                break

        # Finalize result
        result.total_duration = time.time() - start_time
        result.total_steps = len(result.steps)
        if result.steps:
            result.final_output = result.steps[-1].response

        self._history.append(result)
        return result

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return max(1, len(text) // 4)
