"""
Tests for benchmark source guards.
===================================
Verifies that source="benchmark" skips Grimoire storage and Apex escalation.
"""

import pytest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.shadow.orchestrator import (
    Orchestrator,
    TaskClassification,
    TaskType,
    BrainType,
    ExecutionPlan,
)


# --- Test Config ---

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
def config(tmp_path: Path) -> dict:
    cfg = dict(TEST_CONFIG)
    cfg["system"] = {"state_file": str(tmp_path / "state.json")}
    return cfg


@pytest.fixture
def orchestrator(config: dict) -> Orchestrator:
    return Orchestrator(config)


# --- _step7_log: Grimoire guard ---

class TestStep7BenchmarkGuard:
    """Benchmark source must skip Grimoire storage in _step7_log."""

    @pytest.mark.asyncio
    async def test_benchmark_source_skips_grimoire_storage(self, orchestrator):
        """source='benchmark' must not call grimoire.remember()."""
        mock_grimoire_inner = MagicMock()
        mock_grimoire_inner.remember = MagicMock(return_value="fake_id")

        mock_grimoire_mod = MagicMock()
        mock_grimoire_mod._grimoire = mock_grimoire_inner

        orchestrator.registry = MagicMock()
        orchestrator.registry.__contains__ = lambda self, key: key == "grimoire"
        orchestrator.registry.get_module = MagicMock(return_value=mock_grimoire_mod)

        classification = TaskClassification(
            task_type=TaskType.RESEARCH,
            complexity="simple",
            target_module="reaper",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=5,
        )

        import time
        await orchestrator._step7_log(
            user_input="What is the capital of France?",
            classification=classification,
            response="Paris is the capital of France.",
            loop_start=time.time(),
            source="benchmark",
        )

        mock_grimoire_inner.remember.assert_not_called()

    @pytest.mark.asyncio
    async def test_user_source_stores_to_grimoire(self, orchestrator):
        """source='user' (default) must still store to Grimoire."""
        mock_grimoire_inner = MagicMock()
        mock_grimoire_inner.remember = MagicMock(return_value="fake_id")

        mock_grimoire_mod = MagicMock()
        mock_grimoire_mod._grimoire = mock_grimoire_inner

        orchestrator.registry = MagicMock()
        orchestrator.registry.__contains__ = lambda self, key: key == "grimoire"
        orchestrator.registry.get_module = MagicMock(return_value=mock_grimoire_mod)

        classification = TaskClassification(
            task_type=TaskType.RESEARCH,
            complexity="simple",
            target_module="reaper",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=5,
        )

        import time
        await orchestrator._step7_log(
            user_input="What is the capital of France?",
            classification=classification,
            response="Paris is the capital of France.",
            loop_start=time.time(),
            source="user",
        )

        mock_grimoire_inner.remember.assert_called_once()
        call_kwargs = mock_grimoire_inner.remember.call_args
        assert call_kwargs[1]["source"] == "interaction_log"
        assert call_kwargs[1]["category"] == "operational"

    @pytest.mark.asyncio
    async def test_telegram_source_stores_to_grimoire(self, orchestrator):
        """Non-benchmark sources must still store to Grimoire."""
        mock_grimoire_inner = MagicMock()
        mock_grimoire_inner.remember = MagicMock(return_value="fake_id")

        mock_grimoire_mod = MagicMock()
        mock_grimoire_mod._grimoire = mock_grimoire_inner

        orchestrator.registry = MagicMock()
        orchestrator.registry.__contains__ = lambda self, key: key == "grimoire"
        orchestrator.registry.get_module = MagicMock(return_value=mock_grimoire_mod)

        classification = TaskClassification(
            task_type=TaskType.CONVERSATION,
            complexity="simple",
            target_module="direct",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=5,
        )

        import time
        await orchestrator._step7_log(
            user_input="hello",
            classification=classification,
            response="Hello!",
            loop_start=time.time(),
            source="telegram_message",
        )

        mock_grimoire_inner.remember.assert_called_once()


# --- _step5_with_retry: Apex escalation guard ---

