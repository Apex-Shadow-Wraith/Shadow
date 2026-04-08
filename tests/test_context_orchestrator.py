"""
Tests for ContextOrchestrator — unified context assembly pipeline.

Covers: pipeline, degradation, minimal context, profiling, integration, edge cases.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from modules.shadow.context_orchestrator import ContextOrchestrator, ContextPackage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_context_manager():
    """Mock ContextManager with token estimation and limits."""
    cm = MagicMock()
    cm.effective_limit = 120000
    cm.max_tokens = 128000
    cm.reserve_tokens = 4096
    cm.estimate_tokens = MagicMock(side_effect=lambda text: max(1, len(text) // 4) if text else 0)
    cm.estimate_messages_tokens = MagicMock(
        side_effect=lambda msgs: sum(4 + max(1, len(m.get("content", "")) // 4) for m in msgs) if msgs else 0
    )
    cm.update_model = MagicMock()
    return cm


@pytest.fixture
def mock_compressor():
    """Mock ContextCompressor."""
    comp = MagicMock()
    comp.compress_conversation_history = MagicMock(
        side_effect=lambda history, keep_recent=3: history[-keep_recent:] if len(history) > keep_recent else list(history)
    )
    comp.get_compression_report = MagicMock(return_value={
        "overall_ratio": 0.3,
        "summary": "Compressed 1000 to 700 tokens (30% reduction)",
    })
    return comp


@pytest.fixture
def mock_staged_retrieval():
    """Mock StagedRetrieval."""
    sr = MagicMock()
    sr.search = MagicMock(return_value=[
        {"content": "Full document about Python error handling", "type": "full", "doc_id": "d1", "stage": 2},
        {"content": "Summary of testing patterns", "type": "summary", "doc_id": "d2", "stage": 1, "relevance_score": 0.8},
        {"_stats": {"stage1_count": 5, "stage2_count": 2, "tokens_saved_estimate": 3000}},
    ])
    sr.get_retrieval_stats = MagicMock(return_value={
        "total_searches": 1,
        "avg_stage1_results": 5.0,
        "avg_stage2_pulls": 2.0,
        "avg_token_savings": 3000.0,
        "hit_rate": 0.4,
    })
    return sr


@pytest.fixture
def mock_tool_loader():
    """Mock DynamicToolLoader."""
    tl = MagicMock()
    tl.get_tools_for_task = MagicMock(return_value=[
        {"name": "grimoire_search", "description": "Search memories", "parameters": {}},
        {"name": "send_notification", "description": "Send alert", "parameters": {}},
    ])
    tl.get_core_tools = MagicMock(return_value=[
        {"name": "grimoire_search", "description": "Search memories", "parameters": {}},
    ])
    tl.get_loading_report = MagicMock(return_value={
        "tools_loaded": 2, "tools_available": 120, "tokens_saved": 3000,
        "tokens_loaded": 500, "module_loaded": "wraith",
    })
    return tl


@pytest.fixture
def mock_failure_pattern_db():
    """Mock FailurePatternDB."""
    db = MagicMock()
    db.format_patterns_for_context = MagicMock(return_value=[
        {
            "description": "Task type: math. Mistake: Used simple interest. Correct approach: Use compound formula.",
            "task_type": "math",
            "mistake": "Used simple interest",
            "correct_approach": "Use compound formula",
            "source": "retry_engine",
            "trust_level": 0.5,
        }
    ])
    return db


@pytest.fixture
def mock_grimoire():
    """Mock Grimoire module."""
    grim = MagicMock()
    grim.status = "online"
    return grim


@pytest.fixture
def full_orchestrator(mock_context_manager, mock_compressor, mock_staged_retrieval,
                      mock_tool_loader, mock_failure_pattern_db, mock_grimoire):
    """ContextOrchestrator with all dependencies available."""
    return ContextOrchestrator(
        context_manager=mock_context_manager,
        compressor=mock_compressor,
        staged_retrieval=mock_staged_retrieval,
        tool_loader=mock_tool_loader,
        failure_pattern_db=mock_failure_pattern_db,
        grimoire=mock_grimoire,
    )


@pytest.fixture
def sample_task():
    return {"description": "Calculate compound interest", "type": "math", "module": "cipher"}


@pytest.fixture
def sample_history():
    return [
        {"role": "user", "content": "Hello Shadow"},
        {"role": "assistant", "content": "Hello! How can I help you today?"},
        {"role": "user", "content": "I need help with math"},
        {"role": "assistant", "content": "Sure, what kind of math problem?"},
        {"role": "user", "content": "Compound interest calculation"},
    ]


# ===========================================================================
# Pipeline tests
# ===========================================================================

class TestBuildOptimalContext:
    """Tests for build_optimal_context pipeline."""

    def test_produces_valid_context_package(self, full_orchestrator, sample_task, sample_history):
        """build_optimal_context returns a ContextPackage with all fields populated."""
        pkg = full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
            model="gemma4-26b",
        )

        assert isinstance(pkg, ContextPackage)
        assert pkg.system_prompt == "You are Shadow."
        assert pkg.token_budget > 0
        assert pkg.total_tokens >= 0
        assert isinstance(pkg.token_breakdown, dict)
        assert isinstance(pkg.messages, list)
        assert isinstance(pkg.tool_schemas, list)
        assert isinstance(pkg.trimmed_details, list)
        assert isinstance(pkg.retrieval_stats, dict)
        assert isinstance(pkg.compression_report, dict)

    def test_calls_staged_retrieval(self, full_orchestrator, sample_task,
                                     sample_history, mock_staged_retrieval):
        """Pipeline calls staged retrieval with task description."""
        full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
        )

        mock_staged_retrieval.search.assert_called_once_with(
            query="Calculate compound interest",
            n_results=10,
            auto_select=3,
        )

    def test_calls_failure_pattern_search(self, full_orchestrator, sample_task, sample_history):
        """Pipeline attempts to load failure patterns."""
        pkg = full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
        )
        # Failure patterns loaded (even if empty from sync stub)
        assert isinstance(pkg.failure_patterns, str)

    def test_calls_dynamic_tool_loader(self, full_orchestrator, sample_task,
                                        sample_history, mock_tool_loader):
        """Pipeline calls tool loader with target module."""
        full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
        )

        mock_tool_loader.get_tools_for_task.assert_called_once_with(
            module_name="cipher",
            task=sample_task,
        )

    def test_calls_compressor(self, full_orchestrator, sample_task,
                               sample_history, mock_compressor):
        """Pipeline calls compressor on conversation history."""
        full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
        )

        mock_compressor.compress_conversation_history.assert_called_once()

    def test_respects_token_budget(self, full_orchestrator, sample_task, sample_history):
        """Result total_tokens should not exceed token_budget."""
        pkg = full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
        )

        assert pkg.total_tokens <= pkg.token_budget

    def test_trims_when_over_budget(self, mock_compressor, mock_staged_retrieval,
                                     mock_tool_loader, mock_failure_pattern_db, mock_grimoire):
        """When context exceeds budget, trimming occurs."""
        # Use a tiny budget to force trimming
        tiny_cm = MagicMock()
        tiny_cm.effective_limit = 100  # Very small budget
        tiny_cm.estimate_tokens = MagicMock(side_effect=lambda text: max(1, len(text) // 4) if text else 0)
        tiny_cm.update_model = MagicMock()

        orch = ContextOrchestrator(
            context_manager=tiny_cm,
            compressor=mock_compressor,
            staged_retrieval=mock_staged_retrieval,
            tool_loader=mock_tool_loader,
            failure_pattern_db=mock_failure_pattern_db,
            grimoire=mock_grimoire,
        )

        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test"},
            system_prompt="You are Shadow, the AI agent.",
            conversation_history=[
                {"role": "user", "content": "Hello " * 100},
                {"role": "assistant", "content": "Response " * 100},
            ],
        )

        assert pkg.trimmed is True
        assert len(pkg.trimmed_details) > 0

    def test_system_prompt_never_trimmed(self, mock_compressor, mock_staged_retrieval,
                                          mock_tool_loader, mock_failure_pattern_db, mock_grimoire):
        """System prompt must never be trimmed, even with tiny budget."""
        tiny_cm = MagicMock()
        tiny_cm.effective_limit = 50  # Extremely small
        tiny_cm.estimate_tokens = MagicMock(side_effect=lambda text: max(1, len(text) // 4) if text else 0)
        tiny_cm.update_model = MagicMock()

        orch = ContextOrchestrator(
            context_manager=tiny_cm,
            compressor=mock_compressor,
            staged_retrieval=mock_staged_retrieval,
            tool_loader=mock_tool_loader,
            failure_pattern_db=mock_failure_pattern_db,
            grimoire=mock_grimoire,
        )

        system_prompt = "You are Shadow, the autonomous AI agent system."
        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test"},
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": "big " * 200}],
        )

        assert pkg.system_prompt == system_prompt

    def test_grimoire_context_populated(self, full_orchestrator, sample_task, sample_history):
        """Grimoire context is populated from staged retrieval results."""
        pkg = full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
        )

        assert "Python error handling" in pkg.grimoire_context
        assert "testing patterns" in pkg.grimoire_context

    def test_retrieval_stats_populated(self, full_orchestrator, sample_task, sample_history):
        """Retrieval stats contain staged retrieval metadata."""
        pkg = full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
        )

        assert "total_searches" in pkg.retrieval_stats


# ===========================================================================
# Degradation tests
# ===========================================================================

class TestGracefulDegradation:
    """Tests for graceful degradation when dependencies are missing."""

    def test_all_dependencies_none(self):
        """Works with all dependencies None — returns empty but valid package."""
        orch = ContextOrchestrator()
        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test"},
            system_prompt="You are Shadow.",
            conversation_history=[],
        )

        assert isinstance(pkg, ContextPackage)
        assert pkg.system_prompt == "You are Shadow."
        assert pkg.token_budget > 0
        assert pkg.grimoire_context == ""
        assert pkg.failure_patterns == ""
        assert pkg.tool_schemas == []

    def test_only_context_manager_available(self, mock_context_manager):
        """Works with only ContextManager — token estimation works, rest empty."""
        orch = ContextOrchestrator(context_manager=mock_context_manager)
        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test"},
            system_prompt="You are Shadow.",
            conversation_history=[{"role": "user", "content": "hello"}],
        )

        assert isinstance(pkg, ContextPackage)
        assert pkg.token_budget == 120000
        assert pkg.grimoire_context == ""
        assert pkg.tool_schemas == []
        assert len(pkg.messages) == 1

    def test_only_grimoire_available(self, mock_grimoire, mock_staged_retrieval):
        """Works with only grimoire/staged_retrieval — retrieval works, rest defaults."""
        orch = ContextOrchestrator(
            staged_retrieval=mock_staged_retrieval,
            grimoire=mock_grimoire,
        )
        pkg = orch.build_optimal_context(
            task={"description": "test query", "type": "test"},
            system_prompt="You are Shadow.",
            conversation_history=[],
        )

        assert isinstance(pkg, ContextPackage)
        assert pkg.grimoire_context != ""
        assert pkg.tool_schemas == []

    def test_only_tool_loader_available(self, mock_tool_loader):
        """Works with only tool_loader — tools loaded, rest defaults."""
        orch = ContextOrchestrator(tool_loader=mock_tool_loader)
        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test", "module": "wraith"},
            system_prompt="You are Shadow.",
            conversation_history=[],
        )

        assert isinstance(pkg, ContextPackage)
        assert len(pkg.tool_schemas) == 2
        assert pkg.grimoire_context == ""

    def test_missing_dependency_skips_gracefully(self):
        """Each missing dependency skips its pipeline step without errors."""
        orch = ContextOrchestrator()  # All None
        # Should not raise any exceptions
        pkg = orch.build_optimal_context(
            task={"description": "complex task", "type": "code", "module": "omen"},
            system_prompt="You are Shadow.",
            conversation_history=[
                {"role": "user", "content": "Write code"},
                {"role": "assistant", "content": "Sure, what code?"},
            ],
        )

        assert isinstance(pkg, ContextPackage)
        assert len(pkg.messages) == 2  # History preserved without compressor

    def test_staged_retrieval_exception_handled(self, mock_context_manager):
        """If staged retrieval raises, pipeline continues."""
        bad_sr = MagicMock()
        bad_sr.search = MagicMock(side_effect=RuntimeError("ChromaDB is down"))

        orch = ContextOrchestrator(
            context_manager=mock_context_manager,
            staged_retrieval=bad_sr,
        )

        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test"},
            system_prompt="You are Shadow.",
            conversation_history=[],
        )

        assert isinstance(pkg, ContextPackage)
        assert pkg.grimoire_context == ""

    def test_tool_loader_exception_handled(self, mock_context_manager):
        """If tool loader raises, pipeline continues with empty tools."""
        bad_tl = MagicMock()
        bad_tl.get_tools_for_task = MagicMock(side_effect=RuntimeError("Registry broken"))

        orch = ContextOrchestrator(
            context_manager=mock_context_manager,
            tool_loader=bad_tl,
        )

        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test"},
            system_prompt="You are Shadow.",
            conversation_history=[],
        )

        assert isinstance(pkg, ContextPackage)
        assert pkg.tool_schemas == []

    def test_compressor_exception_handled(self, mock_context_manager):
        """If compressor raises, pipeline continues with raw history."""
        bad_comp = MagicMock()
        bad_comp.compress_conversation_history = MagicMock(
            side_effect=RuntimeError("Compression failed")
        )

        history = [{"role": "user", "content": "hello"}]
        orch = ContextOrchestrator(
            context_manager=mock_context_manager,
            compressor=bad_comp,
        )

        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test"},
            system_prompt="You are Shadow.",
            conversation_history=history,
        )

        assert isinstance(pkg, ContextPackage)
        # Falls back to original history
        assert len(pkg.messages) == 1


# ===========================================================================
# Minimal context tests
# ===========================================================================

class TestBuildMinimalContext:
    """Tests for build_minimal_context."""

    def test_returns_small_context_package(self, full_orchestrator):
        """Minimal context returns a package with no grimoire or failure patterns."""
        pkg = full_orchestrator.build_minimal_context(
            task={"description": "hi", "type": "conversation"},
            system_prompt="You are Shadow.",
        )

        assert isinstance(pkg, ContextPackage)
        assert pkg.grimoire_context == ""
        assert pkg.failure_patterns == ""
        assert pkg.messages == []

    def test_doesnt_call_grimoire(self, full_orchestrator, mock_staged_retrieval):
        """Minimal context doesn't trigger Grimoire search."""
        full_orchestrator.build_minimal_context(
            task={"description": "hi", "type": "conversation"},
            system_prompt="You are Shadow.",
        )

        mock_staged_retrieval.search.assert_not_called()

    def test_doesnt_call_failure_patterns(self, full_orchestrator, mock_failure_pattern_db):
        """Minimal context doesn't search failure patterns."""
        full_orchestrator.build_minimal_context(
            task={"description": "hi", "type": "conversation"},
            system_prompt="You are Shadow.",
        )

        mock_failure_pattern_db.format_patterns_for_context.assert_not_called()

    def test_loads_core_tools_only(self, full_orchestrator, mock_tool_loader):
        """Minimal context loads only core tools."""
        pkg = full_orchestrator.build_minimal_context(
            task={"description": "hi", "type": "conversation"},
            system_prompt="You are Shadow.",
        )

        mock_tool_loader.get_core_tools.assert_called_once()
        assert len(pkg.tool_schemas) == 1  # Only core tool

    def test_no_tool_loader_returns_empty(self):
        """With no tool loader, minimal context has empty tool_schemas."""
        orch = ContextOrchestrator()
        pkg = orch.build_minimal_context(
            task={"description": "hi", "type": "conversation"},
            system_prompt="You are Shadow.",
        )
        assert pkg.tool_schemas == []


