"""
Adversarial Model Sparring — Dual-Instance Debate
====================================================
Run two model instances with opposing directives on hard problems.
Instance A (Solver) generates solutions, Instance B (Critic) tries to
break them. Multiple rounds of debate produce battle-tested solutions.

Same model, different system prompts. The critic must be honest — say
"no issues" when the solution is genuinely good. All model calls are
wrapped in try/except so a failure never crashes the pipeline.

Feeds into: Confidence Scorer (before/after comparison), Grimoire
(critique pattern storage), Growth Engine (sparring stats).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("shadow.adversarial_sparring")

# ── System Prompts ──────────────────────────────────────────────────

SOLVER_SYSTEM_PROMPT = (
    "You are solving a problem. Provide the best, most thorough solution you can. "
    "If a critic has identified issues with your previous attempt, address every issue explicitly."
)

CRITIC_SYSTEM_PROMPT = (
    "You are a rigorous code reviewer and logic checker. Your job is to BREAK the proposed solution. "
    "Find: logical errors, missing edge cases, incorrect assumptions, performance issues, security flaws. "
    "Be specific — cite exact lines or claims that are wrong and explain WHY they're wrong. "
    "If the solution is genuinely good, say \"No issues found\" — don't manufacture fake problems."
)

# Patterns that indicate the critic found no issues
_NO_ISSUES_PATTERNS = re.compile(
    r"(?i)\b(no issues found|no issues|looks good|looks correct|correct|no problems|"
    r"no errors|solution is correct|solution is good|no flaws|well done|"
    r"no bugs|nothing wrong|all good)\b"
)

# Patterns for extracting individual issues from critic response
_NUMBERED_ISSUE = re.compile(r"^\s*\d+[\.\)]\s*(.+)", re.MULTILINE)
_BULLET_ISSUE = re.compile(r"^\s*[-*•]\s*(.+)", re.MULTILINE)
_LABELED_ISSUE = re.compile(
    r"^\s*(?:Issue|Problem|Error|Bug|Flaw|Concern)\s*[:\d]*[:\.\)]\s*(.+)",
    re.MULTILINE | re.IGNORECASE,
)

# Keywords that indicate a task is complex enough to warrant sparring
_CODE_KEYWORDS = re.compile(
    r"\b(function|class|implement|debug|refactor|algorithm|api|code|script|program|"
    r"deploy|migration|database|schema)\b",
    re.IGNORECASE,
)
_SECURITY_KEYWORDS = re.compile(
    r"\b(security|vulnerability|injection|auth|encrypt|decrypt|firewall|exploit|"
    r"permission|access control|xss|csrf|sql injection)\b",
    re.IGNORECASE,
)
_MATH_KEYWORDS = re.compile(
    r"\b(calculate|compute|prove|equation|formula|integral|derivative|optimize|"
    r"statistics|probability|theorem)\b",
    re.IGNORECASE,
)
_SIMPLE_TASK_PATTERNS = re.compile(
    r"(?i)^(hello|hi|hey|greet|what time|what date|who are you|thanks|thank you|"
    r"good morning|good night|remind me|set reminder|weather)\b"
)


# ── Data Schemas ────────────────────────────────────────────────────

@dataclass
class DebateRound:
    """One round of solver-critic exchange."""
    round_number: int
    solver_response: str
    critic_response: str
    issues_found: list[str]
    solver_addressed: bool  # did solver fix the issues in next round?
    timestamp: float


@dataclass
class SparringResult:
    """Full result of a sparring session."""
    task: str
    rounds: list[DebateRound]
    final_solution: str
    total_issues_found: int
    issues_resolved: int
    confidence_before: float  # confidence of direct attempt
    confidence_after: float   # confidence of battle-tested solution
    improved: bool            # did sparring improve the solution?
    duration_seconds: float


# ── Main Class ──────────────────────────────────────────────────────

class AdversarialSparring:
    """Run dual-instance debate to battle-test solutions."""

    def __init__(
        self,
        generate_fn: Optional[Callable] = None,
        grimoire: Any = None,
        max_rounds: int = 3,
    ):
        self.generate_fn = generate_fn
        self.grimoire = grimoire
        self.max_rounds = max(1, max_rounds)
        self._history: list[SparringResult] = []

    # ── Public API ──────────────────────────────────────────────────

    def spar(
        self,
        task: str,
        initial_solution: Optional[str] = None,
        context: str = "",
    ) -> SparringResult:
        """Run a multi-round debate between solver and critic.

        Args:
            task: The problem to solve.
            initial_solution: Optional starting solution. If None, solver generates from scratch.
            context: Additional context for both instances.

        Returns:
            SparringResult with the battle-tested solution and metrics.
        """
        start = time.time()
        rounds: list[DebateRound] = []
        current_solution = initial_solution or ""

        # Score initial confidence (before sparring)
        confidence_before = self._estimate_confidence(current_solution, task)

        for round_num in range(1, self.max_rounds + 1):
            # ── Solver turn ─────────────────────────────────────
            solver_prompt = self._build_solver_prompt(
                task, current_solution, rounds, context,
            )
            solver_response = self._call_model(SOLVER_SYSTEM_PROMPT, solver_prompt)
            if solver_response is None:
                # Model failure — use best available
                logger.warning("Solver failed in round %d, stopping early", round_num)
                break

            current_solution = solver_response

            # ── Critic turn ─────────────────────────────────────
            critic_prompt = self._build_critic_prompt(task, current_solution, context)
            critic_response = self._call_model(CRITIC_SYSTEM_PROMPT, critic_prompt)
            if critic_response is None:
                logger.warning("Critic failed in round %d, stopping early", round_num)
                rounds.append(DebateRound(
                    round_number=round_num,
                    solver_response=solver_response,
                    critic_response="",
                    issues_found=[],
                    solver_addressed=False,
                    timestamp=time.time(),
                ))
                break

            issues = self.parse_critic_issues(critic_response)

            rnd = DebateRound(
                round_number=round_num,
                solver_response=solver_response,
                critic_response=critic_response,
                issues_found=issues,
                solver_addressed=False,  # updated in next round
                timestamp=time.time(),
            )
            rounds.append(rnd)

            # Early exit — critic found no issues
            if not issues:
                logger.info("Critic found no issues in round %d — stopping early", round_num)
                break

            logger.info("Round %d: critic found %d issue(s)", round_num, len(issues))

        # Mark solver_addressed for rounds where the next round exists
        for i in range(len(rounds) - 1):
            if rounds[i].issues_found:
                rounds[i].solver_addressed = True

        # Final metrics
        total_issues = sum(len(r.issues_found) for r in rounds)
        issues_resolved = sum(len(r.issues_found) for r in rounds if r.solver_addressed)
        final_solution = current_solution

        confidence_after = self._estimate_confidence(final_solution, task)
        # Boost confidence if issues were found and resolved
        if total_issues > 0 and issues_resolved > 0:
            resolution_ratio = issues_resolved / total_issues
            confidence_after = min(1.0, confidence_after + resolution_ratio * 0.15)

        improved = confidence_after > confidence_before

        result = SparringResult(
            task=task,
            rounds=rounds,
            final_solution=final_solution,
            total_issues_found=total_issues,
            issues_resolved=issues_resolved,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            improved=improved,
            duration_seconds=time.time() - start,
        )

        self._history.append(result)

        # Store critique patterns if Grimoire available
        if self.grimoire and total_issues > 0:
            try:
                self.store_critique_patterns(result, self.grimoire)
            except Exception as exc:
                logger.warning("Failed to store critique patterns: %s", exc)

        return result

    def parse_critic_issues(self, critic_response: str) -> list[str]:
        """Extract individual issues from the critic's response.

        Looks for numbered lists, bullet points, and labeled issues.
        Returns empty list if the critic indicates no issues.

        Args:
            critic_response: Raw text from the critic instance.

        Returns:
            List of individual issue strings.
        """
        if not critic_response or not critic_response.strip():
            return []

        # Check for "no issues" signals first
        if _NO_ISSUES_PATTERNS.search(critic_response):
            # Make sure it's not a false positive — if there are also numbered
            # issues, the issues win
            has_numbered = _NUMBERED_ISSUE.search(critic_response)
            has_bullets = _BULLET_ISSUE.search(critic_response)
            has_labeled = _LABELED_ISSUE.search(critic_response)
            if not (has_numbered or has_bullets or has_labeled):
                return []

        issues: list[str] = []
        seen: set[str] = set()

        # Try labeled issues first (most specific)
        for match in _LABELED_ISSUE.finditer(critic_response):
            text = match.group(1).strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                issues.append(text)

        # Then numbered lists
        for match in _NUMBERED_ISSUE.finditer(critic_response):
            text = match.group(1).strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                issues.append(text)

        # Then bullet points
        for match in _BULLET_ISSUE.finditer(critic_response):
            text = match.group(1).strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                issues.append(text)

        return issues

    def store_critique_patterns(
        self,
        result: SparringResult,
        grimoire: Any,
    ) -> list[str]:
        """Store effective critique patterns in Grimoire.

        Only stores issues that were actually resolved (solver addressed them),
        as these represent validated critique patterns worth remembering.

        Args:
            result: The completed sparring result.
            grimoire: Grimoire instance for storage.

        Returns:
            List of stored document IDs.
        """
        doc_ids: list[str] = []

        for rnd in result.rounds:
            if not rnd.solver_addressed or not rnd.issues_found:
                continue

            for issue in rnd.issues_found:
                try:
                    doc_id = grimoire.store(
                        content=issue,
                        category="critique_pattern",
                        metadata={
                            "task_type": self._classify_task(result.task),
                            "issue_type": self._classify_issue(issue),
                            "resolution": "resolved",
                            "round_number": rnd.round_number,
                            "source": "adversarial_sparring",
                        },
                    )
                    if doc_id:
                        doc_ids.append(doc_id)
                except Exception as exc:
                    logger.warning("Failed to store critique pattern: %s", exc)

        return doc_ids

    def should_spar(self, task: str, initial_confidence: float) -> bool:
        """Decide whether a task is worth the multi-round sparring cost.

        Args:
            task: The task description.
            initial_confidence: Confidence score from a direct attempt.

        Returns:
            True if sparring is likely to improve the result.
        """
        # High confidence — no need to spar
        if initial_confidence >= 0.7:
            return False

        # Simple tasks — not worth the cost
        if _SIMPLE_TASK_PATTERNS.search(task):
            return False

        # Complex tasks benefit from sparring
        if _CODE_KEYWORDS.search(task):
            return True
        if _SECURITY_KEYWORDS.search(task):
            return True
        if _MATH_KEYWORDS.search(task):
            return True

        # Low confidence on anything moderately complex
        if initial_confidence < 0.5 and len(task.split()) > 10:
            return True

        return False

    def get_sparring_stats(self) -> dict:
        """Return aggregate statistics for the Growth Engine.

        Returns:
            Dict with total_spars, avg_rounds, avg_issues_found,
            avg_improvement, tasks_improved_pct.
        """
        if not self._history:
            return {
                "total_spars": 0,
                "avg_rounds": 0.0,
                "avg_issues_found": 0.0,
                "avg_improvement": 0.0,
                "tasks_improved_pct": 0.0,
            }

        total = len(self._history)
        avg_rounds = sum(len(r.rounds) for r in self._history) / total
        avg_issues = sum(r.total_issues_found for r in self._history) / total
        avg_improvement = sum(
            r.confidence_after - r.confidence_before for r in self._history
        ) / total
        improved_count = sum(1 for r in self._history if r.improved)

        return {
            "total_spars": total,
            "avg_rounds": round(avg_rounds, 2),
            "avg_issues_found": round(avg_issues, 2),
            "avg_improvement": round(avg_improvement, 4),
            "tasks_improved_pct": round(improved_count / total * 100, 1),
        }

    # ── Private Helpers ─────────────────────────────────────────────

    def _call_model(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call the generate function with error handling."""
        if self.generate_fn is None:
            return None
        try:
            result = self.generate_fn(system_prompt=system_prompt, prompt=user_prompt)
            if isinstance(result, str):
                return result
            # Handle dict-style returns
            if isinstance(result, dict):
                return result.get("response") or result.get("text") or str(result)
            return str(result) if result is not None else None
        except Exception as exc:
            logger.error("Model call failed: %s", exc)
            return None

    def _build_solver_prompt(
        self,
        task: str,
        current_solution: str,
        rounds: list[DebateRound],
        context: str,
    ) -> str:
        """Build the prompt for the solver instance."""
        parts = [f"Task: {task}"]
        if context:
            parts.append(f"Context: {context}")

        if rounds and rounds[-1].issues_found:
            parts.append(f"\nYour previous solution:\n{current_solution}")
            parts.append("\nThe critic found these issues:")
            for i, issue in enumerate(rounds[-1].issues_found, 1):
                parts.append(f"  {i}. {issue}")
            parts.append("\nAddress every issue and provide an improved solution.")
        elif current_solution:
            parts.append(f"\nStarting point:\n{current_solution}")
            parts.append("\nImprove this solution or confirm it is correct.")
        else:
            parts.append("\nProvide your best solution.")

        return "\n".join(parts)

    def _build_critic_prompt(self, task: str, solution: str, context: str) -> str:
        """Build the prompt for the critic instance."""
        parts = [
            f"Original task: {task}",
        ]
        if context:
            parts.append(f"Context: {context}")
        parts.append(f"\nProposed solution:\n{solution}")
        parts.append("\nReview this solution rigorously. List every issue you find.")
        return "\n".join(parts)

    def _estimate_confidence(self, solution: str, task: str) -> float:
        """Quick heuristic confidence estimate (no LLM call)."""
        if not solution or not solution.strip():
            return 0.2

        score = 0.5
        # Longer, more detailed solutions get a boost
        word_count = len(solution.split())
        if word_count > 100:
            score += 0.1
        if word_count > 300:
            score += 0.05

        # Check if solution mentions key terms from task
        task_words = set(w.lower() for w in task.split() if len(w) > 3)
        solution_lower = solution.lower()
        overlap = sum(1 for w in task_words if w in solution_lower)
        if task_words:
            relevance = overlap / len(task_words)
            score += relevance * 0.15

        return min(0.95, max(0.1, score))

    def _classify_task(self, task: str) -> str:
        """Classify a task for metadata."""
        if _CODE_KEYWORDS.search(task):
            return "code"
        if _SECURITY_KEYWORDS.search(task):
            return "security"
        if _MATH_KEYWORDS.search(task):
            return "math"
        return "general"

    def _classify_issue(self, issue: str) -> str:
        """Classify an issue type for metadata."""
        issue_lower = issue.lower()
        if any(w in issue_lower for w in ("edge case", "boundary", "corner case")):
            return "edge_case"
        if any(w in issue_lower for w in ("performance", "slow", "O(n", "complexity")):
            return "performance"
        if any(w in issue_lower for w in ("security", "injection", "vulnerability", "xss")):
            return "security"
        if any(w in issue_lower for w in ("logic", "incorrect", "wrong", "error", "bug")):
            return "logic_error"
        if any(w in issue_lower for w in ("missing", "forgot", "omit", "lack")):
            return "missing_feature"
        return "other"
