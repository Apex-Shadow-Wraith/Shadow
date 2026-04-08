"""Tests for the Adversarial Self-Review Pass."""

import time
import pytest

from modules.shadow.self_review import SelfReviewer, ReviewResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeConfidenceScorer:
    """Returns a configurable confidence score."""

    def __init__(self, score: float = 0.5):
        self._score = score

    def set_score(self, score: float):
        self._score = score

    def score_response(self, task, response, task_type="", context=None):
        return {"confidence": self._score}


def make_generate_fn(response: str = "generated response"):
    """Return a simple generate_fn that always returns *response*."""
    calls = []

    def fn(prompt: str) -> str:
        calls.append(prompt)
        return response

    fn.calls = calls
    return fn


def make_sequenced_generate_fn(responses: list[str]):
    """Return a generate_fn that returns responses in sequence."""
    idx = [0]

    def fn(prompt: str) -> str:
        i = idx[0]
        idx[0] += 1
        if i < len(responses):
            return responses[i]
        return responses[-1]

    return fn


# ---------------------------------------------------------------------------
# ReviewResult dataclass
# ---------------------------------------------------------------------------

class TestReviewResult:
    def test_review_result_has_all_fields(self):
        r = ReviewResult(
            original_response="orig",
            reviewed_response="reviewed",
            review_cycles=1,
            issues_found=["issue1"],
            issues_fixed=["issue1"],
            confidence_before=0.4,
            confidence_after=0.8,
            improved=True,
            duration_seconds=0.5,
        )
        assert r.original_response == "orig"
        assert r.reviewed_response == "reviewed"
        assert r.review_cycles == 1
        assert r.issues_found == ["issue1"]
        assert r.issues_fixed == ["issue1"]
        assert r.confidence_before == 0.4
        assert r.confidence_after == 0.8
        assert r.improved is True
        assert r.duration_seconds == 0.5


# ---------------------------------------------------------------------------
# review() method
# ---------------------------------------------------------------------------