# ===========================================================================
# Profiling tests
# ===========================================================================

class TestContextProfile:
    """Tests for get_context_profile and estimate_context_for_task."""

    def test_profile_valid_after_multiple_builds(self, full_orchestrator, sample_task, sample_history):
        """Profile returns valid stats after multiple builds."""
        for _ in range(5):
            full_orchestrator.build_optimal_context(
                task=sample_task,
                system_prompt="You are Shadow.",
                conversation_history=sample_history,
            )

        profile = full_orchestrator.get_context_profile()

        assert profile["total_builds"] == 5
        assert profile["avg_tokens_used"] > 0
        assert profile["avg_tokens_budget"] > 0
        assert 0 <= profile["avg_usage_percent"] <= 100
        assert isinstance(profile["avg_grimoire_tokens"], (int, float))
        assert isinstance(profile["avg_tool_tokens"], (int, float))
        assert isinstance(profile["avg_history_tokens"], (int, float))
        assert isinstance(profile["times_trimmed"], int)

    def test_profile_empty_when_no_builds(self):
        """Profile returns zeros when no builds have happened."""
        orch = ContextOrchestrator()
        profile = orch.get_context_profile()

        assert profile["total_builds"] == 0
        assert profile["avg_tokens_used"] == 0
        assert profile["most_common_trim_target"] is None

    def test_estimate_returns_reasonable_values(self, full_orchestrator):
        """Estimate returns plausible token counts and percentages."""
        estimate = full_orchestrator.estimate_context_for_task(
            task={"description": "Calculate compound interest", "type": "math"},
            model="gemma4-26b",
        )

        assert "estimated_total_tokens" in estimate
        assert "estimated_usage_percent" in estimate
        assert "will_need_trimming" in estimate
        assert "token_budget" in estimate
        assert estimate["estimated_total_tokens"] > 0
        assert estimate["token_budget"] > 0

    def test_estimate_no_context_manager(self):
        """Estimate works without ContextManager (uses defaults)."""
        orch = ContextOrchestrator()
        estimate = orch.estimate_context_for_task(
            task={"description": "test", "type": "test"},
        )

        assert estimate["token_budget"] > 0
        assert estimate["estimated_total_tokens"] > 0


