"""
Tests for CrossModuleDreamer — Cross-Module Capability Discovery.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from modules.morpheus.cross_module_dreaming import (
    CrossModuleDreamer,
    MODULE_DESCRIPTIONS,
    DREAM_PROMPT_TEMPLATE,
)


# --- Fixtures ---

def make_generate_fn(response):
    """Create a mock generate_fn returning the given response."""
    def generate_fn(prompt):
        return response
    return generate_fn


def make_json_response(hypotheses):
    """Create a JSON string from a list of hypothesis dicts."""
    return json.dumps(hypotheses)


SAMPLE_HYPOTHESES = [
    {
        "title": "Security-aware code generation",
        "description": "Sentinel's threat models inform Omen's code scaffolding to produce hardened code by default",
        "testable": True,
        "potential_value": "high",
    },
    {
        "title": "Vulnerability pattern learning",
        "description": "Omen's failure learning database feeds Sentinel's scanning rules",
        "testable": True,
        "potential_value": "medium",
    },
]


@pytest.fixture
def mock_experiment_store():
    """Mock ExperimentStore that records calls."""
    store = MagicMock()
    store.store_failure.return_value = "exp-123-mock"
    return store


@pytest.fixture
def dreamer_with_generate():
    """CrossModuleDreamer with a working generate_fn."""
    gen_fn = make_generate_fn(make_json_response(SAMPLE_HYPOTHESES))
    return CrossModuleDreamer(generate_fn=gen_fn)


@pytest.fixture
def dreamer_no_generate():
    """CrossModuleDreamer without generate_fn."""
    return CrossModuleDreamer()


@pytest.fixture
def dreamer_with_store(mock_experiment_store):
    """CrossModuleDreamer with experiment_store."""
    gen_fn = make_generate_fn(make_json_response(SAMPLE_HYPOTHESES))
    return CrossModuleDreamer(generate_fn=gen_fn, experiment_store=mock_experiment_store)


# --- dream() tests ---

class TestDream:
    """Tests for the dream() method."""

    def test_dream_generates_hypotheses(self, dreamer_with_generate):
        """dream() should return hypothesis dicts for random module pairs."""
        results = dreamer_with_generate.dream(max_combinations=1)
        assert len(results) > 0
        for r in results:
            assert "module_a" in r
            assert "module_b" in r
            assert "hypothesis" in r
            assert "potential_value" in r
            assert "testable" in r
            assert r["module_a"] in MODULE_DESCRIPTIONS
            assert r["module_b"] in MODULE_DESCRIPTIONS
            assert r["module_a"] != r["module_b"]

    def test_dream_respects_max_combinations(self, dreamer_with_generate):
        """dream() should not exceed max_combinations pairs."""
        results_1 = dreamer_with_generate.dream(max_combinations=1)
        # All results should come from exactly 1 module pair
        pairs = {(r["module_a"], r["module_b"]) for r in results_1}
        assert len(pairs) == 1

    def test_dream_with_max_combinations_3(self):
        """dream() with max_combinations=3 explores up to 3 pairs."""
        gen_fn = make_generate_fn(make_json_response([SAMPLE_HYPOTHESES[0]]))
        dreamer = CrossModuleDreamer(generate_fn=gen_fn)
        results = dreamer.dream(max_combinations=3)
        pairs = {(r["module_a"], r["module_b"]) for r in results}
        assert len(pairs) <= 3

    def test_dream_no_generate_fn_returns_empty(self, dreamer_no_generate):
        """dream() without generate_fn should return empty results."""
        results = dreamer_no_generate.dream(max_combinations=3)
        assert results == []

    def test_dream_same_pair_not_dreamed_twice(self):
        """Same module pair should not be explored twice in a session."""
        gen_fn = make_generate_fn(make_json_response([SAMPLE_HYPOTHESES[0]]))
        dreamer = CrossModuleDreamer(generate_fn=gen_fn)

        # Dream multiple times — explored pairs should accumulate
        dreamer.dream(max_combinations=2)
        first_explored = len(dreamer._explored_pairs)
        dreamer.dream(max_combinations=2)
        second_explored = len(dreamer._explored_pairs)

        # Should have explored new pairs, not repeated old ones
        assert second_explored > first_explored


# --- get_module_descriptions() tests ---

class TestGetModuleDescriptions:
    """Tests for get_module_descriptions()."""

    def test_returns_post_phase_a_modules(self, dreamer_no_generate):
        """Should return descriptions for all post-Phase-A modules.

        Phase A consolidation: Sentinel → Cerberus, Cipher → Omen,
        Void → daemon.  MODULE_DESCRIPTIONS now has 10 entries
        (active modules + dormant Morpheus)."""
        descriptions = dreamer_no_generate.get_module_descriptions()
        assert len(descriptions) == 10
        expected_modules = {
            "shadow", "wraith", "cerberus", "apex", "grimoire",
            "harbinger", "reaper", "omen",
            "nova", "morpheus",
        }
        assert set(descriptions.keys()) == expected_modules

    def test_uses_custom_registry(self):
        """Should use module_registry when provided."""
        custom = {"alpha": "Module A", "beta": "Module B"}
        dreamer = CrossModuleDreamer(module_registry=custom)
        descriptions = dreamer.get_module_descriptions()
        assert descriptions == custom

    def test_descriptions_are_nonempty_strings(self, dreamer_no_generate):
        """All descriptions should be non-empty strings."""
        for name, desc in dreamer_no_generate.get_module_descriptions().items():
            assert isinstance(desc, str), f"{name} description not a string"
            assert len(desc) > 0, f"{name} description is empty"


# --- evaluate_dream() tests ---

class TestEvaluateDream:
    """Tests for evaluate_dream()."""

    def test_creative_hypothesis_worth_investigating(self, dreamer_no_generate):
        """A creative, non-trivial hypothesis should be worth investigating."""
        dream = {
            "module_a": "sentinel",
            "module_b": "omen",
            "hypothesis": "Security-hardened code generation patterns",
            "description": "Sentinel threat models inform Omen scaffolding for secure defaults",
            "potential_value": "high",
            "testable": True,
        }
        result = dreamer_no_generate.evaluate_dream(dream)
        assert result["worth_investigating"] is True
        assert result["priority"] <= 2  # high value + testable

    def test_trivial_combination_not_worth_it(self, dreamer_no_generate):
        """Trivial data piping should not be worth investigating."""
        dream = {
            "module_a": "reaper",
            "module_b": "grimoire",
            "hypothesis": "Just pass output to grimoire for storage",
            "description": "Send data from reaper and pass output to grimoire",
            "potential_value": "low",
            "testable": False,
        }
        result = dreamer_no_generate.evaluate_dream(dream)
        assert result["worth_investigating"] is False
        assert "trivial" in result["reason"].lower() or "piping" in result["reason"].lower()

    def test_empty_hypothesis_not_worth_it(self, dreamer_no_generate):
        """Empty hypothesis should not be worth investigating."""
        dream = {
            "module_a": "omen",
            "module_b": "nova",
            "hypothesis": "",
            "description": "",
            "potential_value": "medium",
            "testable": False,
        }
        result = dreamer_no_generate.evaluate_dream(dream)
        assert result["worth_investigating"] is False

    def test_restated_capability_not_worth_it(self, dreamer_no_generate):
        """A hypothesis that just restates a module's description isn't novel.
        Phase A: cipher absorbed into omen; use omen's description here."""
        desc = MODULE_DESCRIPTIONS["omen"]
        dream = {
            "module_a": "omen",
            "module_b": "nova",
            "hypothesis": desc,
            "description": desc,
            "potential_value": "medium",
            "testable": False,
        }
        result = dreamer_no_generate.evaluate_dream(dream)
        assert result["worth_investigating"] is False

    def test_testable_dream_gets_priority_boost(self, dreamer_no_generate):
        """Testable dreams should get better (lower) priority."""
        base = {
            "module_a": "void",
            "module_b": "harbinger",
            "hypothesis": "Predictive system health briefings",
            "description": "Void trend data feeds Harbinger alert personalization",
            "potential_value": "medium",
        }
        not_testable = {**base, "testable": False}
        testable = {**base, "testable": True}
        r_not = dreamer_no_generate.evaluate_dream(not_testable)
        r_yes = dreamer_no_generate.evaluate_dream(testable)
        assert r_yes["priority"] < r_not["priority"]


