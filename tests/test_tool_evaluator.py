"""Tests for Tool Result Evaluation between chained calls."""

import pytest
from modules.shadow.tool_evaluator import ToolResultEvaluator, EvaluationResult


@pytest.fixture
def evaluator():
    """Create a ToolResultEvaluator with default config."""
    return ToolResultEvaluator()


# --- Error detection ---


class TestErrorDetection:
    """Tests for error keyword detection in tool output."""

    def test_result_with_error_keyword(self, evaluator):
        result = evaluator.evaluate(
            "search", "string", {"output": "An error occurred while searching"}
        )
        assert not result.passed
        assert result.result_type == "failure"
        assert any("error" in i for i in result.issues)

    def test_result_with_traceback(self, evaluator):
        result = evaluator.evaluate(
            "execute", "string", {"output": "Traceback (most recent call last):"}
        )
        assert not result.passed
        assert result.result_type == "failure"

    def test_result_with_http_404(self, evaluator):
        result = evaluator.evaluate(
            "fetch", "json", {"output": "Not Found", "status_code": 404}
        )
        assert not result.passed
        assert result.result_type == "failure"
        assert any("404" in i for i in result.issues)

    def test_result_with_http_500(self, evaluator):
        result = evaluator.evaluate(
            "api_call", "json", {"output": "Internal Server Error", "status_code": 500}
        )
        assert not result.passed

    def test_empty_result(self, evaluator):
        result = evaluator.evaluate("search", "string", {"output": ""})
        assert not result.passed
        assert result.result_type == "failure"
        assert any("empty" in i.lower() for i in result.issues)

    def test_none_result(self, evaluator):
        result = evaluator.evaluate("search", "string", {"output": None})
        assert not result.passed
        assert result.result_type == "failure"

    def test_valid_result_passes(self, evaluator):
        result = evaluator.evaluate(
            "search", "string", {"output": "Here are the search results with data"}
        )
        assert result.passed
        assert result.result_type == "success"

    def test_error_field_in_result(self, evaluator):
        result = evaluator.evaluate(
            "tool", "string", {"output": "", "error": "Connection refused"}
        )
        assert not result.passed
        assert any("Connection refused" in i for i in result.issues)


# --- Type checking ---


class TestTypeChecking:
    """Tests for expected output type validation."""

    def test_expected_json_got_valid_json(self, evaluator):
        result = evaluator.evaluate(
            "api", "json", {"output": '{"key": "value", "count": 42}'}
        )
        assert result.passed
        assert result.result_type == "success"

    def test_expected_json_got_plain_text(self, evaluator):
        result = evaluator.evaluate(
            "api", "json", {"output": "This is just plain text, not JSON at all"}
        )
        assert not result.passed
        assert any("json" in i.lower() for i in result.issues)

    def test_expected_number_got_number(self, evaluator):
        result = evaluator.evaluate("calc", "number", {"output": "42"})
        assert result.passed

    def test_expected_number_got_float(self, evaluator):
        result = evaluator.evaluate("calc", "number", {"output": "3.14159"})
        assert result.passed

    def test_expected_number_got_text(self, evaluator):
        result = evaluator.evaluate(
            "calc", "number", {"output": "hello world this is not a number"}
        )
        assert not result.passed
        assert any("number" in i.lower() for i in result.issues)

    def test_expected_list_got_json_array(self, evaluator):
        result = evaluator.evaluate(
            "search", "list", {"output": '["item1", "item2", "item3"]'}
        )
        assert result.passed

    def test_expected_list_got_non_list(self, evaluator):
        result = evaluator.evaluate(
            "search", "list", {"output": "This is definitely not a list format"}
        )
        assert not result.passed


# --- Content validation ---


class TestContentValidation:
    """Tests for content quality validation."""

    def test_nonempty_meaningful_result(self, evaluator):
        result = evaluator.evaluate(
            "search", "string", {"output": "Found 5 matching documents in the database"}
        )
        assert result.passed

    def test_whitespace_only_result(self, evaluator):
        result = evaluator.evaluate("search", "string", {"output": "   \n\t  "})
        assert not result.passed

    def test_result_contains_expected_keywords(self, evaluator):
        plan_step = {"success_criteria": ["temperature", "forecast"]}
        result = evaluator.evaluate(
            "weather",
            "string",
            {"output": "The temperature today is 72F with a clear forecast"},
            plan_step=plan_step,
        )
        assert result.passed
        assert result.confidence > 0.8

    def test_result_missing_expected_keywords(self, evaluator):
        plan_step = {"success_criteria": ["temperature", "forecast"]}
        result = evaluator.evaluate(
            "weather",
            "string",
            {"output": "Something unrelated about cooking recipes"},
            plan_step=plan_step,
        )
        assert any("missing" in i.lower() for i in result.issues)


