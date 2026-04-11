"""Tests for Shadow Teaching Shadow — zero-cost knowledge accumulation."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
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
    grimoire.remember = MagicMock(side_effect=lambda **kwargs: f"id_{kwargs.get('metadata', {}).get('tier', 'x')}")
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

    def test_reasoning_steps_accepted_without_error(self, teacher, hard_code_task):
        """reasoning_steps parameter is accepted (not used in prompt to keep it simple)."""
        result = teacher.generate_teaching(
            hard_code_task,
            solution="result",
            reasoning_steps=["step1", "step2"],
        )
        assert result["raw_teaching"] != ""

    def test_graceful_when_generate_fn_fails(self, teacher, hard_code_task):
        teacher._generate_fn.side_effect = RuntimeError("model crashed")
        result = teacher.generate_teaching(hard_code_task, solution="x")
        assert result["raw_teaching"] == ""
        assert result["tiers"]["specific_solution"] == ""

    def test_graceful_when_generate_fn_is_none(self, hard_code_task):
        teacher = SelfTeacher(generate_fn=None)
        result = teacher.generate_teaching(hard_code_task, solution="x")
        assert result["raw_teaching"] == ""

    def test_teaching_prompt_not_empty_and_under_limit(self, teacher, hard_code_task):
        """The prompt sent to generate_fn must be a non-empty string under 2000 chars."""
        teacher.generate_teaching(hard_code_task, solution="Use Floyd's algorithm")
        prompt = teacher._generate_fn.call_args[0][0]
        assert isinstance(prompt, str)
        assert 0 < len(prompt) < 2000

    def test_teaching_prompt_simplified(self, teacher, hard_code_task):
        """The prompt should not require complex XML formatting from the model."""
        teacher.generate_teaching(hard_code_task, solution="Use Floyd's algorithm")
        prompt = teacher._generate_fn.call_args[0][0]
        # Should NOT contain XML tags that local models struggle with
        assert "<specific_solution>" not in prompt
        assert "<general_principle>" not in prompt
        assert "<meta_principle>" not in prompt

    def test_empty_response_retries(self, hard_code_task):
        """When generate_fn returns empty, it should retry once with a simpler prompt."""
        gen_fn = MagicMock(side_effect=["", "Lesson: use hash maps for O(1) lookup."])
        teacher = SelfTeacher(generate_fn=gen_fn)
        result = teacher.generate_teaching(hard_code_task, solution="hash map")
        assert gen_fn.call_count == 2
        assert result["raw_teaching"] == "Lesson: use hash maps for O(1) lookup."
        # Second prompt should be shorter than the first
        first_prompt = gen_fn.call_args_list[0][0][0]
        retry_prompt = gen_fn.call_args_list[1][0][0]
        assert len(retry_prompt) < len(first_prompt)

    def test_empty_response_both_attempts_returns_empty(self, hard_code_task):
        """When both attempts return empty, raw_teaching is empty."""
        gen_fn = MagicMock(return_value="")
        teacher = SelfTeacher(generate_fn=gen_fn)
        result = teacher.generate_teaching(hard_code_task, solution="x")
        assert gen_fn.call_count == 2
        assert result["raw_teaching"] == ""

    def test_successful_teaching_stores(self):
        """When generate_fn returns valid text, store_teaching stores it."""
        gen_fn = MagicMock(return_value="1. SOLUTION: Use a hash map.\n2. PRINCIPLE: O(1) lookups.\n3. STRATEGY: Think about access patterns.")
        grimoire = MagicMock()
        grimoire.remember = MagicMock(return_value="stored-id")
        teacher = SelfTeacher(generate_fn=gen_fn, grimoire=grimoire)
        teaching = teacher.generate_teaching(
            task={"description": "Optimize lookup performance", "type": "code", "difficulty": 7},
            solution="Use a hash map",
        )
        ids = teacher.store_teaching(teaching)
        assert len(ids) >= 1
        grimoire.remember.assert_called()

    def test_extract_tiers_from_numbered_paragraphs(self):
        """_extract_tiers handles numbered paragraph format."""
        teacher = SelfTeacher()
        raw = (
            "1. SOLUTION: Use binary search.\n"
            "2. PRINCIPLE: Divide and conquer.\n"
            "3. STRATEGY: Check if input is sorted first."
        )
        tiers = teacher._extract_tiers(raw)
        assert "binary search" in tiers["specific_solution"].lower()
        assert "divide" in tiers["general_principle"].lower()
        assert "sorted" in tiers["meta_principle"].lower()

    def test_extract_tiers_fallback_whole_response(self):
        """When model returns plain text without structure, store as specific_solution."""
        teacher = SelfTeacher()
        raw = "The key lesson is to always validate input before processing."
        tiers = teacher._extract_tiers(raw)
        assert tiers["specific_solution"] == raw
        assert tiers["general_principle"] == ""
        assert tiers["meta_principle"] == ""

    def test_extract_tiers_xml_still_works(self):
        """XML-tagged output still works for backward compatibility."""
        teacher = SelfTeacher()
        raw = (
            "<specific_solution>Use a hash map.</specific_solution>"
            "<general_principle>O(1) lookups.</general_principle>"
            "<meta_principle>Access patterns first.</meta_principle>"
        )
        tiers = teacher._extract_tiers(raw)
        assert tiers["specific_solution"] == "Use a hash map."
        assert tiers["general_principle"] == "O(1) lookups."
        assert tiers["meta_principle"] == "Access patterns first."

    def test_long_inputs_truncated_in_prompt(self):
        """Long task descriptions and solutions are truncated to keep prompt short."""
        gen_fn = MagicMock(return_value="Lesson learned.")
        teacher = SelfTeacher(generate_fn=gen_fn)
        long_desc = "x " * 500  # 1000 chars
        long_solution = "y " * 500
        teacher.generate_teaching(
            task={"description": long_desc, "type": "code"},
            solution=long_solution,
        )
        prompt = gen_fn.call_args_list[0][0][0]
        assert len(prompt) < 2000


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
        for call in teacher._grimoire.remember.call_args_list:
            kwargs = call[1]
            assert kwargs["trust_level"] == 0.5
            assert kwargs["source"] == "self_teaching"

    def test_metadata_includes_self_teaching_source(self, teacher):
        teaching = {
            "tiers": {"specific_solution": "x", "general_principle": "", "meta_principle": ""},
            "task_hash": "h",
            "domain_tags": [],
            "generated_at": 0,
            "source": "self_teaching",
        }
        teacher.store_teaching(teaching)
        call_kwargs = teacher._grimoire.remember.call_args[1]
        assert call_kwargs["category"] == "self_teaching"

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
        grimoire.remember = MagicMock(return_value="fallback_id")
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


# ── Test: GrimoireModule unwrapping in SelfTeacher ────────────────────

class TestGrimoireModuleUnwrap:
    """SelfTeacher should unwrap a GrimoireModule adapter to access the
    inner Grimoire instance that has the .remember() method."""

    def test_unwraps_grimoire_module_at_init(self):
        """If passed an object without .remember() but with ._grimoire,
        SelfTeacher should use the inner object."""
        inner_grimoire = MagicMock()
        inner_grimoire.remember = MagicMock(return_value="doc-1")

        # Simulate GrimoireModule: has ._grimoire but no .remember()
        class FakeGrimoireModule:
            pass

        wrapper = FakeGrimoireModule()
        wrapper._grimoire = inner_grimoire

        teacher = SelfTeacher(grimoire=wrapper)
        assert teacher._grimoire is inner_grimoire

    def test_keeps_real_grimoire_as_is(self):
        """If passed an object that already has .remember(), use it directly."""
        grimoire = MagicMock()
        grimoire.remember = MagicMock(return_value="doc-1")

        teacher = SelfTeacher(grimoire=grimoire)
        assert teacher._grimoire is grimoire


# ── Integration tests: SelfTeacher → real Grimoire storage ─────────────

class TestStoreTeachingIntegration:
    """End-to-end tests: generate_fn produces content → store_teaching()
    persists in a real Grimoire (SQLite + ChromaDB in tmp dir) → recall works."""

    @pytest.fixture
    def real_grimoire(self, tmp_path):
        """Create a real Grimoire instance backed by SQLite + ChromaDB in a temp dir."""
        from modules.grimoire.grimoire import Grimoire

        db_path = str(tmp_path / "test_memory.db")
        vector_dir = str(tmp_path / "vectors")
        os.makedirs(vector_dir, exist_ok=True)

        grimoire = Grimoire(
            db_path=db_path,
            vector_path=vector_dir,
        )
        return grimoire

    @pytest.fixture
    def teaching_payload(self):
        """A valid teaching dict as generate_teaching() would produce."""
        return {
            "raw_teaching": (
                "<specific_solution>Use Floyd's tortoise-hare algorithm.</specific_solution>"
                "<general_principle>Two-pointer techniques solve cycle detection in O(1) space.</general_principle>"
                "<meta_principle>Consider space-time tradeoffs before reaching for hash sets.</meta_principle>"
            ),
            "tiers": {
                "specific_solution": "Use Floyd's tortoise-hare algorithm.",
                "general_principle": "Two-pointer techniques solve cycle detection in O(1) space.",
                "meta_principle": "Consider space-time tradeoffs before reaching for hash sets.",
            },
            "task_hash": "abc123deadbeef",
            "domain_tags": ["code", "algorithms"],
            "generated_at": time.time(),
            "source": "self_teaching",
        }

    def test_store_teaching_succeeds(self, real_grimoire, teaching_payload):
        """store_teaching() with a real Grimoire returns non-empty ID list."""
        teacher = SelfTeacher(grimoire=real_grimoire)
        ids = teacher.store_teaching(teaching_payload)
        assert len(ids) == 3
        for mid in ids:
            assert mid is not None
            assert isinstance(mid, str)
            assert len(mid) > 0

    def test_store_teaching_content_valid(self, real_grimoire, teaching_payload):
        """Content passed to remember() is a non-empty string for each tier."""
        teacher = SelfTeacher(grimoire=real_grimoire)
        ids = teacher.store_teaching(teaching_payload)
        assert len(ids) == 3  # All 3 tiers had non-empty content

    def test_store_teaching_category_valid(self, real_grimoire, teaching_payload):
        """Category stored in Grimoire is the expected 'self_teaching' string."""
        teacher = SelfTeacher(grimoire=real_grimoire)
        ids = teacher.store_teaching(teaching_payload)
        # Verify via direct DB query that category is correct
        import sqlite3
        db_path = str(real_grimoire.db_path)
        conn = sqlite3.connect(db_path)
        for mid in ids:
            row = conn.execute(
                "SELECT category FROM memories WHERE id = ?", (mid,)
            ).fetchone()
            assert row is not None, f"Memory {mid} not found in DB"
            assert row[0] == "self_teaching"
        conn.close()

    def test_store_teaching_returns_ids(self, real_grimoire, teaching_payload):
        """store_teaching() returns a list of string memory IDs."""
        teacher = SelfTeacher(grimoire=real_grimoire)
        ids = teacher.store_teaching(teaching_payload)
        assert isinstance(ids, list)
        assert all(isinstance(i, str) for i in ids)
        assert len(ids) > 0

    def test_teaching_persists_in_db(self, real_grimoire, teaching_payload):
        """After store_teaching(), Grimoire.recall() can find the memories."""
        teacher = SelfTeacher(grimoire=real_grimoire)
        ids = teacher.store_teaching(teaching_payload)
        assert len(ids) > 0

        # recall() should find at least one of the stored teachings
        results = real_grimoire.recall("Floyd's tortoise-hare algorithm", n_results=5)
        assert len(results) > 0
        # At least one result should match our stored content
        found = any(
            "Floyd" in (r.get("content", "") if isinstance(r, dict) else str(r))
            for r in results
        )
        assert found, f"Expected to find Floyd's algorithm in recall results: {results}"

    def test_generate_fn_none_produces_empty_tiers(self):
        """When generate_fn is None, all tiers are empty → 0 stored."""
        grimoire = MagicMock()
        grimoire.remember = MagicMock(return_value="id-1")
        teacher = SelfTeacher(generate_fn=None, grimoire=grimoire)
        teaching = teacher.generate_teaching(
            task={"description": "complex task", "type": "code"},
            solution="the solution",
        )
        # All tiers should be empty since generate_fn is None
        for tier_content in teaching["tiers"].values():
            assert tier_content == ""
        # store_teaching should store nothing (all tiers empty)
        ids = teacher.store_teaching(teaching)
        assert ids == []
        grimoire.remember.assert_not_called()

    def test_full_pipeline_with_real_grimoire(self, real_grimoire):
        """End-to-end: generate_fn → generate_teaching → store_teaching → recall."""
        gen_fn = MagicMock(return_value=(
            "<specific_solution>Use binary search for sorted arrays.</specific_solution>"
            "<general_principle>Divide and conquer reduces O(n) to O(log n).</general_principle>"
            "<meta_principle>Always check if input is sorted before choosing algorithm.</meta_principle>"
        ))
        teacher = SelfTeacher(
            generate_fn=gen_fn,
            grimoire=real_grimoire,
            config={"difficulty_threshold": 1, "confidence_threshold": 0.1},
        )
        result = teacher.teach_from_success(
            task={
                "description": "Implement efficient search in a sorted array with edge case handling",
                "type": "code",
                "difficulty": 8,
            },
            solution="Use binary search with boundary checks",
            confidence_score=0.95,
            was_escalated=False,
        )
        assert result is not None
        assert len(result["stored_ids"]) == 3
        # Verify persistence
        results = real_grimoire.recall("binary search sorted", n_results=5)
        assert len(results) > 0
