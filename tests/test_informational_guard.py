"""
Tests for informational guard on fast-path classification.

Knowledge/advice questions should NOT fast-path to action modules.
Action commands should still fast-path normally.
"""

import pytest
from pathlib import Path
from modules.shadow.orchestrator import Orchestrator, TaskType


TEST_CONFIG = {
    "system": {"state_file": ""},
    "models": {
        "ollama_base_url": "http://localhost:11434",
        "router": {"name": "phi4-mini"},
        "fast_brain": {"name": "phi4-mini"},
        "smart_brain": {"name": "phi4-mini"},
    },
    "decision_loop": {
        "context_memories": 3,
    },
}


@pytest.fixture
def config(tmp_path: Path):
    cfg = dict(TEST_CONFIG)
    cfg["system"] = {"state_file": str(tmp_path / "state.json")}
    return cfg


@pytest.fixture
def orch(config):
    return Orchestrator(config)


class TestInformationalGuardOmen:
    """Omen stems ('program', 'code', etc.) should skip fast-path
    when the query is informational."""

    def test_programming_knowledge_question(self, orch):
        result = orch._fast_path_classify(
            "What programming language was created by Guido van Rossum?"
        )
        assert result is None or result.target_module != "omen"

    def test_http_status_code_question(self, orch):
        result = orch._fast_path_classify(
            "What does HTTP status code 404 mean?"
        )
        assert result is None or result.target_module != "omen"

    def test_what_is_a_function(self, orch):
        result = orch._fast_path_classify("What is a function in Python?")
        assert result is None or result.target_module != "omen"

    def test_explain_coding_concept(self, orch):
        result = orch._fast_path_classify(
            "Explain what object-oriented programming is"
        )
        assert result is None or result.target_module != "omen"

    # --- Regression: action commands still fast-path to Omen ---

    def test_write_function_still_fast_paths(self, orch):
        result = orch._fast_path_classify("write a Python function to sort a list")
        assert result is not None
        assert result.target_module == "omen"

    def test_debug_this_code_still_fast_paths(self, orch):
        result = orch._fast_path_classify("debug this code")
        assert result is not None
        assert result.target_module == "omen"

    def test_refactor_script_still_fast_paths(self, orch):
        result = orch._fast_path_classify("refactor this script for readability")
        assert result is not None
        assert result.target_module == "omen"

    def test_lint_my_code_still_fast_paths(self, orch):
        result = orch._fast_path_classify("lint my Python code")
        assert result is not None
        assert result.target_module == "omen"


class TestInformationalGuardCipher:
    """Phase A: Cipher → Omen merge.  The Priority 5 stem block
    (calculate/solve/math/differenc/price/total/logic/puzzle/...) was
    DELETED, not migrated to Omen, to fix the S41 over-matching bug.
    Math-keyword PROSE no longer fast-paths anywhere — neither cipher
    (gone) nor omen.  Numeric EXPRESSIONS still fast-path, but to omen
    (Priority 1, retargeted)."""

    def test_difference_knowledge_question(self, orch):
        result = orch._fast_path_classify(
            "What is the difference between TCP and UDP?"
        )
        # Must not hijack to cipher (gone) or omen (would recreate the bug).
        assert result is None or result.target_module not in ("cipher", "omen")

    def test_pricing_advice_question(self, orch):
        result = orch._fast_path_classify(
            "How should I price a weekly mowing job for a 10,000 sq ft lawn?"
        )
        assert result is None or result.target_module not in ("cipher", "omen")

    def test_what_is_total_price(self, orch):
        result = orch._fast_path_classify(
            "What is the total price for the job?"
        )
        assert result is None or result.target_module not in ("cipher", "omen")

    def test_comparison_knowledge_question(self, orch):
        result = orch._fast_path_classify(
            "What is the difference between a stack and a queue?"
        )
        assert result is None or result.target_module not in ("cipher", "omen")

    # --- Regression: math-keyword prose no longer fast-paths ---

    def test_calculate_keyword_no_longer_fast_paths(self, orch):
        """Pre-merge: 'calculate' stem matched Priority 5 → cipher.
        Post-merge: stem block deleted, no fast-path."""
        result = orch._fast_path_classify(
            "calculate the cost of 3 yards of mulch at $45 each"
        )
        assert result is None or result.target_module not in ("cipher", "omen")

    def test_numeric_expression_routes_to_omen(self, orch):
        """Priority 1 math regex still fires; target retargeted to omen."""
        result = orch._fast_path_classify("what is 17 + 9")
        assert result is not None
        assert result.target_module == "omen"

    def test_numeric_expression_with_multiply_routes_to_omen(self, orch):
        result = orch._fast_path_classify("347 × 892")
        assert result is not None
        assert result.target_module == "omen"

    def test_solve_equation_no_longer_fast_paths(self, orch):
        """'solve' stem block deleted; no fast-path on stem alone.
        '2x + 5 = 15' has 'x' between digits which the regex would
        match — but here the actual digit-op-digit sequence in the
        Priority 1 regex doesn't fire on '2x + 5' (x isn't an
        operator alone — the regex is `\\d+\\s*[+\\-*/×÷xX^%]\\s*\\d+`,
        so 2x+5 matches; but the equation form is preserved as
        intent).  Test the broader case: solve-stem prose without
        a clean numeric expression doesn't fast-path."""
        result = orch._fast_path_classify(
            "solve this puzzle about logic and balance scales"
        )
        assert result is None or result.target_module not in ("cipher", "omen")

    def test_factorial_no_longer_fast_paths(self, orch):
        """'factorial' stem deleted; word-only prose flows to LLM router."""
        result = orch._fast_path_classify("what is the factorial of 10")
        assert result is None or result.target_module not in ("cipher", "omen")

    def test_logic_puzzle_no_longer_fast_paths(self, orch):
        """'logic'/'puzzle'/'solve' stems deleted.  Ambiguous prose
        without a numeric expression no longer fast-paths."""
        result = orch._fast_path_classify(
            "solve this logic puzzle about 8 balls and a balance scale"
        )
        assert result is None or result.target_module not in ("cipher", "omen")


class TestInformationalGuardReaper:
    """Reaper stem 'search' should skip fast-path when informational.
    Explicit search commands ('search for', 'look up') should still
    fast-path."""

    def test_time_complexity_question(self, orch):
        result = orch._fast_path_classify(
            "What is the time complexity of binary search?"
        )
        assert result is None or result.target_module != "reaper"

    def test_search_algorithm_question(self, orch):
        result = orch._fast_path_classify(
            "How does a search engine work?"
        )
        assert result is None or result.target_module != "reaper"

    # --- Regression: explicit search commands still fast-path ---

    def test_search_for_still_fast_paths(self, orch):
        result = orch._fast_path_classify("search for Python tutorials")
        assert result is not None
        assert result.target_module == "reaper"

    def test_look_up_still_fast_paths(self, orch):
        result = orch._fast_path_classify("look up the best mulch for flower beds")
        assert result is not None
        assert result.target_module == "reaper"

    def test_research_still_fast_paths(self, orch):
        result = orch._fast_path_classify("research landscaping trends in Alabama")
        assert result is not None
        assert result.target_module == "reaper"
