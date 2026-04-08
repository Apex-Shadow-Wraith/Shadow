"""Tests for Shadow Teaching Shadow — zero-cost knowledge accumulation."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from modules.shadow.self_teaching import SelfTeacher


# --- Fixtures ---

@pytest.fixture
def teacher():
    """Basic SelfTeacher with mocked dependencies."""
    gen_fn = MagicMock(return_value=(
        "<specific_solution>Use a hash map.</specific_solution>"
        "<general_principle>Prefer O(1) lookups for repeated access.</general_principle>"
        "<meta_principle>Think about data access patterns first.</meta_principle>"
    ))
    grimoire = MagicMock()
    grimoire.store = MagicMock(side_effect=lambda **kwargs: f"id_{kwargs.get('metadata', {}).get('tier', 'x')}")
    return SelfTeacher(
        generate_fn=gen_fn,
        grimoire=grimoire,
        config={"difficulty_threshold": 5, "confidence_threshold": 0.7},
    )


@pytest.fixture
def hard_code_task():
    """A task that should trigger self-teaching."""
    return {
        "description": "Implement a function that detects cycle in a linked list, then optimize for O(1) space",
        "type": "code",
        "difficulty": 7,
    }


@pytest.fixture
def simple_task():
    """A task too simple to trigger self-teaching."""
    return {
        "description": "Hello",
        "type": "conversation",
        "difficulty": 1,
    }


# --- should_teach tests ---

class TestShouldTeach:
    def test_high_difficulty_high_confidence_no_escalation(self, teacher, hard_code_task):
        assert teacher.should_teach(hard_code_task, confidence_score=0.9, was_escalated=False) is True

    def test_low_difficulty_returns_false(self, teacher):
        task = {"description": "Hi", "type": "code", "difficulty": 2}
        assert teacher.should_teach(task, confidence_score=0.9, was_escalated=False) is False

    def test_low_confidence_returns_false(self, teacher, hard_code_task):
        assert teacher.should_teach(hard_code_task, confidence_score=0.3, was_escalated=False) is False

    def test_confidence_at_threshold_returns_false(self, teacher, hard_code_task):
        """Confidence must be strictly greater than threshold."""
        assert teacher.should_teach(hard_code_task, confidence_score=0.7, was_escalated=False) is False

    def test_was_escalated_returns_false(self, teacher, hard_code_task):
        assert teacher.should_teach(hard_code_task, confidence_score=0.9, was_escalated=True) is False

    def test_simple_task_type_returns_false(self, teacher, simple_task):
        assert teacher.should_teach(simple_task, confidence_score=0.9, was_escalated=False) is False

    def test_routing_type_returns_false(self, teacher):
        task = {"description": "Route to module", "type": "routing", "difficulty": 8}
        assert teacher.should_teach(task, confidence_score=0.9, was_escalated=False) is False

    def test_estimates_difficulty_when_not_provided(self, teacher):
        """When task has no difficulty, estimate_difficulty is used."""
        task = {
            "description": "Implement a recursive algorithm to solve the knapsack problem then optimize with memoization",
            "type": "code",
        }
        # Should be high difficulty due to code keywords + multi-step + length
        assert teacher.should_teach(task, confidence_score=0.9, was_escalated=False) is True


# --- estimate_difficulty tests ---

class TestEstimateDifficulty:
    def test_short_simple_question(self, teacher):
        task = {"description": "Hi there"}
        assert teacher.estimate_difficulty(task) <= 3

    def test_complex_code_task(self, teacher):
        task = {"description": "Implement a distributed consensus algorithm with fault tolerance that handles network partitions and ensures data consistency across multiple nodes"}
        score = teacher.estimate_difficulty(task)
        assert score >= 6

    def test_math_bonus(self, teacher):
        task_no_math = {"description": "Explain the process in detail"}
        task_math = {"description": "Calculate the integral of this equation"}
        score_no_math = teacher.estimate_difficulty(task_no_math)
        score_math = teacher.estimate_difficulty(task_math)
        assert score_math > score_no_math

    def test_capped_at_10(self, teacher):
        task = {
            "description": (
                "Implement a function that computes the algorithm, "
                "then calculate the derivative, then compare results, "
                "then after that finally analyze the output step 1 step 2 step 3"
            ),
        }
        assert teacher.estimate_difficulty(task) == 10

    def test_multistep_indicators_increase_score(self, teacher):
        task_single = {"description": "Write a sorting function for the list"}
        task_multi = {"description": "Write a sorting function then optimize it after that test it finally deploy"}
        score_single = teacher.estimate_difficulty(task_single)
        score_multi = teacher.estimate_difficulty(task_multi)
        assert score_multi > score_single


# --- generate_teaching tests ---

class TestGenerateTeaching:
    def test_calls_generate_fn_with_correct_prompt(self, teacher, hard_code_task):
        teacher.generate_teaching(hard_code_task, solution="Use Floyd's algorithm")
        teacher._generate_fn.assert_called_once()
        prompt = teacher._generate_fn.call_args[0][0]
        assert "Implement a function" in prompt
        assert "Floyd's algorithm" in prompt

    def test_returns_dict_with_all_required_fields(self, teacher, hard_code_task):
        result = teacher.generate_teaching(hard_code_task, solution="solution")
        assert "raw_teaching" in result
        assert "tiers" in result
        assert "task_hash" in result
        assert "domain_tags" in result
        assert "generated_at" in result
        assert result["source"] == "self_teaching"

    def test_tiers_extracted_correctly(self, teacher, hard_code_task):
        result = teacher.generate_teaching(hard_code_task, solution="solution")
        tiers = result["tiers"]
        assert tiers["specific_solution"] == "Use a hash map."
        assert "O(1) lookups" in tiers["general_principle"]
        assert "data access patterns" in tiers["meta_principle"]

    def test_passes_reasoning_steps_in_prompt(self, teacher, hard_code_task):
        teacher.generate_teaching(
            hard_code_task,
            solution="result",
            reasoning_steps=["step1", "step2"],
        )
        prompt = teacher._generate_fn.call_args[0][0]
        assert "step1" in prompt
        assert "step2" in prompt

    def test_graceful_when_generate_fn_fails(self, teacher, hard_code_task):
        teacher._generate_fn.side_effect = RuntimeError("model crashed")
        result = teacher.generate_teaching(hard_code_task, solution="x")
        assert result["raw_teaching"] == ""
        assert result["tiers"]["specific_solution"] == ""

    def test_graceful_when_generate_fn_is_none(self, hard_code_task):
        teacher = SelfTeacher(generate_fn=None)
        result = teacher.generate_teaching(hard_code_task, solution="x")
        assert result["raw_teaching"] == ""


# --- store_teaching tests ---

class TestStoreTeaching:
    def test_stores_in_grimoire_with_trust_level(self, teacher):
        teaching = {
            "tiers": {"specific_solution": "content", "general_principle": "gp", "meta_principle": "mp"},
            "task_hash": "abc123",
            "domain_tags": ["code"],
            "generated_at": time.time(),
            "source": "self_teaching",
        }
        ids = teacher.store_teaching(teaching)
        assert len(ids) == 3
        # Verify trust_level 0.5 in all calls
        for call in teacher._grimoire.store.call_args_list:
            metadata = call[1]["metadata"]
            assert metadata["trust_level"] == 0.5
            assert metadata["source"] == "self_teaching"

    def test_metadata_includes_self_teaching_source(self, teacher):
        teaching = {
            "tiers": {"specific_solution": "x", "general_principle": "", "meta_principle": ""},
            "task_hash": "h",
            "domain_tags": [],
            "generated_at": 0,
            "source": "self_teaching",
        }
        teacher.store_teaching(teaching)
        call_metadata = teacher._grimoire.store.call_args[1]["metadata"]
        assert call_metadata["category"] == "self_teaching"

    def test_uses_teaching_extractor_when_available(self):
        extractor = MagicMock()
        extractor.store_three_tiers = MagicMock(return_value=["id1", "id2", "id3"])
        teacher = SelfTeacher(teaching_extractor=extractor)
        teaching = {
            "tiers": {"specific_solution": "a", "general_principle": "b", "meta_principle": "c"},
            "task_hash": "h",
            "domain_tags": [],
            "generated_at": 0,
        }
        ids = teacher.store_teaching(teaching)
        assert ids == ["id1", "id2", "id3"]
        extractor.store_three_tiers.assert_called_once()

    def test_graceful_when_grimoire_unavailable(self):
        teacher = SelfTeacher()
        teaching = {
            "tiers": {"specific_solution": "a", "general_principle": "b", "meta_principle": "c"},
            "task_hash": "h",
            "domain_tags": [],
            "generated_at": 0,
        }
        ids = teacher.store_teaching(teaching)
        assert ids == []

    def test_graceful_when_teaching_extractor_fails(self):
        extractor = MagicMock()
        extractor.store_three_tiers = MagicMock(side_effect=RuntimeError("boom"))
        grimoire = MagicMock()
        grimoire.store = MagicMock(return_value="fallback_id")
        teacher = SelfTeacher(teaching_extractor=extractor, grimoire=grimoire)
        teaching = {
            "tiers": {"specific_solution": "a", "general_principle": "", "meta_principle": ""},
            "task_hash": "h",
            "domain_tags": [],
            "generated_at": 0,
        }
        ids = teacher.store_teaching(teaching)
        # Falls back to Grimoire
        assert "fallback_id" in ids


# --- teach_from_success tests ---

class TestTeachFromSuccess:
    def test_full_pipeline_when_conditions_met(self, teacher, hard_code_task):
        result = teacher.teach_from_success(
            task=hard_code_task,
            solution="Floyd's cycle detection",
            confidence_score=0.9,
            was_escalated=False,
        )
        assert result is not None
        assert result["source"] == "self_teaching"
        assert "stored_ids" in result

    def test_returns_none_when_conditions_not_met(self, teacher, simple_task):
        result = teacher.teach_from_success(
            task=simple_task,
            solution="Hello!",
            confidence_score=0.9,
            was_escalated=False,
        )
        assert result is None

    def test_graceful_when_generate_fn_fails(self, teacher, hard_code_task):
        teacher._generate_fn.side_effect = RuntimeError("model down")
        result = teacher.teach_from_success(
            task=hard_code_task,
            solution="x",
            confidence_score=0.9,
            was_escalated=False,
        )
        # Should still return a result (with empty raw_teaching), not crash
        assert result is not None
        assert result["raw_teaching"] == ""


# --- Domain tags ---

class TestDomainTags:
    def test_inferred_from_task_type(self, teacher):
        task = {"description": "Explain quantum physics", "type": "research"}
        result = teacher.generate_teaching(task, solution="explanation")
        assert "research" in result["domain_tags"]

    def test_code_keywords_add_code_tag(self, teacher):
        task = {"description": "Implement a function", "type": "code"}
        result = teacher.generate_teaching(task, solution="def foo(): pass")
        assert "code" in result["domain_tags"]

    def test_no_duplicate_tags(self, teacher):
        task = {"description": "Implement a function", "type": "code"}
        result = teacher.generate_teaching(task, solution="def foo(): pass")
        assert len(result["domain_tags"]) == len(set(result["domain_tags"]))
