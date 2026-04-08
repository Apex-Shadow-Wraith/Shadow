"""
Recursive Decomposition Before Escalation
============================================
When confidence is low, break the problem into sub-problems before
escalating to Apex. Handles problems too complex for one pass but that
don't actually need a frontier model.

Algorithm:
  1. Try solving directly → score confidence
  2. If confidence >= 0.7 → done
  3. If confidence < 0.7 AND depth < max_depth:
     a. Decompose into 2-5 independent sub-problems
     b. Recursively solve each sub-problem
     c. Merge sub-problem solutions
     d. If merged score > direct score → use merged
     e. Otherwise → use direct (decomposition didn't help)
  4. If depth >= max_depth → return best available

Feeds into: RetryEngine (strategy #2), Orchestrator (pre-Apex gate).
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("shadow.recursive_decomposer")


# ── Data Classes ────────────────────────────────────────────────────

@dataclass
class SubProblem:
    """A single node in the decomposition tree."""

    id: str
    parent_id: Optional[str]       # None for root
    depth: int
    description: str
    solution: str = ""
    confidence: float = 0.0
    status: str = "pending"        # "pending", "solved", "decomposed", "failed"
    children: list[str] = field(default_factory=list)


@dataclass
class DecompositionResult:
    """Complete result of a recursive decomposition pass."""

    original_task: str
    sub_problems: list[SubProblem] = field(default_factory=list)
    merged_solution: str = ""
    overall_confidence: float = 0.0
    total_model_calls: int = 0
    max_depth_reached: int = 0
    decomposition_helped: bool = False


# ── Multi-step indicators for should_decompose heuristic ────────────

_MULTI_STEP_INDICATORS = frozenset({
    " and ", " then ", " also ", " additionally ", " furthermore ",
    " next ", " finally ", " first ", " second ", " third ",
    " step ", " steps ",
})

_SIMPLE_QUESTION_PATTERNS = [
    r"^what is\b",
    r"^what's\b",
    r"^who is\b",
    r"^who's\b",
    r"^when did\b",
    r"^when was\b",
    r"^where is\b",
    r"^where's\b",
    r"^how many\b",
    r"^how much\b",
    r"^define\b",
    r"^what does .+ mean",
]


# ── Recursive Decomposer ───────────────────────────────────────────

class RecursiveDecomposer:
    """Break complex problems into sub-problems before escalating to Apex.

    Uses recursive decomposition with confidence-gated depth control.
    Only decomposes when it actually improves the answer — never for
    its own sake.
    """

    # Confidence threshold: above this, no decomposition needed
    CONFIDENCE_THRESHOLD = 0.7

    def __init__(
        self,
        generate_fn: Callable | None = None,
        confidence_scorer: Any = None,
        max_depth: int = 3,
    ) -> None:
        """Initialize the recursive decomposer.

        Args:
            generate_fn: Callable(prompt) -> str. Calls the model.
            confidence_scorer: Object with a score_response() method,
                or None (falls back to simple length heuristic).
            max_depth: Maximum recursion depth (prevent infinite decomposition).
        """
        self._generate_fn = generate_fn
        self._confidence_scorer = confidence_scorer
        self._max_depth = max_depth

    def decompose(self, task: str, context: str = "") -> list[str]:
        """Ask the model to break a task into 2-5 independent sub-problems.

        Args:
            task: The task to decompose.
            context: Additional context for the model.

        Returns:
            List of sub-problem descriptions. Returns [task] if
            decomposition fails or produces fewer than 2 sub-problems.
        """
        if self._generate_fn is None:
            return [task]

        prompt = (
            "This task is too complex to solve in one step. Break it into "
            "2-5 smaller, independent sub-problems that can be solved "
            "separately and combined:\n\n"
            f"Task: {task}"
        )
        if context:
            prompt += f"\nContext: {context}"
        prompt += "\n\nList each sub-problem on its own line, prefixed with a number."

        try:
            response = self._generate_fn(prompt)
        except Exception as e:
            logger.warning("Decomposition model call failed: %s", e)
            return [task]

        # Parse numbered lines
        sub_problems = self._parse_numbered_list(response)

        if len(sub_problems) < 2:
            logger.info("Decomposition produced %d sub-problems — returning original task",
                        len(sub_problems))
            return [task]

        # Cap at 5
        return sub_problems[:5]

    def solve_with_decomposition(
        self,
        task: str,
        context: str = "",
        depth: int = 0,
    ) -> DecompositionResult:
        """Main entry point. Recursively decompose and solve.

        Args:
            task: The task to solve.
            context: Additional context.
            depth: Current recursion depth (internal use).

        Returns:
            DecompositionResult with the best solution found.
        """
        result = DecompositionResult(original_task=task)

        # Step 1: Try solving directly
        direct_solution, direct_confidence, direct_calls = self._solve_direct(task, context)
        result.total_model_calls += direct_calls
        result.max_depth_reached = depth

        # Create root sub-problem
        root = SubProblem(
            id=str(uuid.uuid4()),
            parent_id=None,
            depth=depth,
            description=task,
            solution=direct_solution,
            confidence=direct_confidence,
            status="solved",
        )
        result.sub_problems.append(root)

        # Step 2: If confidence is good enough, return direct solution
        if direct_confidence >= self.CONFIDENCE_THRESHOLD:
            result.merged_solution = direct_solution
            result.overall_confidence = direct_confidence
            result.decomposition_helped = False
            return result

        # Step 3: If we've hit max depth, return what we have
        if depth >= self._max_depth:
            result.merged_solution = direct_solution
            result.overall_confidence = direct_confidence
            result.decomposition_helped = False
            return result

        # Step 4: Decompose and solve sub-problems
        sub_descriptions = self.decompose(task, context)

        # If decompose returned [task], can't break it down further
        if len(sub_descriptions) == 1 and sub_descriptions[0] == task:
            result.merged_solution = direct_solution
            result.overall_confidence = direct_confidence
            result.decomposition_helped = False
            return result

        root.status = "decomposed"
        child_sub_problems: list[SubProblem] = []

        for desc in sub_descriptions:
            # Recursively solve each sub-problem
            try:
                child_result = self.solve_with_decomposition(
                    task=desc,
                    context=context,
                    depth=depth + 1,
                )
                result.total_model_calls += child_result.total_model_calls
                result.max_depth_reached = max(
                    result.max_depth_reached,
                    child_result.max_depth_reached,
                )

                # Get the best sub-problem from the child result
                child_sp = SubProblem(
                    id=str(uuid.uuid4()),
                    parent_id=root.id,
                    depth=depth + 1,
                    description=desc,
                    solution=child_result.merged_solution,
                    confidence=child_result.overall_confidence,
                    status="solved" if child_result.merged_solution else "failed",
                )
                root.children.append(child_sp.id)
                child_sub_problems.append(child_sp)
                result.sub_problems.append(child_sp)

            except Exception as e:
                logger.warning("Sub-problem solve failed at depth %d: %s", depth + 1, e)
                failed_sp = SubProblem(
                    id=str(uuid.uuid4()),
                    parent_id=root.id,
                    depth=depth + 1,
                    description=desc,
                    solution="",
                    confidence=0.0,
                    status="failed",
                )
                root.children.append(failed_sp.id)
                child_sub_problems.append(failed_sp)
                result.sub_problems.append(failed_sp)

        # Step 5: Merge sub-problem solutions
        solved_children = [sp for sp in child_sub_problems if sp.status == "solved" and sp.solution]
        if not solved_children:
            # All children failed — return direct solution
            result.merged_solution = direct_solution
            result.overall_confidence = direct_confidence
            result.decomposition_helped = False
            return result

        merged_solution = self.merge_solutions(task, solved_children)
        result.total_model_calls += 1  # merge call

        # Step 6: Score merged solution
        merged_confidence = self._score_solution(task, merged_solution)

        # Step 7: Pick the better solution
        if merged_confidence > direct_confidence:
            result.merged_solution = merged_solution
            result.overall_confidence = merged_confidence
            result.decomposition_helped = True
        else:
            result.merged_solution = direct_solution
            result.overall_confidence = direct_confidence
            result.decomposition_helped = False

        return result

    def merge_solutions(self, task: str, sub_problems: list[SubProblem]) -> str:
        """Combine sub-problem solutions into a coherent answer.

        Args:
            task: The original task.
            sub_problems: Solved sub-problems with their solutions.

        Returns:
            Merged solution string.
        """
        if not sub_problems:
            return ""

        if len(sub_problems) == 1:
            return sub_problems[0].solution

        if self._generate_fn is None:
            # Fallback: concatenate
            return "\n\n".join(sp.solution for sp in sub_problems if sp.solution)

        formatted = "\n\n".join(
            f"Sub-problem: {sp.description}\nSolution: {sp.solution}"
            for sp in sub_problems
            if sp.solution
        )

        prompt = (
            "These sub-problems were solved independently. Combine them "
            "into a single coherent solution for the original task:\n\n"
            f"Original task: {task}\n\n"
            f"Sub-problem solutions:\n{formatted}\n\n"
            "Provide the merged solution."
        )

        try:
            return self._generate_fn(prompt)
        except Exception as e:
            logger.warning("Merge model call failed: %s", e)
            # Fallback: concatenate
            return "\n\n".join(sp.solution for sp in sub_problems if sp.solution)

    def should_decompose(self, task: str, confidence: float) -> bool:
        """Quick heuristic: is this task worth decomposing?

        Args:
            task: The task text.
            confidence: Current confidence score for the task.

        Returns:
            True if decomposition is likely to help.
        """
        # High confidence — no need
        if confidence >= self.CONFIDENCE_THRESHOLD:
            return False

        task_lower = task.lower().strip()

        # Simple factual questions — decomposition won't help
        for pattern in _SIMPLE_QUESTION_PATTERNS:
            if re.match(pattern, task_lower):
                return False

        # Check for multi-part indicators
        has_multi_part = any(ind in task_lower for ind in _MULTI_STEP_INDICATORS)
        if has_multi_part:
            return True

        # Multiple sentences suggest complexity
        sentences = [s.strip() for s in re.split(r"[.!?]+", task) if s.strip()]
        if len(sentences) >= 3:
            return True

        # Multiple question marks
        if task.count("?") >= 2:
            return True

        return False

    # ── Private Helpers ─────────────────────────────────────────────

    def _solve_direct(
        self, task: str, context: str,
    ) -> tuple[str, float, int]:
        """Solve a task directly (single model call).

        Returns:
            Tuple of (solution, confidence, model_calls).
        """
        if self._generate_fn is None:
            return ("", 0.0, 0)

        prompt = f"Solve this task:\n\n{task}"
        if context:
            prompt += f"\n\nContext: {context}"

        try:
            solution = self._generate_fn(prompt)
        except Exception as e:
            logger.warning("Direct solve failed: %s", e)
            return ("", 0.0, 1)

        confidence = self._score_solution(task, solution)
        return (solution, confidence, 1)

    def _score_solution(self, task: str, solution: str) -> float:
        """Score a solution's confidence.

        Uses confidence_scorer if available, otherwise falls back
        to a simple length-based heuristic.

        Args:
            task: The original task.
            solution: The generated solution.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not solution:
            return 0.0

        if self._confidence_scorer is not None:
            try:
                result = self._confidence_scorer.score_response(
                    task=task,
                    response=solution,
                    task_type="general",
                )
                return result.get("confidence", 0.0)
            except Exception as e:
                logger.warning("Confidence scorer failed, using length heuristic: %s", e)

        # Simple length-based fallback
        word_count = len(solution.split())
        if word_count >= 50:
            return 0.8
        if word_count >= 20:
            return 0.6
        if word_count >= 5:
            return 0.4
        return 0.2

    @staticmethod
    def _parse_numbered_list(text: str) -> list[str]:
        """Parse a numbered list from model output.

        Handles formats like:
          1. First sub-problem
          2) Second sub-problem
          1: First sub-problem

        Args:
            text: Raw model output.

        Returns:
            List of parsed items (stripped of numbering).
        """
        if not text:
            return []

        lines = text.strip().split("\n")
        items: list[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Match numbered prefixes: "1.", "1)", "1:", "1 -"
            match = re.match(r"^\d+[\.\)\:\-]\s*(.+)", line)
            if match:
                item = match.group(1).strip()
                if item:
                    items.append(item)

        return items
