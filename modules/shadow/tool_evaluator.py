"""Tool Result Evaluation Between Chained Calls.

After every tool call in a multi-step chain, evaluate the result before
proceeding. Prevents blindly proceeding through a broken workflow.
All evaluation is rule-based — no LLM calls.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EvaluationResult:
    """Result of evaluating a tool's output."""

    passed: bool
    result_type: str  # "success", "partial", "failure", "unexpected"
    confidence: float  # 0.0-1.0
    issues: list[str] = field(default_factory=list)
    recommendation: str = "proceed"  # "proceed", "retry_step", "replan", "abort"
    details: dict = field(default_factory=dict)


# Keywords indicating errors in tool output
_ERROR_KEYWORDS = [
    "traceback",
    "exception",
    "error",
    "failed",
]

# Keywords indicating security/corruption issues
_CRITICAL_KEYWORDS = [
    "permission denied",
    "access denied",
    "data corruption",
    "integrity check failed",
    "unauthorized",
    "malicious",
]

# Keywords suggesting the wrong tool was used
_WRONG_TOOL_KEYWORDS = [
    "not supported",
    "invalid tool",
    "unknown command",
    "no such tool",
    "not implemented",
]

# Transient/recoverable error keywords
_TRANSIENT_KEYWORDS = [
    "timeout",
    "timed out",
    "connection reset",
    "temporarily unavailable",
    "rate limit",
    "retry",
    "503",
    "429",
]

# Maximum result size (1 MB)
_MAX_RESULT_SIZE = 1_000_000

# Minimum result length for content tasks
_MIN_CONTENT_LENGTH = 10


