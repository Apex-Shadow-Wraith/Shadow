"""Adversarial Self-Review Pass — second evaluation pass tries to break responses."""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Result of an adversarial self-review pass."""

    original_response: str
    reviewed_response: str
    review_cycles: int
    issues_found: list[str]
    issues_fixed: list[str]
    confidence_before: float
    confidence_after: float
    improved: bool
    duration_seconds: float


# Task types that warrant adversarial review
_REVIEWABLE_TYPES = {"code", "math", "security", "analysis", "research", "creation"}


class SelfReviewer:
    """Adversarial self-review: before serving a response, a second pass tries to break it."""

    def __init__(
        self,
        generate_fn: Optional[Callable] = None,
        confidence_scorer=None,
        config: Optional[dict] = None,
    ):
        config = config or {}
        self._generate_fn = generate_fn
        self._confidence_scorer = confidence_scorer
        self._max_cycles: int = config.get("max_cycles", 2)
        self._confidence_threshold: float = config.get("confidence_threshold", 0.7)
        self._review_task_types: set[str] = set(
            config.get("review_task_types", _REVIEWABLE_TYPES)
        )

        # Stats
        self._total_reviewed: int = 0
        self._issues_found_count: int = 0
        self._improvement_count: int = 0
        self._revert_count: int = 0
        self._total_cycles: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review(
        self, task: str, response: str, task_type: str = ""
    ) -> ReviewResult:
        """Run adversarial review on *response* for *task*.

        Returns a ReviewResult — caller decides whether to use the
        reviewed_response or the original.
        """
        start = time.time()

        # Score original
        confidence_before = self._score(task, response, task_type)

        # Fast path: high confidence → no review needed
        if confidence_before >= self._confidence_threshold:
            return ReviewResult(
                original_response=response,
                reviewed_response=response,
                review_cycles=0,
                issues_found=[],
                issues_fixed=[],
                confidence_before=confidence_before,
                confidence_after=confidence_before,
                improved=False,
                duration_seconds=time.time() - start,
            )

        best_response = response
        best_score = confidence_before
        all_issues_found: list[str] = []
        all_issues_fixed: list[str] = []
        cycles = 0

        for cycle in range(self._max_cycles):
            cycles += 1

            # --- Adversarial review ---
            review_text = self._run_review(task, best_response)
            if review_text is None:
                # generate_fn failure — stop reviewing
                break

            issues = self.parse_review_issues(review_text)
            all_issues_found.extend(issues)

            if not issues:
                # Reviewer found nothing wrong
                break

            # --- Regenerate with critique ---
            corrected = self._regenerate_with_critique(
                task, best_response, issues
            )
            if corrected is None:
                # generate_fn failure — keep what we have
                break

            corrected_score = self._score(task, corrected, task_type)

            if corrected_score > best_score:
                all_issues_fixed.extend(issues)
                best_response = corrected
                best_score = corrected_score
            else:
                # Correction didn't help — revert and stop
                self._revert_count += 1
                break

        improved = best_response != response
        duration = time.time() - start

        # Update stats
        self._total_reviewed += 1
        self._total_cycles += cycles
        if all_issues_found:
            self._issues_found_count += 1
        if improved:
            self._improvement_count += 1

        return ReviewResult(
            original_response=response,
            reviewed_response=best_response,
            review_cycles=cycles,
            issues_found=all_issues_found,
            issues_fixed=all_issues_fixed,
            confidence_before=confidence_before,
            confidence_after=best_score,
            improved=improved,
            duration_seconds=duration,
        )

    def should_review(self, task_type: str, initial_confidence: float) -> bool:
        """Decide whether a task warrants adversarial review.

        Review if: task involves code, math, security, or analysis
        AND confidence < threshold.
        Skip if: simple greetings, routing, high confidence responses.
        """
        if initial_confidence >= self._confidence_threshold:
            return False

        task_lower = task_type.lower().strip()

        # Skip trivial task types
        if task_lower in {"conversation", "greeting", "system", "routing", ""}:
            return False

        # Review if task type matches reviewable set
        return task_lower in self._review_task_types

    def parse_review_issues(self, review_response: str) -> list[str]:
        """Extract individual issues from a review response.

        Handles numbered lists, bullets, 'Issue:' prefixes.
        Returns empty list for 'No issues found'.
        """
        if not review_response or not review_response.strip():
            return []

        text = review_response.strip()

        # Check for "no issues" variants
        no_issue_patterns = [
            r"no\s+issues?\s+found",
            r"no\s+problems?\s+found",
            r"no\s+flaws?\s+found",
            r"response\s+is\s+correct",
            r"looks?\s+good",
            r"no\s+issues?\s+detected",
        ]
        for pattern in no_issue_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return []

        issues: list[str] = []

        # Match numbered items: "1. ...", "1) ..."
        numbered = re.findall(r"^\s*\d+[\.\)]\s*(.+)$", text, re.MULTILINE)
        if numbered:
            issues.extend(item.strip() for item in numbered if item.strip())

        # Match bullet items: "- ...", "* ..."
        if not issues:
            bullets = re.findall(r"^\s*[\-\*\u2022]\s*(.+)$", text, re.MULTILINE)
            if bullets:
                issues.extend(item.strip() for item in bullets if item.strip())

        # Match "Issue:" prefixed lines
        if not issues:
            issue_lines = re.findall(
                r"(?:^|\n)\s*[Ii]ssue\s*(?:\d+)?\s*:\s*(.+)", text
            )
            if issue_lines:
                issues.extend(item.strip() for item in issue_lines if item.strip())

        # Fallback: if no structured format, treat non-empty lines as issues
        if not issues:
            for line in text.split("\n"):
                line = line.strip()
                if line and len(line) > 10:
                    issues.append(line)

        return issues

    def get_review_stats(self) -> dict:
        """Return review statistics for Growth Engine."""
        total = self._total_reviewed or 1  # avoid div-by-zero
        return {
            "total_reviewed": self._total_reviewed,
            "issues_found_rate": self._issues_found_count / total,
            "improvement_rate": self._improvement_count / total,
            "avg_cycles": self._total_cycles / total,
            "revert_rate": self._revert_count / total,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _score(self, task: str, response: str, task_type: str) -> float:
        """Score a response using the confidence scorer. Returns 0.5 if unavailable."""
        if self._confidence_scorer is None:
            return 0.5
        try:
            result = self._confidence_scorer.score_response(
                task=task,
                response=response,
                task_type=task_type,
                context={},
            )
            return result.get("confidence", 0.5)
        except Exception as e:
            logger.debug("Confidence scoring failed during review: %s", e)
            return 0.5

    def _run_review(self, task: str, response: str) -> Optional[str]:
        """Ask the LLM to adversarially critique the response."""
        if self._generate_fn is None:
            return None

        prompt = (
            "You are a critical reviewer. Find flaws in this response:\n\n"
            f"Task: {task}\n"
            f"Response: {response}\n\n"
            "Look for: logical errors, missing edge cases, incorrect facts, "
            "incomplete answers, security issues, code bugs. "
            "List specific issues found.\n"
            'If the response is correct, say "No issues found."'
        )
        try:
            return self._generate_fn(prompt)
        except Exception as e:
            logger.debug("Review generation failed: %s", e)
            return None

    def _regenerate_with_critique(
        self, task: str, response: str, issues: list[str]
    ) -> Optional[str]:
        """Regenerate the response incorporating reviewer critique."""
        if self._generate_fn is None:
            return None

        issues_text = "\n".join(f"- {issue}" for issue in issues)
        prompt = (
            f"Original task: {task}\n"
            f"Your previous response: {response}\n"
            f"Issues found by reviewer:\n{issues_text}\n\n"
            "Provide a corrected response that addresses all issues."
        )
        try:
            return self._generate_fn(prompt)
        except Exception as e:
            logger.debug("Regeneration with critique failed: %s", e)
            return None
