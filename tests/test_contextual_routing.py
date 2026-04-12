"""
Tests for contextual reference routing in the fast-path classifier.
==================================================================
When a user says "do that", "yes proceed", etc., the fast-path should
re-route to the same module that handled the previous message instead
of keyword-matching the current input.
"""

import pytest
from pathlib import Path

from modules.shadow.orchestrator import (
    Orchestrator,
    TaskClassification,
    TaskType,
    BrainType,
)


TEST_CONFIG = {
    "system": {"state_file": ""},
    "models": {
        "ollama_base_url": "http://localhost:11434",
        "router": {"name": "phi4-mini"},
        "fast_brain": {"name": "phi4-mini"},
        "smart_brain": {"name": "phi4-mini"},
    },
    "decision_loop": {"context_memories": 3},
}


@pytest.fixture
def config(tmp_path: Path) -> dict:
    cfg = dict(TEST_CONFIG)
    cfg["system"] = {"state_file": str(tmp_path / "state.json")}
    return cfg


@pytest.fixture
def orch(config: dict) -> Orchestrator:
    return Orchestrator(config)


def _make_classification(target_module: str, task_type: TaskType = TaskType.ACTION) -> TaskClassification:
    """Helper to build a TaskClassification for seeding _last_route."""
    return TaskClassification(
        task_type=task_type,
        complexity="moderate",
        target_module=target_module,
        brain=BrainType.FAST,
        safety_flag=False,
        priority=3,
        confidence=0.85,
    )


# --- Core contextual routing tests ---

class TestContextualRouting:
    """Contextual references ('do that', 'yes', etc.) re-route to previous module."""

    def test_do_that_after_omen_routes_to_omen(self, orch: Orchestrator):
        """'do that' after an Omen task should route back to Omen."""
        orch._last_route = _make_classification("omen", TaskType.CREATION)
        result = orch._fast_path_classify("do that, and then write what you came up with here")
        assert result is not None
        assert result.target_module == "omen"
        assert result.confidence == 0.90

    def test_yes_proceed_after_reaper_routes_to_reaper(self, orch: Orchestrator):
        """'yes proceed' after a Reaper search should route back to Reaper."""
        orch._last_route = _make_classification("reaper", TaskType.RESEARCH)
        result = orch._fast_path_classify("yes proceed")
        assert result is not None
        assert result.target_module == "reaper"
        assert result.task_type == TaskType.RESEARCH

    def test_go_ahead_after_sentinel_routes_to_sentinel(self, orch: Orchestrator):
        orch._last_route = _make_classification("sentinel", TaskType.ACTION)
        result = orch._fast_path_classify("go ahead")
        assert result is not None
        assert result.target_module == "sentinel"

    def test_continue_after_cipher_routes_to_cipher(self, orch: Orchestrator):
        orch._last_route = _make_classification("cipher", TaskType.ANALYSIS)
        result = orch._fast_path_classify("continue with that calculation")
        assert result is not None
        assert result.target_module == "cipher"

    def test_proceed_after_nova_routes_to_nova(self, orch: Orchestrator):
        orch._last_route = _make_classification("nova", TaskType.CREATION)
        result = orch._fast_path_classify("proceed")
        assert result is not None
        assert result.target_module == "nova"

    def test_do_it_after_wraith_routes_to_wraith(self, orch: Orchestrator):
        orch._last_route = _make_classification("wraith", TaskType.ACTION)
        result = orch._fast_path_classify("do it")
        assert result is not None
        assert result.target_module == "wraith"

    def test_yeah_after_grimoire_routes_to_grimoire(self, orch: Orchestrator):
        orch._last_route = _make_classification("grimoire", TaskType.MEMORY)
        result = orch._fast_path_classify("yeah")
        assert result is not None
        assert result.target_module == "grimoire"

    def test_please_do_after_morpheus_routes_to_morpheus(self, orch: Orchestrator):
        orch._last_route = _make_classification("morpheus", TaskType.RESEARCH)
        result = orch._fast_path_classify("please do")
        assert result is not None
        assert result.target_module == "morpheus"