class TestReview:
    def test_high_confidence_returns_original_no_review(self):
        """High confidence responses skip review entirely."""
        scorer = FakeConfidenceScorer(score=0.9)
        reviewer = SelfReviewer(confidence_scorer=scorer)

        result = reviewer.review("What is 2+2?", "4", "math")

        assert result.reviewed_response == "4"
        assert result.review_cycles == 0
        assert result.issues_found == []
        assert result.improved is False
        assert result.confidence_before == 0.9

    def test_low_confidence_triggers_review(self):
        """Low confidence responses trigger the review pass."""
        scorer = FakeConfidenceScorer(score=0.4)
        gen = make_generate_fn("No issues found.")
        reviewer = SelfReviewer(
            generate_fn=gen, confidence_scorer=scorer
        )

        result = reviewer.review("task", "response", "code")

        assert result.review_cycles >= 1
        assert len(gen.calls) >= 1  # At least the review call happened

    def test_issues_found_triggers_regeneration(self):
        """When issues are found, a corrected response is generated."""
        scorer = FakeConfidenceScorer(score=0.4)
        responses = [
            "1. Missing edge case for empty input\n2. No error handling",
            "Corrected response with edge cases",
        ]
        gen = make_sequenced_generate_fn(responses)

        # Make corrected score higher
        scores = [0.4, 0.4, 0.8]  # original, original again (recheck), corrected
        call_idx = [0]
        original_score = scorer.score_response

        def varying_score(task, response, task_type="", context=None):
            i = call_idx[0]
            call_idx[0] += 1
            s = scores[i] if i < len(scores) else 0.8
            return {"confidence": s}

        scorer.score_response = varying_score

        reviewer = SelfReviewer(generate_fn=gen, confidence_scorer=scorer)
        result = reviewer.review("task", "original", "code")

        assert result.issues_found
        assert result.review_cycles >= 1

    def test_corrected_scores_higher_uses_corrected(self):
        """When corrected response scores higher, it replaces the original."""
        call_idx = [0]
        scores = [0.3, 0.8]  # original low, corrected high

        def varying_score(task, response, task_type="", context=None):
            i = call_idx[0]
            call_idx[0] += 1
            return {"confidence": scores[min(i, len(scores) - 1)]}

        scorer = FakeConfidenceScorer()
        scorer.score_response = varying_score

        responses = ["1. Issue found", "Better response"]
        gen = make_sequenced_generate_fn(responses)

        reviewer = SelfReviewer(generate_fn=gen, confidence_scorer=scorer)
        result = reviewer.review("task", "bad response", "code")

        assert result.improved is True
        assert result.reviewed_response == "Better response"
        assert result.confidence_after > result.confidence_before

    def test_corrected_scores_lower_reverts_to_original(self):
        """When corrected response scores lower, revert to original."""
        call_idx = [0]
        scores = [0.5, 0.3]  # original, corrected (worse)

        def varying_score(task, response, task_type="", context=None):
            i = call_idx[0]
            call_idx[0] += 1
            return {"confidence": scores[min(i, len(scores) - 1)]}

        scorer = FakeConfidenceScorer()
        scorer.score_response = varying_score

        responses = ["1. Some issue", "Worse response"]
        gen = make_sequenced_generate_fn(responses)

        reviewer = SelfReviewer(generate_fn=gen, confidence_scorer=scorer)
        result = reviewer.review("task", "original response", "code")

        assert result.improved is False
        assert result.reviewed_response == "original response"

    def test_max_two_cycles_enforced(self):
        """Review never exceeds max_cycles (default 2)."""
        call_idx = [0]
        # Scores keep improving to tempt more cycles
        scores = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

        def varying_score(task, response, task_type="", context=None):
            i = call_idx[0]
            call_idx[0] += 1
            return {"confidence": scores[min(i, len(scores) - 1)]}

        scorer = FakeConfidenceScorer()
        scorer.score_response = varying_score

        # Always find issues and generate corrections
        responses = [
            "1. Issue A",
            "corrected A",
            "1. Issue B",
            "corrected B",
            "1. Issue C",
            "corrected C",
        ]
        gen = make_sequenced_generate_fn(responses)

        reviewer = SelfReviewer(generate_fn=gen, confidence_scorer=scorer)
        result = reviewer.review("task", "original", "code")

        assert result.review_cycles <= 2

    def test_no_issues_found_returns_original(self):
        """When reviewer says 'No issues found', return original."""
        scorer = FakeConfidenceScorer(score=0.4)
        gen = make_generate_fn("No issues found.")

        reviewer = SelfReviewer(generate_fn=gen, confidence_scorer=scorer)
        result = reviewer.review("task", "good response", "code")

        assert result.reviewed_response == "good response"
        assert result.issues_found == []
        assert result.review_cycles == 1

    def test_generate_fn_failure_returns_original(self):
        """If generate_fn raises, return original response gracefully."""
        scorer = FakeConfidenceScorer(score=0.4)

        def failing_fn(prompt):
            raise RuntimeError("LLM down")

        reviewer = SelfReviewer(generate_fn=failing_fn, confidence_scorer=scorer)
        result = reviewer.review("task", "original", "code")

        assert result.reviewed_response == "original"
        assert result.improved is False

    def test_no_generate_fn_returns_original(self):
        """If generate_fn is None, return original response."""
        scorer = FakeConfidenceScorer(score=0.4)
        reviewer = SelfReviewer(generate_fn=None, confidence_scorer=scorer)
        result = reviewer.review("task", "original", "code")

        assert result.reviewed_response == "original"
        assert result.improved is False

    def test_confidence_scorer_unavailable_reviews_by_task_type(self):
        """Without a confidence scorer, score defaults to 0.5 (below threshold)."""
        gen = make_generate_fn("No issues found.")
        reviewer = SelfReviewer(generate_fn=gen, confidence_scorer=None)

        result = reviewer.review("task", "response", "code")

        # 0.5 < 0.7 threshold → review should trigger
        assert result.review_cycles >= 1

    def test_duration_tracked(self):
        """ReviewResult tracks duration."""
        scorer = FakeConfidenceScorer(score=0.9)
        reviewer = SelfReviewer(confidence_scorer=scorer)

        result = reviewer.review("task", "response", "code")
        assert result.duration_seconds >= 0


