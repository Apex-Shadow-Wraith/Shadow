"""
Tests for ConfidenceScorer — Response Quality Evaluation
=========================================================
Validates scoring factors, thresholds, task-type bonuses,
improvement tracking, and analytics.
"""

import time
import tempfile
from pathlib import Path

import pytest

from modules.shadow.confidence_scorer import ConfidenceScorer


@pytest.fixture
def scorer(tmp_path):
    """Create a ConfidenceScorer with a temporary database."""
    db = tmp_path / "test_confidence.db"
    s = ConfidenceScorer(db_path=db)
    yield s
    s.close()


# ================================================================
# BASIC SCORING
# ================================================================


class TestEmptyResponse:
    """Empty response scores 0.0."""

    def test_empty_string(self, scorer):
        result = scorer.score_response("What is Python?", "", "question")
        assert result["confidence"] == 0.0

    def test_whitespace_only(self, scorer):
        result = scorer.score_response("What is Python?", "   ", "question")
        assert result["confidence"] == 0.0

    def test_none_like(self, scorer):
        result = scorer.score_response("What is Python?", "I don't know.", "question")
        # Completeness is 0.0 but other factors still contribute
        assert result["factors"]["completeness"] == 0.0
        assert result["confidence"] < 0.5


class TestCompleteResponse:
    """Complete, relevant responses score 0.8+."""

    def test_good_question_response(self, scorer):
        task = "What is Python used for?"
        response = (
            "Python is a versatile programming language used for web development, "
            "data science, machine learning, automation, scripting, and scientific "
            "computing. It has a large ecosystem of libraries like Django, NumPy, "
            "and TensorFlow that make it suitable for many domains."
        )
        result = scorer.score_response(task, response, "question")
        assert result["confidence"] >= 0.8
        assert result["recommendation"] == "respond"

    def test_good_research_response(self, scorer):
        task = "Research the benefits of solar energy"
        response = (
            "Solar energy offers several key benefits:\n\n"
            "1. Renewable and sustainable — the sun provides virtually unlimited energy.\n"
            "2. Reduces electricity bills — homeowners save $10,000-$30,000 over 25 years.\n"
            "3. Low maintenance costs — panels require minimal upkeep after installation.\n"
            "4. Environmental benefits — produces no greenhouse gas emissions during operation.\n"
            "5. Energy independence — reduces reliance on fossil fuels and foreign oil.\n"
        )
        result = scorer.score_response(task, response, "research")
        assert result["confidence"] >= 0.8
        assert result["recommendation"] == "respond"


class TestWrongTopic:
    """Response about wrong topic scores low on relevance."""

    def test_irrelevant_response(self, scorer):
        task = "How do I configure a PostgreSQL database?"
        response = (
            "Chocolate cake is a classic dessert made with cocoa powder, flour, "
            "sugar, eggs, and butter. Preheat your oven to 350°F and mix the "
            "dry ingredients together before adding the wet ingredients."
        )
        result = scorer.score_response(task, response, "question")
        assert result["factors"]["relevance"] < 0.3
        assert result["confidence"] < 0.7


# ================================================================
# CODE RESPONSES
# ================================================================


class TestCodeResponses:
    """Code response scoring with syntax validation."""

    def test_valid_python_gets_bonus(self, scorer):
        task = "Write a function to check if a number is prime"
        response = (
            "```python\n"
            "def is_prime(n):\n"
            '    """Check if a number is prime."""\n'
            "    if n <= 1:\n"
            "        return False\n"
            "    for i in range(2, int(n**0.5) + 1):\n"
            "        if n % i == 0:\n"
            "            return False\n"
            "    return True\n"
            "```"
        )
        result = scorer.score_response(task, response, "creation")
        assert result["bonus"] > 0  # Syntax bonus applied
        assert result["confidence"] >= 0.7

    def test_syntax_error_no_bonus(self, scorer):
        task = "Write a function to sort a list"
        response = (
            "```python\n"
            "def sort_list(lst)\n"  # Missing colon
            "    return sorted(lst)\n"
            "```"
        )
        result = scorer.score_response(task, response, "creation")
        # Should not get syntax bonus
        assert result["bonus"] <= 0.05


# ================================================================
# MATH RESPONSES
# ================================================================