# --- Size validation ---


class TestSizeValidation:
    """Tests for result size validation."""

    def test_very_short_result_for_content_task(self, evaluator):
        result = evaluator.evaluate("search", "string", {"output": "ok"})
        assert any("short" in i.lower() for i in result.issues)

    def test_normal_sized_result(self, evaluator):
        result = evaluator.evaluate(
            "search", "string", {"output": "A perfectly normal search result with content"}
        )
        assert result.passed
        assert not any("short" in i.lower() for i in result.issues)
        assert not any("large" in i.lower() for i in result.issues)

    def test_oversized_result(self, evaluator):
        big = "x" * 1_100_000
        result = evaluator.evaluate("search", "string", {"output": big})
        assert any("large" in i.lower() for i in result.issues)


# --- Recommendations ---


class TestRecommendations:
    """Tests for recommendation logic."""

    def test_all_pass_recommends_proceed(self, evaluator):
        result = evaluator.evaluate(
            "search", "string", {"output": "Good result with enough content here"}
        )
        assert result.recommendation == "proceed"

    def test_transient_error_recommends_retry(self, evaluator):
        result = evaluator.evaluate(
            "fetch", "json", {"output": "Request timed out after 30s"}
        )
        assert result.recommendation == "retry_step"

    def test_wrong_tool_recommends_replan(self, evaluator):
        result = evaluator.evaluate(
            "bad_tool", "string", {"output": "not supported for this operation"}
        )
        assert result.recommendation == "replan"

    def test_security_issue_recommends_abort(self, evaluator):
        result = evaluator.evaluate(
            "file_read", "string", {"output": "permission denied: access denied to /etc/shadow"}
        )
        assert result.recommendation == "abort"


# --- Chain progress ---


class TestChainProgress:
    """Tests for evaluate_chain_progress."""

    def test_three_successful_steps(self, evaluator):
        steps = [
            {"tool_name": "step1", "evaluation": {"passed": True}},
            {"tool_name": "step2", "evaluation": {"passed": True}},
            {"tool_name": "step3", "evaluation": {"passed": True}},
        ]
        progress = evaluator.evaluate_chain_progress(steps)
        assert progress["on_track"] is True
        assert progress["steps_failed"] == 0

    def test_same_step_failed_three_times(self, evaluator):
        steps = [
            {"tool_name": "fetch", "evaluation": {"passed": False}},
            {"tool_name": "fetch", "evaluation": {"passed": False}},
            {"tool_name": "fetch", "evaluation": {"passed": False}},
        ]
        progress = evaluator.evaluate_chain_progress(steps)
        assert progress["on_track"] is False
        assert progress["divergence_detected"] is True
        assert "replan" in progress["suggestion"].lower()

    def test_empty_steps_valid_default(self, evaluator):
        progress = evaluator.evaluate_chain_progress([])
        assert progress["on_track"] is True
        assert progress["divergence_detected"] is False
        assert progress["steps_failed"] == 0

    def test_mixed_results(self, evaluator):
        steps = [
            {"tool_name": "a", "evaluation": {"passed": True}},
            {"tool_name": "b", "evaluation": {"passed": False}},
            {"tool_name": "c", "evaluation": {"passed": True}},
            {"tool_name": "d", "evaluation": {"passed": True}},
        ]
        progress = evaluator.evaluate_chain_progress(steps)
        assert progress["on_track"] is True
        assert progress["steps_failed"] == 1

    def test_with_evaluation_result_objects(self, evaluator):
        steps = [
            {
                "tool_name": "a",
                "evaluation": EvaluationResult(
                    passed=True, result_type="success", confidence=1.0
                ),
            },
            {
                "tool_name": "b",
                "evaluation": EvaluationResult(
                    passed=False, result_type="failure", confidence=0.8
                ),
            },
        ]
        progress = evaluator.evaluate_chain_progress(steps)
        assert progress["steps_failed"] == 1


# --- Formatting ---


class TestFormatting:
    """Tests for format_evaluation_for_context."""

    def test_format_produces_readable_string(self, evaluator):
        ev = EvaluationResult(
            passed=True,
            result_type="success",
            confidence=0.95,
            issues=[],
            recommendation="proceed",
            details={"tool_name": "search"},
        )
        text = evaluator.format_evaluation_for_context(ev)
        assert "search" in text
        assert "success" in text
        assert "proceed" in text

    def test_format_includes_issues(self, evaluator):
        ev = EvaluationResult(
            passed=False,
            result_type="failure",
            confidence=0.7,
            issues=["Result is empty", "Expected JSON"],
            recommendation="retry_step",
            details={"tool_name": "api_call"},
        )
        text = evaluator.format_evaluation_for_context(ev)
        assert "api_call" in text
        assert "failure" in text
        assert "retry_step" in text
        assert "Result is empty" in text