# ---------------------------------------------------------------------------
# should_review()
# ---------------------------------------------------------------------------

class TestShouldReview:
    def test_code_task_low_confidence(self):
        reviewer = SelfReviewer()
        assert reviewer.should_review("code", 0.4) is True

    def test_math_task_low_confidence(self):
        reviewer = SelfReviewer()
        assert reviewer.should_review("math", 0.5) is True

    def test_security_task_low_confidence(self):
        reviewer = SelfReviewer()
        assert reviewer.should_review("security", 0.3) is True

    def test_analysis_task_low_confidence(self):
        reviewer = SelfReviewer()
        assert reviewer.should_review("analysis", 0.6) is True

    def test_greeting_skipped(self):
        reviewer = SelfReviewer()
        assert reviewer.should_review("greeting", 0.3) is False

    def test_conversation_skipped(self):
        reviewer = SelfReviewer()
        assert reviewer.should_review("conversation", 0.3) is False

    def test_high_confidence_skipped(self):
        reviewer = SelfReviewer()
        assert reviewer.should_review("code", 0.9) is False

    def test_empty_task_type_skipped(self):
        reviewer = SelfReviewer()
        assert reviewer.should_review("", 0.3) is False

    def test_system_task_skipped(self):
        reviewer = SelfReviewer()
        assert reviewer.should_review("system", 0.3) is False


# ---------------------------------------------------------------------------
# parse_review_issues()
# ---------------------------------------------------------------------------

class TestParseReviewIssues:
    def test_numbered_list(self):
        reviewer = SelfReviewer()
        text = "1. Missing error handling\n2. No input validation\n3. SQL injection risk"
        issues = reviewer.parse_review_issues(text)
        assert len(issues) == 3
        assert "Missing error handling" in issues[0]

    def test_bullet_list(self):
        reviewer = SelfReviewer()
        text = "- Off by one error\n- Missing null check"
        issues = reviewer.parse_review_issues(text)
        assert len(issues) == 2

    def test_no_issues_found_string(self):
        reviewer = SelfReviewer()
        assert reviewer.parse_review_issues("No issues found.") == []

    def test_no_issues_found_variant(self):
        reviewer = SelfReviewer()
        assert reviewer.parse_review_issues("The response is correct and complete.") == []

    def test_empty_string(self):
        reviewer = SelfReviewer()
        assert reviewer.parse_review_issues("") == []

    def test_none_input(self):
        reviewer = SelfReviewer()
        assert reviewer.parse_review_issues(None) == []

    def test_issue_prefix_format(self):
        reviewer = SelfReviewer()
        text = "Issue 1: Buffer overflow\nIssue 2: Memory leak"
        issues = reviewer.parse_review_issues(text)
        assert len(issues) == 2
        assert "Buffer overflow" in issues[0]


# ---------------------------------------------------------------------------
# get_review_stats()
# ---------------------------------------------------------------------------

class TestGetReviewStats:
    def test_returns_valid_stats_empty(self):
        reviewer = SelfReviewer()
        stats = reviewer.get_review_stats()
        assert stats["total_reviewed"] == 0
        assert stats["issues_found_rate"] == 0.0
        assert stats["improvement_rate"] == 0.0
        assert stats["avg_cycles"] == 0.0
        assert stats["revert_rate"] == 0.0

    def test_stats_after_reviews(self):
        scorer = FakeConfidenceScorer(score=0.4)
        gen = make_generate_fn("No issues found.")
        reviewer = SelfReviewer(generate_fn=gen, confidence_scorer=scorer)

        # Run a review that actually triggers
        reviewer.review("task", "response", "code")

        stats = reviewer.get_review_stats()
        assert stats["total_reviewed"] == 1
        assert isinstance(stats["improvement_rate"], float)