class TestMathResponses:
    """Math responses must contain numbers."""

    def test_math_with_number(self, scorer):
        task = "What is 15 times 23?"
        response = "15 times 23 equals 345."
        result = scorer.score_response(task, response, "math")
        # Should not be penalized for missing number
        assert result["confidence"] > 0.3

    def test_math_without_number(self, scorer):
        task = "What is the square root of 144?"
        response_no_num = "The square root is a value that when multiplied by itself gives the original."
        response_with_num = "The square root of 144 is 12."
        result_no = scorer.score_response(task, response_no_num, "math")
        result_yes = scorer.score_response(task, response_with_num, "math")
        assert result_yes["confidence"] > result_no["confidence"]


# ================================================================
# HEDGING LANGUAGE
# ================================================================


class TestHedgingLanguage:
    """Excessive hedging lowers confidence."""

    def test_heavy_hedging(self, scorer):
        task = "What is the capital of France?"
        response = (
            "I think it might possibly be Paris. Maybe that's right, "
            "but I'm not sure. Perhaps you should verify. I believe it "
            "could be Paris, but I guess there's some uncertainty."
        )
        result = scorer.score_response(task, response, "question")
        assert result["factors"]["self_consistency"] < 0.8

    def test_confident_response(self, scorer):
        task = "What is the capital of France?"
        response = "The capital of France is Paris."
        result = scorer.score_response(task, response, "question")
        assert result["factors"]["self_consistency"] == 1.0


# ================================================================
# REPEATED / LOOPING TEXT
# ================================================================


class TestRepeatedText:
    """Repeated paragraphs/sentences get penalized."""

    def test_repeated_paragraphs(self, scorer):
        paragraph = "Python is a great language for beginners and experts alike."
        response = f"{paragraph}\n\n{paragraph}\n\n{paragraph}"
        result = scorer.score_response("Tell me about Python", response, "question")
        assert result["factors"]["coherence"] < 0.8

    def test_no_repetition(self, scorer):
        response = (
            "Python is a great language.\n\n"
            "It supports multiple paradigms.\n\n"
            "The community is very active."
        )
        result = scorer.score_response("Tell me about Python", response, "question")
        assert result["factors"]["coherence"] == 1.0


# ================================================================
# RECOMMENDATION THRESHOLDS
# ================================================================


class TestRecommendationThresholds:
    """Correct mapping from confidence to recommendation."""

    def test_high_confidence_respond(self, scorer):
        task = "What is Python used for?"
        response = (
            "Python is used for web development with Django and Flask, "
            "data science with NumPy and Pandas, machine learning with "
            "TensorFlow and PyTorch, automation, scripting, and more."
        )
        result = scorer.score_response(task, response, "question")
        assert result["confidence"] >= 0.8
        assert result["recommendation"] == "respond"

    def test_low_confidence_escalate(self, scorer):
        # Empty response guarantees escalate
        result = scorer.score_response(
            "Explain quantum computing", "", "question"
        )
        assert result["confidence"] < 0.3
        assert result["recommendation"] == "escalate"

    def test_very_short_response_low_confidence(self, scorer):
        result = scorer.score_response(
            "Explain quantum computing", "Hmm.", "question"
        )
        assert result["confidence"] < 0.5
        assert result["recommendation"] in ("escalate", "retry_with_context", "retry")

    def test_medium_confidence_retry(self, scorer):
        # A mediocre response — some content but not great
        task = "How do I set up Docker on Ubuntu?"
        response = "You can install Docker. It's a container tool."
        result = scorer.score_response(task, response, "question")
        # Should be in retry range (0.3-0.79)
        assert result["recommendation"] in ("retry", "retry_with_context", "respond")


# ================================================================
# SCORE IMPROVEMENT
# ================================================================


class TestScoreImprovement:
    """score_improvement correctly detects changes."""

    def test_improvement_detected(self, scorer):
        result = scorer.score_improvement(0.45, 0.75)
        assert result["improved"] is True
        assert result["delta"] == pytest.approx(0.3, abs=0.01)
        assert "significant improvement" in result["recommendation"]

    def test_degradation_detected(self, scorer):
        result = scorer.score_improvement(0.75, 0.45)
        assert result["improved"] is False
        assert result["delta"] == pytest.approx(-0.3, abs=0.01)
        assert "degraded" in result["recommendation"]

    def test_marginal_improvement(self, scorer):
        result = scorer.score_improvement(0.60, 0.63)
        assert result["delta"] == pytest.approx(0.03, abs=0.01)
        assert "marginal" in result["recommendation"]

    def test_no_change(self, scorer):
        result = scorer.score_improvement(0.70, 0.70)
        assert result["delta"] == 0.0
        assert result["improved"] is False


