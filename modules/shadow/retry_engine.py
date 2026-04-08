"""
Retry Engine — 12-Attempt Strategy Rotation with Apex Escalation-Learning
===========================================================================
When Shadow fails a task, it doesn't just retry the same thing. It cycles
through 12 genuinely different strategies. If all fail, it escalates to
Apex, gets the answer AND a teaching explanation, re-attempts locally to
verify understanding, then stores the lesson permanently in Grimoire.

Architecture principle: 'Shadow should exhaust every local option before
spending API dollars. And when it DOES escalate, it must learn, not just
copy the answer.'
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from modules.base import ToolResult

logger = logging.getLogger("shadow.retry_engine")

# Graceful import — RetryEngine works without RecursiveDecomposer
try:
    from modules.shadow.recursive_decomposer import RecursiveDecomposer
    _DECOMPOSER_AVAILABLE = True
except ImportError:
    _DECOMPOSER_AVAILABLE = False


# ── Strategy Definitions ─────────────────────────────────────────────

STRATEGY_CATEGORIES: list[tuple[str, str]] = [
    (
        "direct",
        "Attempt the task straightforwardly with the default approach. "
        "No tricks, no workarounds — just execute directly.",
    ),
    (
        "decomposition",
        "Break this task into 3-5 smaller sub-tasks. Solve each independently. "
        "Combine the results into a final answer.",
    ),
    (
        "alternative_tools",
        "Use a completely different tool or module to achieve the same goal. "
        "If the previous approach used search, try memory. If it used code, try reasoning.",
    ),
    (
        "reformulation",
        "Restate the problem in completely different terms. Rephrase the question, "
        "reframe the goal. Approach it as if hearing it for the first time.",
    ),
    (
        "simplification",
        "Solve an easier version of this problem first. Strip away complexity, "
        "get a basic answer, then build up to the full solution.",
    ),
    (
        "analogy",
        "Search for similar solved problems in Grimoire. Adapt a known solution "
        "to fit this new task. Pattern-match against past successes.",
    ),
    (
        "inversion",
        "Work backward from the desired output. Define what success looks like, "
        "then trace the steps in reverse to find the path.",
    ),
    (
        "model_switch",
        "Switch to a different brain. If fast_brain failed, use smart_brain. "
        "If smart_brain failed, try fast_brain with a radically different prompt.",
    ),
    (
        "partial_solution",
        "Solve what you can and explicitly flag what you cannot. Provide partial "
        "results with clear markers for the unsolved portions.",
    ),
    (
        "research_first",
        "Before attempting the task, search Grimoire and the web for relevant "
        "approaches, methods, or prior art. Use findings to inform the attempt.",
    ),
    (
        "constraint_relaxation",
        "Identify which requirements are flexible. Relax non-critical constraints "
        "and explore alternative solutions that meet the core goal.",
    ),
    (
        "human_collaboration",
        "Ask the user for clarification, hints, or additional context. Frame "
        "specific questions about what has been tried and what might work.",
    ),
]

# Hardware/software impossibility indicators
_IMPOSSIBILITY_MARKERS = [
    "out of memory",
    "oom",
    "vram",
    "cuda out of memory",
    "not installed",
    "command not found",
    "network unreachable",
    "connection refused",
    "dns resolution failed",
    "no such file or directory",
    "permission denied",
]


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class Attempt:
    """Record of a single retry attempt."""

    attempt_number: int
    strategy: str
    approach_description: str
    tools_used: list[str]
    result: Optional[dict] = None
    error: Optional[str] = None
    success: bool = False
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RetrySession:
    """Full session tracking all retry attempts for a task."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_task: str = ""
    task_type: str = ""
    module: str = ""
    attempts: list[Attempt] = field(default_factory=list)
    max_attempts: int = 12
    current_attempt: int = 0
    status: str = "attempting"  # attempting, succeeded, exhausted, escalated, learned
    final_result: Optional[dict] = None
    escalation_data: Optional[dict] = None


# ── Retry Engine ─────────────────────────────────────────────────────