class ToolResultEvaluator:
    """Evaluates tool results between chained calls."""

    def __init__(self, config: dict = None):
        """Initialize evaluator with optional configuration.

        Args:
            config: Optional dict with evaluation settings.
        """
        self.config = config or {}
        self.max_retries = self.config.get("max_retries", 3)
        self.min_content_length = self.config.get(
            "min_content_length", _MIN_CONTENT_LENGTH
        )
        self.max_result_size = self.config.get("max_result_size", _MAX_RESULT_SIZE)

    def evaluate(
        self,
        tool_name: str,
        expected_output: str,
        actual_result: dict,
        plan_step: dict = None,
    ) -> EvaluationResult:
        """Evaluate a tool's result against expectations.

        Args:
            tool_name: Name of the tool that produced the result.
            expected_output: Expected output type/description
                ("json", "list", "string", "number", or free text).
            actual_result: The actual result dict from the tool.
                Expected keys: "output" (the content), optionally
                "status_code", "error".
            plan_step: Optional plan step dict with "success_criteria"
                (list of keywords) and other metadata.

        Returns:
            EvaluationResult with pass/fail, issues, and recommendation.
        """
        issues = []
        confidence = 1.0
        result_type = "success"
        details = {"tool_name": tool_name}

        output = actual_result.get("output", "")
        output_str = str(output) if output is not None else ""
        status_code = actual_result.get("status_code")

        # --- Error detection ---
        critical = self._check_critical(output_str)
        if critical:
            return EvaluationResult(
                passed=False,
                result_type="failure",
                confidence=0.95,
                issues=critical,
                recommendation="abort",
                details=details,
            )

        wrong_tool = self._check_wrong_tool(output_str)
        if wrong_tool:
            return EvaluationResult(
                passed=False,
                result_type="failure",
                confidence=0.85,
                issues=wrong_tool,
                recommendation="replan",
                details=details,
            )

        transient = self._check_transient(output_str)
        if transient:
            return EvaluationResult(
                passed=False,
                result_type="failure",
                confidence=0.8,
                issues=transient,
                recommendation="retry_step",
                details=details,
            )

        error_issues = self._check_errors(output_str)
        if error_issues:
            issues.extend(error_issues)
            result_type = "failure"
            confidence = min(confidence, 0.8)

        if status_code is not None and status_code >= 400:
            issues.append(f"HTTP status {status_code} indicates failure")
            result_type = "failure"
            confidence = min(confidence, 0.85)

        # --- Empty result ---
        if actual_result.get("error"):
            issues.append(f"Tool returned error: {actual_result['error']}")
            result_type = "failure"
            confidence = min(confidence, 0.8)

        if output is None or (isinstance(output, str) and not output_str.strip()):
            issues.append("Result is empty or whitespace-only")
            result_type = "failure"
            confidence = min(confidence, 0.9)

        # --- Type checking ---
        if expected_output and result_type != "failure":
            type_issues = self._check_type(expected_output, output_str)
            if type_issues:
                issues.extend(type_issues)
                result_type = "failure"
                confidence = min(confidence, 0.85)

        # --- Content validation ---
        if result_type != "failure" and output_str.strip():
            content_issues = self._check_content(output_str, plan_step)
            if content_issues:
                issues.extend(content_issues)
                if any("echo" in i.lower() for i in content_issues):
                    result_type = "partial"
                    confidence = min(confidence, 0.6)
                else:
                    confidence = min(confidence, 0.7)

        # --- Size validation ---
        if result_type != "failure" and output_str.strip():
            size_issues = self._check_size(output_str, expected_output)
            if size_issues:
                issues.extend(size_issues)
                if result_type == "success":
                    result_type = "partial"
                confidence = min(confidence, 0.7)

        # --- Determine recommendation ---
        passed = result_type in ("success", "partial")
        if result_type == "success" and not issues:
            recommendation = "proceed"
        elif result_type == "partial":
            recommendation = "proceed"
        elif result_type == "failure":
            recommendation = "retry_step"
        else:
            recommendation = "proceed"

        return EvaluationResult(
            passed=passed,
            result_type=result_type,
            confidence=confidence,
            issues=issues,
            recommendation=recommendation,
            details=details,
        )

    def evaluate_chain_progress(
        self, steps_completed: list[dict], plan: dict = None
    ) -> dict:
        """Evaluate progress across a chain of completed steps.

        Args:
            steps_completed: List of dicts, each with keys:
                "tool_name", "evaluation" (EvaluationResult or dict),
                "step_index" (optional).
            plan: Optional plan dict with "total_steps" and "goal".

        Returns:
            Dict with on_track, divergence_detected, steps_failed, suggestion.
        """
        if not steps_completed:
            return {
                "on_track": True,
                "divergence_detected": False,
                "steps_failed": 0,
                "suggestion": "No steps completed yet — ready to begin.",
            }

        steps_failed = 0
        consecutive_failures = 0
        max_consecutive = 0
        failure_counts: dict[str, int] = {}

        for step in steps_completed:
            ev = step.get("evaluation", {})
            if isinstance(ev, EvaluationResult):
                passed = ev.passed
                tool = step.get("tool_name", "unknown")
            else:
                passed = ev.get("passed", True)
                tool = step.get("tool_name", "unknown")

            if not passed:
                steps_failed += 1
                consecutive_failures += 1
                max_consecutive = max(max_consecutive, consecutive_failures)
                failure_counts[tool] = failure_counts.get(tool, 0) + 1
            else:
                consecutive_failures = 0

        # Check if same step failed multiple times
        repeated_failures = {
            t: c for t, c in failure_counts.items() if c >= self.max_retries
        }

        total_steps = len(steps_completed)
        failure_rate = steps_failed / total_steps if total_steps > 0 else 0.0

        on_track = failure_rate < 0.5 and not repeated_failures
        divergence_detected = bool(repeated_failures) or max_consecutive >= 3

        # Build suggestion
        if repeated_failures:
            tools = ", ".join(repeated_failures.keys())
            suggestion = (
                f"Tool(s) {tools} failed {self.max_retries}+ times — "
                f"consider replanning with different tools."
            )
        elif max_consecutive >= 3:
            suggestion = (
                f"{max_consecutive} consecutive failures — "
                f"chain may be broken, consider replanning."
            )
        elif failure_rate > 0.3:
            suggestion = (
                f"High failure rate ({failure_rate:.0%}) — "
                f"review plan feasibility."
            )
        elif steps_failed > 0:
            suggestion = (
                f"{steps_failed}/{total_steps} steps had issues — "
                f"proceeding with caution."
            )
        else:
            suggestion = (
                f"All {total_steps} steps successful — on track."
            )

        return {
            "on_track": on_track,
            "divergence_detected": divergence_detected,
            "steps_failed": steps_failed,
            "suggestion": suggestion,
        }

    def format_evaluation_for_context(self, evaluation: EvaluationResult) -> str:
        """Format an evaluation result as a string for context injection.

        Args:
            evaluation: The EvaluationResult to format.

        Returns:
            Human-readable string summarizing the evaluation.
        """
        tool_name = evaluation.details.get("tool_name", "unknown")
        issues_str = "; ".join(evaluation.issues) if evaluation.issues else "none"
        return (
            f"Previous step ({tool_name}) result: {evaluation.result_type}. "
            f"Issues: {issues_str}. "
            f"Recommendation: {evaluation.recommendation}."
        )

    # --- Private helpers ---

    def _check_errors(self, output: str) -> list[str]:
        """Check for error keywords in output."""
        issues = []
        lower = output.lower()
        for kw in _ERROR_KEYWORDS:
            if kw in lower:
                issues.append(f"Result contains error indicator: '{kw}'")
                break  # one is enough
        return issues

    def _check_critical(self, output: str) -> list[str]:
        """Check for critical/security issues."""
        issues = []
        lower = output.lower()
        for kw in _CRITICAL_KEYWORDS:
            if kw in lower:
                issues.append(f"Critical issue detected: '{kw}'")
        return issues

    def _check_wrong_tool(self, output: str) -> list[str]:
        """Check if output suggests wrong tool was used."""
        issues = []
        lower = output.lower()
        for kw in _WRONG_TOOL_KEYWORDS:
            if kw in lower:
                issues.append(f"Wrong tool indicator: '{kw}'")
                return issues
        return issues

    def _check_transient(self, output: str) -> list[str]:
        """Check for transient/recoverable errors."""
        issues = []
        lower = output.lower()
        for kw in _TRANSIENT_KEYWORDS:
            if kw in lower:
                issues.append(f"Transient error detected: '{kw}'")
                return issues
        return issues

    def _check_type(self, expected: str, output: str) -> list[str]:
        """Check if output matches expected type."""
        issues = []
        expected_lower = expected.lower().strip()

        if expected_lower == "json":
            try:
                json.loads(output.strip())
            except (json.JSONDecodeError, ValueError):
                issues.append("Expected JSON but result is not valid JSON")

        elif expected_lower == "number":
            stripped = output.strip()
            try:
                float(stripped)
            except ValueError:
                issues.append(f"Expected number but got: '{stripped[:50]}'")

        elif expected_lower == "list":
            # Accept JSON arrays or Python-style lists
            stripped = output.strip()
            try:
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    issues.append("Expected list but got non-list JSON")
            except (json.JSONDecodeError, ValueError):
                if not (stripped.startswith("[") and stripped.endswith("]")):
                    issues.append("Expected list but result doesn't look like a list")

        return issues

    def _check_content(self, output: str, plan_step: dict = None) -> list[str]:
        """Validate content quality."""
        issues = []

        # Check for success criteria keywords from plan step
        if plan_step and plan_step.get("success_criteria"):
            criteria = plan_step["success_criteria"]
            lower = output.lower()
            missing = [kw for kw in criteria if kw.lower() not in lower]
            if missing:
                issues.append(
                    f"Missing expected keywords: {', '.join(missing)}"
                )

        return issues

    def _check_size(self, output: str, expected_output: str = "") -> list[str]:
        """Validate result size."""
        issues = []
        length = len(output)

        if length > self.max_result_size:
            issues.append(
                f"Result is suspiciously large ({length:,} bytes, "
                f"max {self.max_result_size:,})"
            )

        # Only flag short results for content-oriented tasks
        expected_lower = (expected_output or "").lower()
        content_types = ("json", "string", "list", "content", "text")
        if expected_lower in content_types or not expected_lower:
            stripped = output.strip()
            if 0 < len(stripped) < self.min_content_length:
                issues.append(
                    f"Result is suspiciously short ({len(stripped)} chars)"
                )

        return issues