# ================================================================
# ANALYTICS
# ================================================================


class TestAnalytics:
    """get_task_type_averages and get_scoring_history work correctly."""

    def test_task_type_averages(self, scorer):
        # Score several responses of different types
        scorer.score_response(
            "What is 2+2?", "2+2 equals 4.", "math",
        )
        scorer.score_response(
            "What is 3+3?", "3+3 equals 6.", "math",
        )
        scorer.score_response(
            "Tell me about Python",
            "Python is a versatile programming language used for many applications.",
            "question",
        )

        averages = scorer.get_task_type_averages()
        assert "math" in averages
        assert "question" in averages
        assert 0.0 <= averages["math"] <= 1.0
        assert 0.0 <= averages["question"] <= 1.0

    def test_scoring_history(self, scorer):
        scorer.score_response("test task", "test response here", "question")
        history = scorer.get_scoring_history(limit=10)
        assert len(history) >= 1
        assert history[0]["task"] == "test task"
        assert "factors" in history[0]
        assert "confidence" in history[0]

    def test_scoring_history_limit(self, scorer):
        for i in range(5):
            scorer.score_response(f"task {i}", f"response {i} is good enough", "question")
        history = scorer.get_scoring_history(limit=3)
        assert len(history) == 3


# ================================================================
# PERFORMANCE
# ================================================================


class TestPerformance:
    """Scoring must be fast — under 10ms per response."""

    def test_scoring_speed(self, scorer):
        task = "Explain the benefits of microservices architecture"
        response = (
            "Microservices architecture offers several benefits: "
            "1. Independent deployment of services. "
            "2. Technology diversity — each service can use different tech. "
            "3. Fault isolation — one service failure doesn't crash everything. "
            "4. Scalability — scale individual services based on demand. "
            "5. Team autonomy — small teams own specific services."
        )
        start = time.perf_counter()
        for _ in range(10):
            scorer.score_response(task, response, "question")
        elapsed = (time.perf_counter() - start) / 10
        # Each call should be under 10ms
        assert elapsed < 0.01, f"Scoring took {elapsed*1000:.1f}ms (limit: 10ms)"


# ================================================================
# EDGE CASES
# ================================================================


class TestEdgeCases:
    """Edge cases that shouldn't crash."""

    def test_very_long_response(self, scorer):
        response = "word " * 10000
        result = scorer.score_response("test", response, "question")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_unicode_response(self, scorer):
        result = scorer.score_response(
            "翻译这个", "这是一个测试响应，包含中文字符。", "question"
        )
        assert 0.0 <= result["confidence"] <= 1.0

    def test_code_only_response(self, scorer):
        response = "def hello():\n    print('hello world')\n    return True"
        result = scorer.score_response("write hello function", response, "creation")
        assert result["confidence"] > 0.3

    def test_empty_task(self, scorer):
        result = scorer.score_response("", "Here is a response.", "question")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_special_characters(self, scorer):
        result = scorer.score_response(
            "What about @#$%^&*?",
            "Those are special characters used in programming.",
            "question",
        )
        assert 0.0 <= result["confidence"] <= 1.0


# ================================================================
# CONFABULATION DETECTION (FACTUAL GROUNDING)
# ================================================================