class RetryEngine:
    """12-attempt retry cycle with strategy rotation and Apex escalation-learning.

    Each attempt uses a genuinely different strategy, not just parameter tweaks.
    If all 12 fail, escalates to Apex for the answer + teaching explanation,
    then verifies understanding locally and stores lessons in Grimoire.
    """

    def __init__(self, registry: Any = None, config: dict[str, Any] | None = None) -> None:
        """Initialize the retry engine.

        Args:
            registry: ModuleRegistry for accessing modules.
            config: Shadow configuration dict.
        """
        self._registry = registry
        self._config = config or {}
        self._session_history: list[dict[str, Any]] = []
        self._max_history = 100

        # Recursive decomposer for strategy #2 (decomposition)
        self._decomposer = None
        if _DECOMPOSER_AVAILABLE:
            try:
                self._decomposer = RecursiveDecomposer()
            except Exception as e:
                logger.warning("RecursiveDecomposer init in RetryEngine failed: %s", e)

    async def attempt_task(
        self,
        task: str,
        module: str,
        context: dict[str, Any],
        evaluate_fn: Callable,
        execute_fn: Callable | None = None,
        grimoire_search_fn: Callable | None = None,
        notify_fn: Callable | None = None,
    ) -> dict[str, Any]:
        """Main entry point. Tries up to 12 strategies before giving up.

        Args:
            task: The task to accomplish.
            module: Which module should handle this task.
            context: Additional context (task_type, tools, etc).
            evaluate_fn: Function that takes a result dict and returns
                {success: bool, confidence: float, reason: str}.
            execute_fn: Async function that takes (task, strategy_context) and
                returns a result dict. If None, returns placeholder.
            grimoire_search_fn: Function to search Grimoire for failure patterns.
                Takes a query string, returns list of dicts.
            notify_fn: Async function to send progress notifications to the user.
                Takes a message string.

        Returns:
            Dict with session data, success status, and result or exhaustion info.
        """
        session = RetrySession(
            original_task=task,
            task_type=context.get("task_type", "general"),
            module=module,
        )

        # Pre-flight: search Grimoire for relevant failure patterns
        failure_context = ""
        if grimoire_search_fn is not None:
            try:
                patterns = grimoire_search_fn(f"failure_pattern {session.task_type}")
                if patterns:
                    lessons = []
                    for p in patterns[:3]:
                        content = p.get("content", "") if isinstance(p, dict) else str(p)
                        if content:
                            lessons.append(content)
                    if lessons:
                        failure_context = (
                            "PREVIOUS LESSONS LEARNED:\n"
                            + "\n".join(f"- {l}" for l in lessons)
                        )
                        logger.info(
                            "Loaded %d failure patterns for task type '%s'",
                            len(lessons), session.task_type,
                        )
            except Exception as e:
                logger.warning("Failed to load failure patterns: %s", e)

        for attempt_num in range(1, session.max_attempts + 1):
            session.current_attempt = attempt_num
            strategy_name, strategy_desc = self.get_strategy_for_attempt(
                attempt_num, session.attempts
            )

            # Build strategy context with history of all prior failures
            strategy_context = self._build_strategy_context(
                task=task,
                attempt_num=attempt_num,
                strategy_name=strategy_name,
                strategy_desc=strategy_desc,
                previous_attempts=session.attempts,
                failure_context=failure_context,
                extra_context=context,
            )

            # Execute the attempt
            start_time = time.time()
            attempt = Attempt(
                attempt_number=attempt_num,
                strategy=strategy_name,
                approach_description=strategy_desc,
                tools_used=context.get("tools", []),
            )

            try:
                if execute_fn is not None:
                    result = await execute_fn(task, strategy_context)
                else:
                    result = {"response": "", "error": "No execute function provided"}
                attempt.duration_seconds = time.time() - start_time
                attempt.result = result

                # Evaluate the result
                evaluation = evaluate_fn(result)
                attempt.success = evaluation.get("success", False)

                if not attempt.success:
                    attempt.error = evaluation.get("reason", "Evaluation failed")

            except Exception as e:
                attempt.duration_seconds = time.time() - start_time
                attempt.error = str(e)
                attempt.success = False
                logger.warning(
                    "Attempt %d (%s) raised exception: %s",
                    attempt_num, strategy_name, e,
                )

            session.attempts.append(attempt)

            # Success — done
            if attempt.success:
                session.status = "succeeded"
                session.final_result = attempt.result
                logger.info(
                    "Task succeeded on attempt %d (%s)",
                    attempt_num, strategy_name,
                )
                self._record_session(session)
                return self._session_to_dict(session)

            # Progress notifications
            if notify_fn is not None:
                await self._send_progress(notify_fn, attempt_num, session)

            # Check for hardware impossibility — early exit
            if attempt.error and self._is_impossibility(attempt.error):
                logger.warning(
                    "Hardware/software impossibility detected at attempt %d: %s",
                    attempt_num, attempt.error,
                )
                session.status = "exhausted"
                self._record_session(session)
                result_dict = self._session_to_dict(session)
                result_dict["exhausted"] = True
                result_dict["ready_to_escalate"] = True
                result_dict["impossibility_detected"] = True
                return result_dict

        # All 12 attempts exhausted
        session.status = "exhausted"
        self._record_session(session)
        result_dict = self._session_to_dict(session)
        result_dict["exhausted"] = True
        result_dict["ready_to_escalate"] = True
        logger.info("All %d attempts exhausted for task: %s", session.max_attempts, task[:100])
        return result_dict

    async def escalate_to_apex(
        self,
        session: RetrySession | dict[str, Any],
        apex_query_fn: Callable | None = None,
        apex_teach_fn: Callable | None = None,
        grimoire_store_fn: Callable | None = None,
        execute_fn: Callable | None = None,
    ) -> dict[str, Any]:
        """Escalate to Apex after exhausting local strategies.

        Steps:
        1. Send original task to Apex, get the answer.
        2. Send follow-up asking Apex to explain its approach vs our failures.
        3. Re-attempt locally using Apex's described approach.
        4. Store three entries in Grimoire: answer, teaching, failure_pattern.

        Args:
            session: RetrySession or dict from attempt_task.
            apex_query_fn: Async fn that sends task to Apex, returns answer str.
            apex_teach_fn: Async fn that sends teaching request, returns explanation str.
            grimoire_store_fn: Fn to store entries in Grimoire.
                Takes (content, tags, trust_level) and returns entry_id str.
            execute_fn: Async fn for local re-verification attempt.

        Returns:
            Dict with answer, teaching, failure_pattern, and verification result.
        """
        # Convert dict to RetrySession if needed
        if isinstance(session, dict):
            rs = RetrySession(
                session_id=session.get("session_id", str(uuid.uuid4())),
                original_task=session.get("original_task", ""),
                task_type=session.get("task_type", "general"),
                module=session.get("module", ""),
                status="escalated",
            )
            # Reconstruct attempts from dict
            for a in session.get("attempts", []):
                rs.attempts.append(Attempt(
                    attempt_number=a.get("attempt_number", 0),
                    strategy=a.get("strategy", ""),
                    approach_description=a.get("approach_description", ""),
                    tools_used=a.get("tools_used", []),
                    result=a.get("result"),
                    error=a.get("error"),
                    success=a.get("success", False),
                    duration_seconds=a.get("duration_seconds", 0.0),
                ))
        else:
            rs = session

        rs.status = "escalated"
        task = rs.original_task

        # Build attempts summary for Apex
        attempts_summary = self._build_attempts_summary(rs.attempts)

        # Step 1: Get the answer from Apex
        answer = ""
        if apex_query_fn is not None:
            try:
                answer = await apex_query_fn(task)
            except Exception as e:
                logger.error("Apex query failed: %s", e)
                return {
                    "success": False,
                    "error": f"Apex query failed: {e}",
                    "session_id": rs.session_id,
                }

        # Step 2: Get teaching explanation from Apex
        teaching = ""
        if apex_teach_fn is not None:
            try:
                teaching_prompt = (
                    f"Here's the task: {task}\n\n"
                    f"Here are my 12 failed approaches:\n{attempts_summary}\n\n"
                    f"Here's your successful answer: {answer}\n\n"
                    f"Explain step by step how you arrived at your solution, "
                    f"what I was doing wrong, and what principle I should learn from this."
                )
                teaching = await apex_teach_fn(teaching_prompt)
            except Exception as e:
                logger.warning("Apex teaching request failed: %s", e)
                teaching = f"Teaching request failed: {e}"

        # Step 3: Build failure pattern
        mistake_summary = self._extract_common_failures(rs.attempts)
        failure_pattern = (
            f"When encountering {rs.task_type} tasks like '{task[:100]}', "
            f"the mistake was: {mistake_summary}. "
            f"The correct approach is: {teaching[:200] if teaching else answer[:200]}"
        )

        # Step 4: Re-attempt locally using Apex's approach
        local_verification_passed = False
        if execute_fn is not None:
            try:
                verification_context = {
                    "strategy": "apex_guided",
                    "instruction": (
                        f"Use this approach from Apex: {teaching[:500] if teaching else answer[:500]}. "
                        f"Apply it to solve: {task}"
                    ),
                }
                verification_result = await execute_fn(task, verification_context)
                # Simple check — did it produce a non-error result?
                if verification_result and not verification_result.get("error"):
                    local_verification_passed = True
            except Exception as e:
                logger.warning("Local re-verification failed: %s", e)

        # Step 5: Store three entries in Grimoire
        stored_ids: list[str] = []
        if grimoire_store_fn is not None:
            try:
                # 1. The successful answer
                answer_id = grimoire_store_fn(
                    content=f"Apex answer for '{task[:100]}': {answer}",
                    tags=["apex_sourced", rs.task_type],
                    trust_level=0.7,
                )
                stored_ids.append(str(answer_id))
            except Exception as e:
                logger.warning("Failed to store Apex answer in Grimoire: %s", e)

            try:
                # 2. The teaching explanation
                teach_id = grimoire_store_fn(
                    content=f"Apex teaching for '{task[:100]}': {teaching}",
                    tags=["apex_learning", rs.task_type],
                    trust_level=0.7,
                )
                stored_ids.append(str(teach_id))
            except Exception as e:
                logger.warning("Failed to store teaching in Grimoire: %s", e)

            try:
                # 3. Failure pattern
                pattern_id = grimoire_store_fn(
                    content=failure_pattern,
                    tags=["failure_pattern", rs.task_type],
                    trust_level=0.7,
                )
                stored_ids.append(str(pattern_id))
            except Exception as e:
                logger.warning("Failed to store failure pattern in Grimoire: %s", e)

        rs.status = "learned"
        rs.escalation_data = {
            "answer": answer,
            "teaching": teaching,
            "failure_pattern": failure_pattern,
            "local_verification_passed": local_verification_passed,
            "grimoire_ids": stored_ids,
        }
        self._record_session(rs)

        logger.info(
            "Escalation complete. Verification=%s, Grimoire entries=%d",
            local_verification_passed, len(stored_ids),
        )

        return {
            "success": True,
            "answer": answer,
            "teaching": teaching,
            "failure_pattern": failure_pattern,
            "local_verification_passed": local_verification_passed,
            "grimoire_ids": stored_ids,
            "session_id": rs.session_id,
        }

    def get_strategy_for_attempt(
        self, attempt_number: int, previous_attempts: list[Attempt]
    ) -> tuple[str, str]:
        """Return (strategy_name, description) for the given attempt number.

        Ensures no strategy is repeated within a session.

        Args:
            attempt_number: 1-based attempt number.
            previous_attempts: All prior attempts in this session.

        Returns:
            Tuple of (strategy_name, strategy_description).
        """
        used_strategies = {a.strategy for a in previous_attempts}

        # Try the default order first
        for name, desc in STRATEGY_CATEGORIES:
            if name not in used_strategies:
                return (name, desc)

        # Fallback — should not happen with 12 strategies and 12 max attempts
        idx = (attempt_number - 1) % len(STRATEGY_CATEGORIES)
        name, desc = STRATEGY_CATEGORIES[idx]
        return (name, f"[RETRY] {desc}")

    def should_escalate(self, session: RetrySession | dict[str, Any]) -> bool:
        """Check whether escalation to Apex is warranted.

        Returns True only if:
        - All 12 attempts have been exhausted, OR
        - A hardware/software impossibility was detected.

        Never escalates pre-emptively for difficulty alone.

        Args:
            session: RetrySession or dict from attempt_task.

        Returns:
            True if escalation is warranted.
        """
        if isinstance(session, dict):
            attempts = session.get("attempts", [])
            max_attempts = session.get("max_attempts", 12)
            status = session.get("status", "")

            # Check impossibility in any attempt
            for a in attempts:
                error = a.get("error", "") or ""
                if self._is_impossibility(error):
                    return True

            return len(attempts) >= max_attempts or status == "exhausted"

        # RetrySession object
        for a in session.attempts:
            if a.error and self._is_impossibility(a.error):
                return True

        return len(session.attempts) >= session.max_attempts or session.status == "exhausted"

    def get_session_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent retry sessions for analytics.

        Feeds into Growth Engine metrics.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of session summary dicts, most recent first.
        """
        return list(reversed(self._session_history[-limit:]))

    # ── Private Helpers ──────────────────────────────────────────────

    def _build_strategy_context(
        self,
        task: str,
        attempt_num: int,
        strategy_name: str,
        strategy_desc: str,
        previous_attempts: list[Attempt],
        failure_context: str,
        extra_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the full context dict for an attempt."""
        context: dict[str, Any] = {
            "task": task,
            "attempt_number": attempt_num,
            "strategy": strategy_name,
            "strategy_description": strategy_desc,
            "max_attempts": 12,
            **extra_context,
        }

        if failure_context:
            context["failure_context"] = failure_context

        if previous_attempts:
            history = []
            for a in previous_attempts:
                history.append({
                    "attempt": a.attempt_number,
                    "strategy": a.strategy,
                    "error": a.error,
                    "duration": a.duration_seconds,
                })
            context["previous_attempts"] = history
            context["instruction"] = (
                f"You have tried {len(previous_attempts)} approaches. "
                f"Strategy '{previous_attempts[-1].strategy}' failed because: "
                f"{previous_attempts[-1].error}. "
                f"Use a FUNDAMENTALLY different approach: {strategy_desc}"
            )
        else:
            context["instruction"] = f"Approach: {strategy_desc}"

        return context

    def _build_attempts_summary(self, attempts: list[Attempt]) -> str:
        """Build a human-readable summary of all attempts for Apex."""
        lines = []
        for a in attempts:
            status = "SUCCESS" if a.success else "FAILED"
            lines.append(
                f"Attempt {a.attempt_number} ({a.strategy}) [{status}]: "
                f"{a.approach_description[:80]}. "
                f"Error: {a.error or 'N/A'}. Duration: {a.duration_seconds:.1f}s"
            )
        return "\n".join(lines)

    def _extract_common_failures(self, attempts: list[Attempt]) -> str:
        """Extract a summary of what went wrong across all attempts."""
        errors = [a.error for a in attempts if a.error]
        if not errors:
            return "unknown failure mode"
        # Deduplicate and summarize
        unique = list(dict.fromkeys(errors))[:5]
        return "; ".join(unique)

    async def _send_progress(
        self, notify_fn: Callable, attempt_num: int, session: RetrySession
    ) -> None:
        """Send progress notifications at milestone attempts."""
        try:
            if attempt_num == 4:
                await notify_fn(
                    "Still working. Tried 3 approaches, switching strategies."
                )
            elif attempt_num == 8:
                summary = self._build_attempts_summary(session.attempts[-7:])
                await notify_fn(
                    f"Tried 7 approaches. Here's what I've learned so far:\n"
                    f"{summary}\nStill have strategies to try."
                )
            elif attempt_num == 12:
                summary = self._build_attempts_summary(session.attempts)
                await notify_fn(
                    f"Exhausted 12 approaches. Full debrief:\n{summary}\n"
                    f"Ready to escalate to Apex if you approve."
                )
        except Exception as e:
            logger.warning("Progress notification failed: %s", e)

    def _is_impossibility(self, error: str) -> bool:
        """Check if an error indicates hardware/software impossibility."""
        error_lower = error.lower()
        return any(marker in error_lower for marker in _IMPOSSIBILITY_MARKERS)

    def _session_to_dict(self, session: RetrySession) -> dict[str, Any]:
        """Convert a RetrySession to a serializable dict."""
        return {
            "session_id": session.session_id,
            "original_task": session.original_task,
            "task_type": session.task_type,
            "module": session.module,
            "attempts": [
                {
                    "attempt_number": a.attempt_number,
                    "strategy": a.strategy,
                    "approach_description": a.approach_description,
                    "tools_used": a.tools_used,
                    "result": a.result,
                    "error": a.error,
                    "success": a.success,
                    "duration_seconds": a.duration_seconds,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in session.attempts
            ],
            "max_attempts": session.max_attempts,
            "current_attempt": session.current_attempt,
            "status": session.status,
            "final_result": session.final_result,
            "escalation_data": session.escalation_data,
        }

    def _record_session(self, session: RetrySession) -> None:
        """Record a session in the history buffer."""
        entry = self._session_to_dict(session)
        self._session_history.append(entry)
        # Trim history
        if len(self._session_history) > self._max_history:
            self._session_history = self._session_history[-self._max_history:]