# ===========================================================================
# Integration tests
# ===========================================================================

class TestOrchestratorIntegration:
    """Tests for orchestrator integration patterns."""

    def test_orchestrator_initializes_with_available_components(
        self, mock_context_manager, mock_compressor, mock_staged_retrieval,
        mock_tool_loader, mock_failure_pattern_db, mock_grimoire,
    ):
        """ContextOrchestrator accepts all components without error."""
        orch = ContextOrchestrator(
            context_manager=mock_context_manager,
            compressor=mock_compressor,
            staged_retrieval=mock_staged_retrieval,
            tool_loader=mock_tool_loader,
            failure_pattern_db=mock_failure_pattern_db,
            grimoire=mock_grimoire,
        )

        assert orch._context_manager is mock_context_manager
        assert orch._compressor is mock_compressor
        assert orch._staged_retrieval is mock_staged_retrieval
        assert orch._tool_loader is mock_tool_loader
        assert orch._failure_pattern_db is mock_failure_pattern_db
        assert orch._grimoire is mock_grimoire

    def test_fallback_when_unavailable(self):
        """ContextOrchestrator(None) works — used by orchestrator fallback path."""
        orch = ContextOrchestrator()
        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test"},
            system_prompt="You are Shadow.",
            conversation_history=[],
        )

        assert isinstance(pkg, ContextPackage)
        assert pkg.system_prompt == "You are Shadow."

    def test_token_breakdown_sums_approximately(self, full_orchestrator, sample_task, sample_history):
        """Token breakdown components sum to approximately total_tokens."""
        pkg = full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
        )

        breakdown = pkg.token_breakdown
        component_sum = (
            breakdown.get("system_prompt", 0)
            + breakdown.get("history", 0)
            + breakdown.get("grimoire", 0)
            + breakdown.get("failure_patterns", 0)
            + breakdown.get("tools", 0)
        )

        assert breakdown.get("total", 0) == component_sum

    def test_context_package_dataclass_defaults(self):
        """ContextPackage has sensible defaults for all fields."""
        pkg = ContextPackage()
        assert pkg.system_prompt == ""
        assert pkg.messages == []
        assert pkg.grimoire_context == ""
        assert pkg.failure_patterns == ""
        assert pkg.tool_schemas == []
        assert pkg.total_tokens == 0
        assert pkg.token_budget == 0
        assert pkg.token_breakdown == {}
        assert pkg.trimmed is False
        assert pkg.trimmed_details == []
        assert pkg.compression_report == {}
        assert pkg.retrieval_stats == {}


