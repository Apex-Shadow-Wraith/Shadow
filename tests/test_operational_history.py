"""
Tests for Operational History Logging
======================================
Verifies that:
  (a) Step 7 stores a compact operational summary in Grimoire
  (b) /history returns recent operational logs
  (c) /failures filters to only failures and fallbacks
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.base import ModuleStatus, ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_grimoire_mock(stored_entries=None):
    """Create a mock Grimoire with working recall_operational."""
    grim = MagicMock()
    grim._stored = [] if stored_entries is None else stored_entries

    def fake_remember(**kwargs):
        entry = {
            "id": f"mem-{len(grim._stored)}",
            "content": kwargs.get("content", ""),
            "source": kwargs.get("source", ""),
            "category": kwargs.get("category", ""),
            "created_at": datetime.now().isoformat(),
            "metadata": kwargs.get("metadata", {}),
        }
        grim._stored.append(entry)
        return entry["id"]

    def fake_recall_operational(limit=20, failures_only=False):
        ops = [e for e in grim._stored
               if e.get("source") == "interaction_log"
               and e.get("category") == "operational"]
        if failures_only:
            ops = [e for e in ops
                   if "failure" in e["content"] or "fallback=yes" in e["content"]]
        ops.sort(key=lambda x: x["created_at"], reverse=True)
        return ops[:limit]

    grim.remember = MagicMock(side_effect=fake_remember)
    grim.recall_operational = MagicMock(side_effect=fake_recall_operational)
    return grim


def _make_classification(target_module="wraith", task_type="general",
                         brain="router", complexity="simple"):
    """Build a minimal TaskClassification-like object."""
    cls = MagicMock()
    cls.target_module = target_module
    cls.task_type = MagicMock()
    cls.task_type.value = task_type
    cls.brain = MagicMock()
    cls.brain.value = brain
    cls.complexity = complexity
    cls.safety_flag = False
    cls.priority = 3
    return cls


def _make_orchestrator_with_grimoire(grim):
    """Build a minimal Orchestrator mock wired to a Grimoire mock."""
    from modules.shadow.orchestrator import Orchestrator

    # Use a real Orchestrator but with heavily mocked internals
    with patch.object(Orchestrator, "__init__", lambda self, *a, **kw: None):
        orch = Orchestrator.__new__(Orchestrator)

    # Minimal state
    orch._state = MagicMock()
    orch._state.interaction_count = 1

    # Registry with grimoire
    grimoire_mod = MagicMock()
    grimoire_mod._grimoire = grim
    grimoire_mod.status = ModuleStatus.ONLINE

    registry = MagicMock()
    registry.__contains__ = lambda self, name: name == "grimoire"
    registry.get_module = MagicMock(return_value=grimoire_mod)

    orch.registry = registry
    return orch


# ---------------------------------------------------------------------------
# (a) Interaction log is stored in Grimoire after Step 7
# ---------------------------------------------------------------------------

class TestStep7StoresOperationalLog:
    @pytest.mark.asyncio
    async def test_stores_summary_on_success(self):
        """Step 7 should store a compact operational summary in Grimoire."""
        grim = _make_grimoire_mock()
        orch = _make_orchestrator_with_grimoire(grim)

        classification = _make_classification(target_module="cipher")
        loop_start = time.time() - 0.15  # simulate 150ms

        # Import and call _step7_log directly
        from modules.shadow.orchestrator import Orchestrator
        await Orchestrator._step7_log(
            orch,
            user_input="What is 2+2?",
            classification=classification,
            response="4",
            loop_start=loop_start,
            confidence=0.95,
            used_fallback=False,
            tool_name="calculate",
        )

        # Verify remember was called
        grim.remember.assert_called_once()
        call_kwargs = grim.remember.call_args[1]

        assert call_kwargs["source"] == "interaction_log"
        assert call_kwargs["category"] == "operational"
        assert call_kwargs["source_module"] == "shadow"
        assert call_kwargs["check_duplicates"] is False

        content = call_kwargs["content"]
        assert "module=cipher" in content
        assert "tool=calculate" in content
        assert "outcome=success" in content
        assert "confidence=0.95" in content
        assert "fallback=no" in content
        assert "What is 2+2?" in content

    @pytest.mark.asyncio
    async def test_stores_failure_on_fallback_response(self):
        """A [Fallback...] response should be logged as failure."""
        grim = _make_grimoire_mock()
        orch = _make_orchestrator_with_grimoire(grim)

        classification = _make_classification(target_module="reaper")

        await __import__("modules.shadow.orchestrator", fromlist=["Orchestrator"]).Orchestrator._step7_log(
            orch,
            user_input="Search for landscaping tips",
            classification=classification,
            response="[Fallback] Could not reach search engine.",
            loop_start=time.time() - 0.5,
            confidence=0.3,
            used_fallback=True,
            tool_name="web_search",
        )

        call_kwargs = grim.remember.call_args[1]
        assert "outcome=failure" in call_kwargs["content"]
        assert "fallback=yes" in call_kwargs["content"]

    @pytest.mark.asyncio
    async def test_no_crash_without_grimoire(self):
        """Step 7 should not crash if Grimoire is not in registry."""
        from modules.shadow.orchestrator import Orchestrator

        with patch.object(Orchestrator, "__init__", lambda self, *a, **kw: None):
            orch = Orchestrator.__new__(Orchestrator)

        orch._state = MagicMock()
        orch._state.interaction_count = 1

        # Registry without grimoire
        registry = MagicMock()
        registry.__contains__ = lambda self, name: False
        orch.registry = registry

        classification = _make_classification()

        # Should not raise
        await Orchestrator._step7_log(
            orch,
            user_input="hello",
            classification=classification,
            response="Hi there",
            loop_start=time.time(),
        )

    @pytest.mark.asyncio
    async def test_defaults_when_no_kwargs(self):
        """Step 7 should work with no optional kwargs (backward compat)."""
        grim = _make_grimoire_mock()
        orch = _make_orchestrator_with_grimoire(grim)

        classification = _make_classification(target_module="wraith")

        from modules.shadow.orchestrator import Orchestrator
        await Orchestrator._step7_log(
            orch,
            user_input="set a reminder",
            classification=classification,
            response="Reminder set for 3pm.",
            loop_start=time.time() - 0.05,
        )

        call_kwargs = grim.remember.call_args[1]
        assert "confidence=n/a" in call_kwargs["content"]
        assert "fallback=no" in call_kwargs["content"]
        assert "tool=none" in call_kwargs["content"]


# ---------------------------------------------------------------------------
# (b) /history returns recent operational logs
# ---------------------------------------------------------------------------

class TestHistoryCommand:
    @pytest.mark.asyncio
    async def test_history_returns_entries(self):
        """/history should query Grimoire for operational entries."""
        grim = _make_grimoire_mock()

        # Pre-populate some operational entries
        grim.remember(
            content="input=hello | module=wraith | tool=none | outcome=success | confidence=0.90 | fallback=no | time=50ms",
            source="interaction_log",
            source_module="shadow",
            category="operational",
        )
        grim.remember(
            content="input=search stuff | module=reaper | tool=web_search | outcome=failure | confidence=0.30 | fallback=yes | time=500ms",
            source="interaction_log",
            source_module="shadow",
            category="operational",
        )

        entries = grim.recall_operational(limit=20)
        assert len(entries) == 2
        assert "wraith" in entries[0]["content"] or "wraith" in entries[1]["content"]

    @pytest.mark.asyncio
    async def test_history_limit(self):
        """/history N should respect the limit."""
        grim = _make_grimoire_mock()
        for i in range(10):
            grim.remember(
                content=f"input=query{i} | module=wraith | tool=none | outcome=success | confidence=0.80 | fallback=no | time=10ms",
                source="interaction_log",
                source_module="shadow",
                category="operational",
            )

        entries = grim.recall_operational(limit=3)
        assert len(entries) == 3


# ---------------------------------------------------------------------------
# (c) /failures filters correctly
# ---------------------------------------------------------------------------

class TestFailuresCommand:
    @pytest.mark.asyncio
    async def test_failures_only_returns_failures(self):
        """/failures should only return entries with failure or fallback=yes."""
        grim = _make_grimoire_mock()

        # Success entry
        grim.remember(
            content="input=hello | module=wraith | tool=none | outcome=success | confidence=0.90 | fallback=no | time=50ms",
            source="interaction_log",
            source_module="shadow",
            category="operational",
        )
        # Failure entry
        grim.remember(
            content="input=search | module=reaper | tool=web_search | outcome=failure | confidence=0.30 | fallback=yes | time=500ms",
            source="interaction_log",
            source_module="shadow",
            category="operational",
        )
        # Another success
        grim.remember(
            content="input=calculate | module=cipher | tool=calc | outcome=success | confidence=0.95 | fallback=no | time=20ms",
            source="interaction_log",
            source_module="shadow",
            category="operational",
        )

        failures = grim.recall_operational(limit=20, failures_only=True)
        assert len(failures) == 1
        assert "failure" in failures[0]["content"]
        assert "reaper" in failures[0]["content"]

    @pytest.mark.asyncio
    async def test_no_failures_returns_empty(self):
        """If all interactions succeeded, /failures returns empty."""
        grim = _make_grimoire_mock()

        grim.remember(
            content="input=hi | module=wraith | tool=none | outcome=success | confidence=0.90 | fallback=no | time=10ms",
            source="interaction_log",
            source_module="shadow",
            category="operational",
        )

        failures = grim.recall_operational(limit=20, failures_only=True)
        assert len(failures) == 0

    @pytest.mark.asyncio
    async def test_fallback_yes_also_caught(self):
        """Entries with fallback=yes but outcome=success should still show in /failures."""
        grim = _make_grimoire_mock()

        # Fallback was used but still got a response
        grim.remember(
            content="input=complex | module=apex | tool=ask_claude | outcome=success | confidence=0.60 | fallback=yes | time=2000ms",
            source="interaction_log",
            source_module="shadow",
            category="operational",
        )

        failures = grim.recall_operational(limit=20, failures_only=True)
        assert len(failures) == 1
        assert "fallback=yes" in failures[0]["content"]