# --- store_dream() tests ---

class TestStoreDream:
    """Tests for store_dream()."""

    def test_store_dream_saves_to_experiment_store(self, dreamer_with_store, mock_experiment_store):
        """store_dream() should call experiment_store.store_failure()."""
        dream = {
            "module_a": "sentinel",
            "module_b": "omen",
            "hypothesis": "Security-hardened code gen",
            "description": "Sentinel informs Omen scaffolding",
            "potential_value": "high",
            "testable": True,
        }
        exp_id = dreamer_with_store.store_dream(dream)
        assert exp_id == "exp-123-mock"
        mock_experiment_store.store_failure.assert_called_once()
        call_kwargs = mock_experiment_store.store_failure.call_args
        assert "cross_module_dream" in call_kwargs.kwargs.get("domain_tags", call_kwargs[1].get("domain_tags", []))

    def test_store_dream_no_store_returns_empty(self, dreamer_no_generate):
        """store_dream() without experiment_store returns empty string."""
        dream = {"module_a": "a", "module_b": "b", "hypothesis": "test"}
        result = dreamer_no_generate.store_dream(dream)
        assert result == ""


# --- get_unexplored_combinations() tests ---

class TestGetUnexploredCombinations:
    """Tests for get_unexplored_combinations()."""

    def test_returns_untried_pairs(self, dreamer_no_generate):
        """Should return all 45 pairs initially (10 choose 2, post-Phase-A)."""
        unexplored = dreamer_no_generate.get_unexplored_combinations()
        assert len(unexplored) == 45  # 10 * 9 / 2 (post-Phase-A)

    def test_shrinks_as_combinations_explored(self):
        """Explored pairs should be excluded from unexplored list."""
        gen_fn = make_generate_fn(make_json_response([SAMPLE_HYPOTHESES[0]]))
        dreamer = CrossModuleDreamer(generate_fn=gen_fn)

        before = len(dreamer.get_unexplored_combinations())
        dreamer.dream(max_combinations=2)
        after = len(dreamer.get_unexplored_combinations())

        assert after == before - 2

    def test_all_pairs_are_unique_tuples(self, dreamer_no_generate):
        """All returned pairs should be unique sorted tuples."""
        unexplored = dreamer_no_generate.get_unexplored_combinations()
        seen = set()
        for a, b in unexplored:
            key = tuple(sorted((a, b)))
            assert key not in seen, f"Duplicate pair: {key}"
            assert a != b, f"Self-pair: {a}"
            seen.add(key)