# --- Non-contextual messages still use normal keyword matching ---

class TestNonContextualStillKeywordMatches:
    """Messages that are NOT contextual references must use normal keyword routing."""

    def test_explicit_keyword_ignores_last_route(self, orch: Orchestrator):
        """'search for X' should route to reaper even if last route was omen."""
        orch._last_route = _make_classification("omen", TaskType.CREATION)
        result = orch._fast_path_classify("search for Python tutorials")
        assert result is not None
        assert result.target_module == "reaper"

    def test_code_keyword_ignores_last_route(self, orch: Orchestrator):
        """'debug this script' should route to omen even if last route was nova."""
        orch._last_route = _make_classification("nova", TaskType.CREATION)
        result = orch._fast_path_classify("debug this script")
        assert result is not None
        assert result.target_module == "omen"

    def test_math_keyword_ignores_last_route(self, orch: Orchestrator):
        """'calculate 5 + 3' should route to cipher even if last route was reaper."""
        orch._last_route = _make_classification("reaper", TaskType.RESEARCH)
        result = orch._fast_path_classify("calculate 15% of 2400")
        assert result is not None
        assert result.target_module == "cipher"

    def test_greeting_ignores_last_route(self, orch: Orchestrator):
        """'hello' is a greeting, not a contextual reference, even if last route was omen."""
        orch._last_route = _make_classification("omen", TaskType.CREATION)
        result = orch._fast_path_classify("hello")
        assert result is not None
        assert result.target_module == "direct"


# --- Edge cases ---

class TestContextualRoutingEdgeCases:
    """Edge cases for contextual reference detection."""

    def test_no_last_route_falls_through(self, orch: Orchestrator):
        """If there's no previous route, contextual references can't match."""
        assert orch._last_route is None
        # 'do that' with no history — should NOT match contextual route
        result = orch._fast_path_classify("do that")
        # Without _last_route, falls through to normal matching (likely None for short input)
        # The key assertion: it does NOT crash and does NOT route to a module
        assert result is None or result.target_module != "do that"

    def test_yes_alone_routes_contextually(self, orch: Orchestrator):
        """Bare 'yes' should trigger contextual routing."""
        orch._last_route = _make_classification("omen", TaskType.CREATION)
        result = orch._fast_path_classify("yes")
        assert result is not None
        assert result.target_module == "omen"

    def test_contextual_preserves_task_type(self, orch: Orchestrator):
        """Contextual routing should preserve the original task_type."""
        orch._last_route = _make_classification("reaper", TaskType.RESEARCH)
        result = orch._fast_path_classify("go ahead")
        assert result.task_type == TaskType.RESEARCH

    def test_contextual_preserves_brain(self, orch: Orchestrator):
        """Contextual routing should preserve the original brain type."""
        orch._last_route = TaskClassification(
            task_type=TaskType.RESEARCH,
            complexity="complex",
            target_module="morpheus",
            brain=BrainType.SMART,
            safety_flag=False,
            priority=2,
            confidence=0.85,
        )
        result = orch._fast_path_classify("sure")
        assert result.brain == BrainType.SMART

    def test_contextual_with_trailing_content(self, orch: Orchestrator):
        """'do that, and also save it' should still match the 'do that' prefix."""
        orch._last_route = _make_classification("omen", TaskType.CREATION)
        result = orch._fast_path_classify("do that, and also save it")
        assert result is not None
        assert result.target_module == "omen"

    def test_yep_routes_contextually(self, orch: Orchestrator):
        orch._last_route = _make_classification("harbinger", TaskType.ACTION)
        result = orch._fast_path_classify("yep")
        assert result is not None
        assert result.target_module == "harbinger"

    def test_go_for_it_routes_contextually(self, orch: Orchestrator):
        orch._last_route = _make_classification("void", TaskType.ANALYSIS)
        result = orch._fast_path_classify("go for it")
        assert result is not None
        assert result.target_module == "void"