class TestApexEscalationBenchmarkGuard:
    """Benchmark source must block Apex escalation."""

    @pytest.mark.asyncio
    async def test_benchmark_exhausted_does_not_escalate(self, orchestrator):
        """When source='benchmark' and retries are exhausted, Apex must not be called."""
        # Set up retry engine to report exhaustion
        mock_retry = MagicMock()
        mock_retry.attempt_task = AsyncMock(return_value={
            "exhausted": True,
            "attempts": [{"strategy": "default", "error": "failed"}] * 3,
            "final_result": {"response": "I could not solve this."},
        })
        orchestrator._retry_engine = mock_retry

        # Register an Apex module — it should NOT be called
        mock_apex = MagicMock()
        mock_apex.execute = AsyncMock()
        orchestrator.registry = MagicMock()
        orchestrator.registry.__contains__ = lambda self, key: key in ("apex",)
        orchestrator.registry.get_module = MagicMock(return_value=mock_apex)

        classification = TaskClassification(
            task_type=TaskType.RESEARCH,
            complexity="complex",
            target_module="reaper",
            brain=BrainType.SMART,
            safety_flag=False,
            priority=5,
        )
        plan = ExecutionPlan(
            steps=[{"tool": "web_search", "module": "reaper", "params": {}}],
            cerberus_approved=True,
        )

        result = await orchestrator._step5_with_retry(
            user_input="Solve this complex problem",
            plan=plan,
            classification=classification,
            context=[],
            source="benchmark",
        )

        # Apex should never have been called
        mock_apex.execute.assert_not_called()
        # Should not set pending escalation
        assert orchestrator._pending_escalation is None
        # Should return failure response, not escalation offer
        assert "escalate" not in result.lower() or "benchmark" in result.lower()

    @pytest.mark.asyncio
    async def test_autonomous_exhausted_does_escalate(self, orchestrator):
        """When source='scheduled_task' and retries are exhausted, Apex IS called."""
        mock_retry = MagicMock()
        mock_retry.attempt_task = AsyncMock(return_value={
            "exhausted": True,
            "attempts": [{"strategy": "default", "error": "failed"}] * 3,
            "final_result": {"response": "I could not solve this."},
        })
        mock_retry.escalate_to_apex = AsyncMock(return_value={
            "success": True,
            "answer": "Apex solved it.",
        })
        orchestrator._retry_engine = mock_retry

        mock_apex = MagicMock()
        orchestrator.registry = MagicMock()
        orchestrator.registry.__contains__ = lambda self, key: key in ("apex",)
        orchestrator.registry.get_module = MagicMock(return_value=mock_apex)

        classification = TaskClassification(
            task_type=TaskType.RESEARCH,
            complexity="complex",
            target_module="reaper",
            brain=BrainType.SMART,
            safety_flag=False,
            priority=5,
        )
        plan = ExecutionPlan(
            steps=[{"tool": "web_search", "module": "reaper", "params": {}}],
            cerberus_approved=True,
        )

        result = await orchestrator._step5_with_retry(
            user_input="Solve this complex problem",
            plan=plan,
            classification=classification,
            context=[],
            source="scheduled_task",
        )

        # Apex escalation SHOULD have been called
        mock_retry.escalate_to_apex.assert_called_once()
        assert result == "Apex solved it."

    @pytest.mark.asyncio
    async def test_user_exhausted_offers_escalation(self, orchestrator):
        """When source='user' and retries are exhausted, offer escalation (don't auto-call)."""
        mock_retry = MagicMock()
        mock_retry.attempt_task = AsyncMock(return_value={
            "exhausted": True,
            "attempts": [{"strategy": "default", "error": "failed"}] * 3,
            "final_result": {"response": "I could not solve this."},
        })
        orchestrator._retry_engine = mock_retry

        mock_apex = MagicMock()
        orchestrator.registry = MagicMock()
        orchestrator.registry.__contains__ = lambda self, key: key in ("apex",)
        orchestrator.registry.get_module = MagicMock(return_value=mock_apex)

        classification = TaskClassification(
            task_type=TaskType.RESEARCH,
            complexity="complex",
            target_module="reaper",
            brain=BrainType.SMART,
            safety_flag=False,
            priority=5,
        )
        plan = ExecutionPlan(
            steps=[{"tool": "web_search", "module": "reaper", "params": {}}],
            cerberus_approved=True,
        )

        result = await orchestrator._step5_with_retry(
            user_input="Solve this complex problem",
            plan=plan,
            classification=classification,
            context=[],
            source="user",
        )

        # Should offer escalation, not auto-escalate
        assert "escalate" in result.lower()
        assert orchestrator._pending_escalation is not None