# --- get_dream_history() tests ---

class TestGetDreamHistory:
    """Tests for get_dream_history()."""

    def test_returns_past_dreams(self):
        """Should return dreams from previous dream() calls."""
        gen_fn = make_generate_fn(make_json_response([SAMPLE_HYPOTHESES[0]]))
        dreamer = CrossModuleDreamer(generate_fn=gen_fn)
        dreamer.dream(max_combinations=1)
        history = dreamer.get_dream_history()
        assert len(history) > 0
        assert "module_a" in history[0]

    def test_respects_limit(self):
        """Should not return more dreams than limit."""
        gen_fn = make_generate_fn(make_json_response([SAMPLE_HYPOTHESES[0]]))
        dreamer = CrossModuleDreamer(generate_fn=gen_fn)
        dreamer.dream(max_combinations=5)
        history = dreamer.get_dream_history(limit=2)
        assert len(history) <= 2

    def test_empty_history_returns_empty(self, dreamer_no_generate):
        """Should return empty list when no dreams have been generated."""
        assert dreamer_no_generate.get_dream_history() == []


# --- get_dreaming_stats() tests ---

class TestGetDreamingStats:
    """Tests for get_dreaming_stats()."""

    def test_returns_valid_counts(self):
        """Stats should have correct keys and non-negative values."""
        gen_fn = make_generate_fn(make_json_response([SAMPLE_HYPOTHESES[0]]))
        dreamer = CrossModuleDreamer(generate_fn=gen_fn)
        dreamer.dream(max_combinations=2)
        stats = dreamer.get_dreaming_stats()
        assert "combinations_explored" in stats
        assert "total_dreams" in stats
        assert "validated_dreams" in stats
        assert "unexplored_pairs" in stats
        assert stats["combinations_explored"] == 2
        assert stats["total_dreams"] >= 2
        assert stats["unexplored_pairs"] == 43  # 45 - 2 (post-Phase-A)

    def test_initial_stats(self, dreamer_no_generate):
        """Initial stats should show zero explored, 45 unexplored
        (post-Phase-A: 10 modules → C(10,2) = 45 pairs)."""
        stats = dreamer_no_generate.get_dreaming_stats()
        assert stats["combinations_explored"] == 0
        assert stats["total_dreams"] == 0
        assert stats["validated_dreams"] == 0
        assert stats["unexplored_pairs"] == 45


# --- Edge cases ---

class TestEdgeCases:
    """Edge case and error handling tests."""

    def test_empty_module_registry_graceful(self):
        """Empty module registry should return empty results."""
        dreamer = CrossModuleDreamer(
            generate_fn=make_generate_fn("[]"),
            module_registry={},
        )
        results = dreamer.dream(max_combinations=3)
        assert results == []
        assert dreamer.get_unexplored_combinations() == []

    def test_single_module_registry_no_pairs(self):
        """Single module registry can't make pairs."""
        dreamer = CrossModuleDreamer(
            generate_fn=make_generate_fn("[]"),
            module_registry={"only_one": "Single module"},
        )
        results = dreamer.dream(max_combinations=3)
        assert results == []

    def test_generate_fn_failure_partial_results(self):
        """If generate_fn raises, that pair produces no hypotheses but doesn't crash."""
        call_count = 0

        def flaky_generate(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("LLM timeout")
            return make_json_response([SAMPLE_HYPOTHESES[0]])

        dreamer = CrossModuleDreamer(generate_fn=flaky_generate)
        # With 2 combinations, one may fail and one may succeed
        results = dreamer.dream(max_combinations=2)
        # Should not raise — just partial results
        # At least one pair's hypotheses (or none if the first one failed)
        assert isinstance(results, list)

    def test_generate_fn_returns_garbage(self):
        """Non-JSON response should be handled gracefully."""
        gen_fn = make_generate_fn("This is not JSON at all, just rambling text.")
        dreamer = CrossModuleDreamer(generate_fn=gen_fn)
        results = dreamer.dream(max_combinations=1)
        # Should still produce results (fallback parsing)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_generate_fn_returns_empty(self):
        """Empty response from generate_fn should produce empty results for that pair."""
        gen_fn = make_generate_fn("")
        dreamer = CrossModuleDreamer(generate_fn=gen_fn)
        results = dreamer.dream(max_combinations=1)
        assert results == []