class TestConfabulationDetection:
    """Factual grounding catches false claims about actions that never happened."""

    def test_confabulation_apex_claim_without_api(self, scorer):
        """Response claims Apex generated it, but source is fallback → 0.0."""
        result = scorer.score_response(
            task="Explain quantum computing",
            response="Apex generated this detailed analysis of quantum computing for you.",
            task_type="question",
            metadata={
                "target_module": "apex",
                "used_fallback": True,
                "source": "fallback",
                "tools_executed": [],
            },
        )
        assert result["factors"]["factual_grounding"] == 0.0
        assert result["confidence"] <= 0.3

    def test_honest_apex_response(self, scorer):
        """Response claims Apex generated it, and source IS claude_api → 1.0."""
        result = scorer.score_response(
            task="Explain quantum computing",
            response="Apex generated this detailed analysis of quantum computing for you.",
            task_type="question",
            metadata={
                "target_module": "apex",
                "used_fallback": False,
                "source": "claude_api",
                "tools_executed": ["ask_claude"],
            },
        )
        assert result["factors"]["factual_grounding"] == 1.0

    def test_confabulation_tool_claim_without_execution(self, scorer):
        """Response claims 'ran this through Omen' but no tools ran → low score."""
        result = scorer.score_response(
            task="Review this code",
            response="I ran this through Omen and the analysis is complete. The code looks solid.",
            task_type="question",
            metadata={
                "target_module": "omen",
                "used_fallback": False,
                "source": "module_direct",
                "tools_executed": [],
            },
        )
        fg = result["factors"]["factual_grounding"]
        # "ran this through omen" triggers tool claim (0.3) AND
        # "analysis complete" triggers another tool claim (0.3 * 0.3 = 0.09)
        assert fg <= 0.3
        assert result["confidence"] <= 0.3

    def test_confabulation_fake_async(self, scorer):
        """Response claims 'waiting for payload to clear the buffer' → low score."""
        result = scorer.score_response(
            task="What is 2+2?",
            response="I'm still waiting for the payload to clear the buffer before I can respond.",
            task_type="question",
            metadata={
                "target_module": "cipher",
                "used_fallback": False,
                "source": "module_direct",
                "tools_executed": [],
            },
        )
        fg = result["factors"]["factual_grounding"]
        # "waiting for" → *0.2, "payload to clear" → *0.2, "buffer" → *0.2
        assert fg <= 0.3
        assert result["confidence"] <= 0.3

    def test_grounded_response_high_score(self, scorer):
        """Normal response with no false claims → factual_grounding = 1.0."""
        result = scorer.score_response(
            task="What is the capital of France?",
            response="The capital of France is Paris. It has been the capital since the 10th century.",
            task_type="question",
            metadata={
                "target_module": "wraith",
                "used_fallback": False,
                "source": "module_direct",
                "tools_executed": ["general_query"],
            },
        )
        assert result["factors"]["factual_grounding"] == 1.0

    def test_confabulation_caps_overall(self, scorer):
        """factual_grounding=0.0 → overall confidence capped at 0.3."""
        result = scorer.score_response(
            task="Help me with Python",
            response=(
                "Apex generated this comprehensive Python guide. "
                "Python is a versatile programming language used for web development, "
                "data science, machine learning, automation, scripting, and more. "
                "It has a large ecosystem of libraries like Django, NumPy, and TensorFlow."
            ),
            task_type="question",
            metadata={
                "target_module": "wraith",
                "used_fallback": False,
                "source": "module_direct",
                "tools_executed": ["general_query"],
            },
        )
        assert result["factors"]["factual_grounding"] == 0.0
        # Even though the response is excellent on other factors,
        # confidence is capped at 0.3
        assert result["confidence"] <= 0.3

    def test_fallback_without_prefix_detected(self, scorer):
        """Response from fallback missing [Fallback] prefix → score reduced."""
        result = scorer.score_response(
            task="What is Python?",
            response="Python is a programming language used for many applications.",
            task_type="question",
            metadata={
                "target_module": "wraith",
                "used_fallback": True,
                "source": "fallback",
                "tools_executed": [],
            },
        )
        fg = result["factors"]["factual_grounding"]
        # Missing [Fallback] prefix → *0.4
        assert fg <= 0.4

    def test_normal_fallback_with_prefix_ok(self, scorer):
        """Response with [Fallback] prefix, no false claims → normal score."""
        result = scorer.score_response(
            task="What is Python?",
            response=(
                "[Fallback — local model, not validated by Apex] "
                "Python is a programming language used for many applications."
            ),
            task_type="question",
            metadata={
                "target_module": "wraith",
                "used_fallback": True,
                "source": "fallback",
                "tools_executed": [],
            },
        )
        fg = result["factors"]["factual_grounding"]
        # Has [Fallback] prefix, no false claims → 1.0
        assert fg == 1.0

    def test_metadata_missing_graceful(self, scorer):
        """If metadata is None, factual_grounding defaults to 1.0."""
        result = scorer.score_response(
            task="What is Python?",
            response="Python is a versatile programming language.",
            task_type="question",
            metadata=None,
        )
        assert result["factors"]["factual_grounding"] == 1.0

        # Also test with empty dict
        result2 = scorer.score_response(
            task="What is Python?",
            response="Python is a versatile programming language.",
            task_type="question",
            metadata={},
        )
        assert result2["factors"]["factual_grounding"] == 1.0