# ===========================================================================
# Edge case tests
# ===========================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_task_description(self, full_orchestrator, sample_history):
        """Empty task description doesn't crash."""
        pkg = full_orchestrator.build_optimal_context(
            task={"description": "", "type": "unknown"},
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
        )

        assert isinstance(pkg, ContextPackage)

    def test_very_long_system_prompt(self, full_orchestrator, sample_task, sample_history):
        """Very long system prompt is preserved (never trimmed)."""
        long_prompt = "You are Shadow. " * 500
        pkg = full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt=long_prompt,
            conversation_history=sample_history,
        )

        assert pkg.system_prompt == long_prompt

    def test_no_conversation_history(self, full_orchestrator, sample_task):
        """No conversation history returns package with empty messages."""
        pkg = full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=[],
        )

        assert isinstance(pkg, ContextPackage)
        assert pkg.messages == []

    def test_none_conversation_history(self, full_orchestrator, sample_task):
        """None conversation history handled gracefully."""
        pkg = full_orchestrator.build_optimal_context(
            task=sample_task,
            system_prompt="You are Shadow.",
            conversation_history=None,
        )

        assert isinstance(pkg, ContextPackage)
        assert pkg.messages == []

    def test_model_not_in_config_uses_default(self):
        """Unknown model uses default token limit."""
        orch = ContextOrchestrator()
        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test"},
            system_prompt="You are Shadow.",
            conversation_history=[],
            model="totally-unknown-model-xyz",
        )

        assert pkg.token_budget > 0  # Should use default

    def test_set_failure_patterns(self, full_orchestrator):
        """set_failure_patterns stores patterns for later use."""
        patterns = [{"task_type": "code", "mistake": "bad import", "correct_approach": "use pathlib"}]
        full_orchestrator.set_failure_patterns(patterns)
        assert full_orchestrator._prefetched_failure_patterns == patterns

    def test_load_failure_patterns_from_results(self, full_orchestrator, mock_failure_pattern_db):
        """_load_failure_patterns_from_results formats patterns correctly."""
        patterns = [{"task_type": "math", "mistake": "wrong formula", "correct_approach": "use compound"}]
        result = full_orchestrator._load_failure_patterns_from_results(patterns)

        assert "FAILURE PATTERNS" in result
        mock_failure_pattern_db.format_patterns_for_context.assert_called_once_with(patterns)

    def test_load_failure_patterns_from_results_empty(self, full_orchestrator):
        """Empty patterns returns empty string."""
        result = full_orchestrator._load_failure_patterns_from_results([])
        assert result == ""

    def test_task_with_no_module(self, full_orchestrator, mock_tool_loader, sample_history):
        """Task without module key loads tools with module_name=None."""
        pkg = full_orchestrator.build_optimal_context(
            task={"description": "general query", "type": "conversation"},
            system_prompt="You are Shadow.",
            conversation_history=sample_history,
        )

        mock_tool_loader.get_tools_for_task.assert_called_once_with(
            module_name=None,
            task={"description": "general query", "type": "conversation"},
        )

    def test_staged_retrieval_empty_results(self, mock_context_manager):
        """Empty staged retrieval results produce empty grimoire_context."""
        empty_sr = MagicMock()
        empty_sr.search = MagicMock(return_value=[])
        empty_sr.get_retrieval_stats = MagicMock(return_value={})

        orch = ContextOrchestrator(
            context_manager=mock_context_manager,
            staged_retrieval=empty_sr,
        )

        pkg = orch.build_optimal_context(
            task={"description": "test", "type": "test"},
            system_prompt="You are Shadow.",
            conversation_history=[],
        )

        assert pkg.grimoire_context == ""
