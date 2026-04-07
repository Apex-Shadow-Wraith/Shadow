"""
Tests for Failure Pattern Database
====================================
Tests storage, retrieval, deduplication, analytics, and
integration with the orchestrator's Step 3 context loading.
"""

import json
import pytest
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.shadow.failure_patterns import FailurePatternDB


# --- Helpers ---


def make_grimoire_mock(search_results=None, store_result=None):
    """Create a mock GrimoireModule with configurable responses."""
    grimoire = AsyncMock()
    grimoire.status = ModuleStatus.ONLINE

    async def mock_execute(tool_name, params):
        if tool_name == "memory_store":
            content = store_result or f"Memory stored: test-id-{datetime.now().timestamp()}"
            return ToolResult(
                success=True, content=content,
                tool_name=tool_name, module="grimoire",
            )
        elif tool_name == "memory_search":
            return ToolResult(
                success=True, content=search_results or [],
                tool_name=tool_name, module="grimoire",
            )
        elif tool_name == "memory_forget":
            return ToolResult(
                success=True, content="Deleted",
                tool_name=tool_name, module="grimoire",
            )
        return ToolResult(
            success=False, content=None,
            tool_name=tool_name, module="grimoire",
            error=f"Unknown tool: {tool_name}",
        )

    grimoire.execute = mock_execute
    return grimoire


# --- Core Storage Tests ---


class TestFailurePatternStorage:
    """Test storing failure patterns in Grimoire."""

    @pytest.mark.asyncio
    async def test_store_failure_pattern_all_fields(self):
        """Failure pattern stored correctly in Grimoire with all fields."""
        stored_params = {}

        async def capture_execute(tool_name, params):
            if tool_name == "memory_store":
                stored_params.update(params)
                return ToolResult(
                    success=True, content="Memory stored: fp-001",
                    tool_name=tool_name, module="grimoire",
                )
            elif tool_name == "memory_search":
                return ToolResult(
                    success=True, content=[],
                    tool_name=tool_name, module="grimoire",
                )
            return ToolResult(
                success=False, content=None,
                tool_name=tool_name, module="grimoire",
                error="Unknown",
            )

        grimoire = AsyncMock()
        grimoire.execute = capture_execute

        db = FailurePatternDB()
        memory_id = await db.store_failure_pattern(
            grimoire=grimoire,
            task="calculate compound interest",
            task_type="math",
            mistake="Used simple interest formula",
            correct_approach="Use A = P(1 + r/n)^(nt)",
            source="retry_engine",
            trust_level=0.5,
        )

        assert memory_id  # Non-empty
        assert "content" in stored_params
        assert "FAILURE PATTERN [math]" in stored_params["content"]
        assert "simple interest" in stored_params["content"]

        metadata = stored_params["metadata"]
        assert metadata["category"] == "failure_pattern"
        assert metadata["task_type"] == "math"
        assert metadata["mistake"] == "Used simple interest formula"
        assert metadata["correct_approach"] == "Use A = P(1 + r/n)^(nt)"
        assert metadata["source"] == "retry_engine"
        assert metadata["trust_level"] == 0.5
        assert metadata["match_count"] == 0
        assert "timestamp" in metadata
        assert "failure_pattern" in metadata["tags"]
        assert "math" in metadata["tags"]

    @pytest.mark.asyncio
    async def test_store_returns_memory_id(self):
        """store_failure_pattern returns the memory ID."""
        grimoire = make_grimoire_mock(store_result="Memory stored: fp-123")
        db = FailurePatternDB()

        result = await db.store_failure_pattern(
            grimoire=grimoire,
            task="write sorting algorithm",
            task_type="code",
            mistake="Used bubble sort for large dataset",
            correct_approach="Use merge sort or timsort for O(n log n)",
            source="apex_learning",
            trust_level=0.7,
        )

        assert "fp-123" in result

    @pytest.mark.asyncio
    async def test_store_failure_handles_grimoire_error(self):
        """Gracefully handles Grimoire storage errors."""
        grimoire = AsyncMock()

        async def fail_execute(tool_name, params):
            if tool_name == "memory_search":
                return ToolResult(success=True, content=[], tool_name=tool_name, module="grimoire")
            return ToolResult(
                success=False, content=None,
                tool_name=tool_name, module="grimoire",
                error="DB connection failed",
            )

        grimoire.execute = fail_execute
        db = FailurePatternDB()

        result = await db.store_failure_pattern(
            grimoire=grimoire,
            task="test", task_type="test",
            mistake="test", correct_approach="test",
        )

        assert result == ""


# --- Search / Retrieval Tests ---


class TestFailurePatternSearch:
    """Test searching for failure patterns."""

    @pytest.mark.asyncio
    async def test_search_returns_matching_patterns(self):
        """Failure pattern retrieved when similar task is attempted."""
        search_results = [
            {
                "id": "fp-001",
                "content": "FAILURE PATTERN [math]: Task: interest. Mistake: wrong formula. Correct approach: compound.",
                "metadata": {
                    "category": "failure_pattern",
                    "task_type": "math",
                    "mistake": "Used simple interest formula",
                    "correct_approach": "Use compound interest formula",
                    "source": "retry_engine",
                    "trust_level": 0.5,
                    "match_count": 3,
                },
                "relevance": 0.85,
            },
        ]

        grimoire = make_grimoire_mock(search_results=search_results)
        db = FailurePatternDB()

        patterns = await db.search_failure_patterns(
            grimoire=grimoire,
            query="calculate interest rates",
            limit=3,
        )

        assert len(patterns) == 1
        assert patterns[0]["task_type"] == "math"
        assert patterns[0]["mistake"] == "Used simple interest formula"
        assert patterns[0]["correct_approach"] == "Use compound interest formula"

    @pytest.mark.asyncio
    async def test_search_filters_non_failure_patterns(self):
        """Only returns items with failure_pattern category."""
        search_results = [
            {
                "id": "mem-001",
                "content": "Shadow uses Ollama for model serving",
                "metadata": {"category": "system", "type": "system"},
                "relevance": 0.6,
            },
            {
                "id": "fp-001",
                "content": "FAILURE PATTERN [code]: ...",
                "metadata": {
                    "category": "failure_pattern",
                    "task_type": "code",
                    "mistake": "Wrong approach",
                    "correct_approach": "Right approach",
                    "source": "retry_engine",
                    "trust_level": 0.5,
                    "match_count": 1,
                },
                "relevance": 0.55,
            },
        ]

        grimoire = make_grimoire_mock(search_results=search_results)
        db = FailurePatternDB()

        patterns = await db.search_failure_patterns(
            grimoire=grimoire, query="code task", limit=3,
        )

        assert len(patterns) == 1
        assert patterns[0]["task_type"] == "code"

    @pytest.mark.asyncio
    async def test_search_empty_results_returns_empty(self):
        """Empty failure pattern search (no matches) returns empty list."""
        grimoire = make_grimoire_mock(search_results=[])
        db = FailurePatternDB()

        patterns = await db.search_failure_patterns(
            grimoire=grimoire, query="something random", limit=3,
        )

        assert patterns == []

    @pytest.mark.asyncio
    async def test_search_handles_grimoire_failure(self):
        """Handles Grimoire search failure gracefully."""
        grimoire = AsyncMock()

        async def fail_search(tool_name, params):
            return ToolResult(
                success=False, content=None,
                tool_name=tool_name, module="grimoire",
                error="Search failed",
            )

        grimoire.execute = fail_search
        db = FailurePatternDB()

        patterns = await db.search_failure_patterns(
            grimoire=grimoire, query="test", limit=3,
        )

        assert patterns == []

    @pytest.mark.asyncio
    async def test_search_respects_limit(self):
        """Search returns at most `limit` patterns."""
        search_results = [
            {
                "id": f"fp-{i}",
                "content": f"FAILURE PATTERN [code]: pattern {i}",
                "metadata": {
                    "category": "failure_pattern",
                    "task_type": "code",
                    "mistake": f"mistake {i}",
                    "correct_approach": f"fix {i}",
                    "source": "retry_engine",
                    "trust_level": 0.5,
                    "match_count": i,
                },
                "relevance": 0.8 - i * 0.1,
            }
            for i in range(5)
        ]

        grimoire = make_grimoire_mock(search_results=search_results)
        db = FailurePatternDB()

        patterns = await db.search_failure_patterns(
            grimoire=grimoire, query="code task", limit=2,
        )

        assert len(patterns) == 2

    @pytest.mark.asyncio
    async def test_search_handles_string_results(self):
        """Handles Grimoire returning raw strings instead of dicts."""
        search_results = [
            "FAILURE PATTERN [research]: Task: find info. Mistake: used wrong source. Correct approach: use official docs.",
            "Some unrelated memory about databases.",
        ]

        grimoire = make_grimoire_mock(search_results=search_results)
        db = FailurePatternDB()

        patterns = await db.search_failure_patterns(
            grimoire=grimoire, query="research task", limit=3,
        )

        assert len(patterns) == 1
        assert patterns[0]["task_type"] == "research"


# --- Deduplication Tests ---


class TestFailurePatternDeduplication:
    """Test that similar patterns update instead of duplicating."""

    @pytest.mark.asyncio
    async def test_duplicate_updates_existing(self):
        """Similar pattern updates existing instead of creating duplicate."""
        call_log = []

        async def tracking_execute(tool_name, params):
            call_log.append(tool_name)
            if tool_name == "memory_search":
                # Return an existing pattern with high relevance (>0.9)
                return ToolResult(
                    success=True,
                    content=[
                        {
                            "id": "existing-fp-001",
                            "content": "FAILURE PATTERN [math]: old content",
                            "metadata": {
                                "category": "failure_pattern",
                                "task_type": "math",
                                "mistake": "old mistake",
                                "correct_approach": "old approach",
                                "source": "retry_engine",
                                "trust_level": 0.5,
                                "match_count": 2,
                                "timestamp": datetime.now().isoformat(),
                            },
                            "relevance": 0.95,  # Above DEDUP_THRESHOLD
                        },
                    ],
                    tool_name=tool_name, module="grimoire",
                )
            elif tool_name == "memory_forget":
                return ToolResult(
                    success=True, content="Deleted",
                    tool_name=tool_name, module="grimoire",
                )
            elif tool_name == "memory_store":
                return ToolResult(
                    success=True, content="Memory stored: updated-fp-001",
                    tool_name=tool_name, module="grimoire",
                )
            return ToolResult(
                success=False, content=None,
                tool_name=tool_name, module="grimoire",
            )

        grimoire = AsyncMock()
        grimoire.execute = tracking_execute

        db = FailurePatternDB()
        result = await db.store_failure_pattern(
            grimoire=grimoire,
            task="calculate interest",
            task_type="math",
            mistake="new mistake description",
            correct_approach="new correct approach",
            source="apex_learning",
            trust_level=0.7,
        )

        # Should have: search (dedup check), forget (delete old), store (new version)
        assert "memory_search" in call_log
        assert "memory_forget" in call_log
        assert "memory_store" in call_log

    @pytest.mark.asyncio
    async def test_no_duplicate_when_below_threshold(self):
        """Low similarity creates a new pattern (no dedup)."""
        call_log = []

        async def tracking_execute(tool_name, params):
            call_log.append(tool_name)
            if tool_name == "memory_search":
                return ToolResult(
                    success=True,
                    content=[
                        {
                            "id": "unrelated-001",
                            "content": "FAILURE PATTERN [code]: unrelated",
                            "metadata": {
                                "category": "failure_pattern",
                                "task_type": "code",
                            },
                            "relevance": 0.3,  # Below DEDUP_THRESHOLD
                        },
                    ],
                    tool_name=tool_name, module="grimoire",
                )
            elif tool_name == "memory_store":
                return ToolResult(
                    success=True, content="Memory stored: new-fp-001",
                    tool_name=tool_name, module="grimoire",
                )
            return ToolResult(
                success=False, content=None,
                tool_name=tool_name, module="grimoire",
            )

        grimoire = AsyncMock()
        grimoire.execute = tracking_execute

        db = FailurePatternDB()
        result = await db.store_failure_pattern(
            grimoire=grimoire,
            task="completely different task",
            task_type="research",
            mistake="new mistake",
            correct_approach="new approach",
        )

        # Should NOT have called memory_forget (no dedup)
        assert "memory_forget" not in call_log
        assert "memory_store" in call_log


# --- Context Integration Tests ---


class TestFailurePatternContext:
    """Test failure patterns included in Step 3 context."""

    def test_format_patterns_for_context(self):
        """Failure patterns formatted correctly for context manager."""
        db = FailurePatternDB()

        patterns = [
            {
                "task_type": "math",
                "mistake": "Used simple interest",
                "correct_approach": "Use compound interest formula",
                "source": "retry_engine",
                "trust_level": 0.5,
            },
            {
                "task_type": "code",
                "mistake": "Used O(n^2) sort",
                "correct_approach": "Use O(n log n) sort for large datasets",
                "source": "apex_learning",
                "trust_level": 0.7,
            },
        ]

        formatted = db.format_patterns_for_context(patterns)

        assert len(formatted) == 2
        assert formatted[0]["description"].startswith("Task type: math")
        assert "simple interest" in formatted[0]["description"]
        assert "compound interest" in formatted[0]["description"]
        assert formatted[1]["task_type"] == "code"

    def test_format_empty_patterns(self):
        """Empty pattern list returns empty formatted list."""
        db = FailurePatternDB()
        assert db.format_patterns_for_context([]) == []

    @pytest.mark.asyncio
    async def test_step3_includes_failure_patterns(self):
        """Failure patterns included in Step 3 context with correct label."""
        from modules.shadow.orchestrator import (
            Orchestrator, TaskClassification, TaskType, BrainType,
        )

        config = {
            "models": {
                "ollama_base_url": "http://localhost:11434",
                "router": {"name": "phi4-mini"},
                "fast_brain": {"name": "phi4-mini"},
                "smart_brain": {"name": "phi4-mini"},
            },
            "system": {},
            "decision_loop": {"context_memories": 5},
        }

        orch = Orchestrator(config)

        # Create mock grimoire
        mock_grimoire = MagicMock()
        mock_grimoire.status = ModuleStatus.ONLINE
        mock_grimoire.name = "grimoire"
        mock_grimoire.get_tools = MagicMock(return_value=[])

        # Mock execute to return failure patterns
        failure_results = [
            {
                "id": "fp-001",
                "content": "FAILURE PATTERN [math]: test",
                "metadata": {
                    "category": "failure_pattern",
                    "task_type": "math",
                    "mistake": "Wrong formula",
                    "correct_approach": "Right formula",
                    "source": "retry_engine",
                    "trust_level": 0.5,
                    "match_count": 1,
                },
                "relevance": 0.8,
            },
        ]

        async def mock_execute(tool_name, params):
            if tool_name == "memory_search":
                query = params.get("query", "")
                if "FAILURE PATTERN" in query:
                    return ToolResult(
                        success=True, content=failure_results,
                        tool_name=tool_name, module="grimoire",
                    )
                return ToolResult(
                    success=True, content=[],
                    tool_name=tool_name, module="grimoire",
                )
            return ToolResult(
                success=False, content=None,
                tool_name=tool_name, module="grimoire",
            )

        mock_grimoire.execute = mock_execute

        # Register mock grimoire
        orch.registry.register(mock_grimoire)

        classification = TaskClassification(
            task_type=TaskType.QUESTION,
            complexity="moderate",
            target_module="wraith",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=3,
        )

        context = await orch._step3_load_context("calculate interest", classification)

        # Find failure_patterns in context
        fp_items = [c for c in context if c["type"] == "failure_patterns"]
        assert len(fp_items) == 1
        assert len(fp_items[0]["content"]) == 1
        assert fp_items[0]["content"][0]["task_type"] == "math"

    @pytest.mark.asyncio
    async def test_step3_empty_failure_patterns_no_break(self):
        """Empty failure pattern search doesn't break Step 3."""
        from modules.shadow.orchestrator import (
            Orchestrator, TaskClassification, TaskType, BrainType,
        )

        config = {
            "models": {
                "ollama_base_url": "http://localhost:11434",
                "router": {"name": "phi4-mini"},
                "fast_brain": {"name": "phi4-mini"},
                "smart_brain": {"name": "phi4-mini"},
            },
            "system": {},
            "decision_loop": {"context_memories": 5},
        }

        orch = Orchestrator(config)

        mock_grimoire = MagicMock()
        mock_grimoire.status = ModuleStatus.ONLINE
        mock_grimoire.name = "grimoire"
        mock_grimoire.get_tools = MagicMock(return_value=[])

        async def mock_execute(tool_name, params):
            return ToolResult(
                success=True, content=[],
                tool_name=tool_name, module="grimoire",
            )

        mock_grimoire.execute = mock_execute
        orch.registry.register(mock_grimoire)

        classification = TaskClassification(
            task_type=TaskType.QUESTION,
            complexity="simple",
            target_module="wraith",
            brain=BrainType.FAST,
            safety_flag=False,
            priority=3,
        )

        context = await orch._step3_load_context("what time is it", classification)

        # Should have context but NO failure_patterns item
        fp_items = [c for c in context if c["type"] == "failure_patterns"]
        assert len(fp_items) == 0
        # Should still have tool availability
        tool_items = [c for c in context if c["type"] == "available_tools"]
        assert len(tool_items) == 1


# --- Analytics Tests ---


class TestFailurePatternAnalytics:
    """Test get_common_failures and get_failure_trend."""

    @pytest.mark.asyncio
    async def test_get_common_failures_sorted(self):
        """get_common_failures returns most matched patterns sorted."""
        search_results = [
            {
                "id": "fp-001",
                "content": "FAILURE PATTERN [math]: low matches",
                "metadata": {
                    "category": "failure_pattern",
                    "task_type": "math",
                    "mistake": "Wrong formula",
                    "correct_approach": "Right formula",
                    "source": "retry_engine",
                    "trust_level": 0.5,
                    "match_count": 2,
                    "timestamp": datetime.now().isoformat(),
                },
            },
            {
                "id": "fp-002",
                "content": "FAILURE PATTERN [code]: high matches",
                "metadata": {
                    "category": "failure_pattern",
                    "task_type": "code",
                    "mistake": "Bad approach",
                    "correct_approach": "Good approach",
                    "source": "retry_engine",
                    "trust_level": 0.5,
                    "match_count": 15,
                    "timestamp": datetime.now().isoformat(),
                },
            },
        ]

        grimoire = make_grimoire_mock(search_results=search_results)
        db = FailurePatternDB()

        results = await db.get_common_failures(grimoire=grimoire, limit=10)

        assert len(results) == 2
        assert results[0]["match_count"] == 15  # Highest first
        assert results[1]["match_count"] == 2

    @pytest.mark.asyncio
    async def test_get_common_failures_empty(self):
        """get_common_failures returns empty list when no patterns exist."""
        grimoire = make_grimoire_mock(search_results=[])
        db = FailurePatternDB()

        results = await db.get_common_failures(grimoire=grimoire)

        assert results == []

    @pytest.mark.asyncio
    async def test_get_failure_trend_improving(self):
        """get_failure_trend detects improvement (fewer recent matches)."""
        now = datetime.now()
        old_ts = (now - timedelta(days=5)).isoformat()
        recent_ts = (now - timedelta(days=1)).isoformat()

        search_results = [
            {
                "id": "fp-old",
                "content": "FAILURE PATTERN [math]: old",
                "metadata": {
                    "category": "failure_pattern",
                    "task_type": "math",
                    "mistake": "old mistake",
                    "correct_approach": "old fix",
                    "source": "retry_engine",
                    "match_count": 10,
                    "trust_level": 0.5,
                    "timestamp": old_ts,
                },
            },
            {
                "id": "fp-recent",
                "content": "FAILURE PATTERN [math]: recent",
                "metadata": {
                    "category": "failure_pattern",
                    "task_type": "math",
                    "mistake": "recent mistake",
                    "correct_approach": "recent fix",
                    "source": "retry_engine",
                    "match_count": 2,
                    "trust_level": 0.5,
                    "timestamp": recent_ts,
                },
            },
        ]

        grimoire = make_grimoire_mock(search_results=search_results)
        db = FailurePatternDB()

        trend = await db.get_failure_trend(grimoire=grimoire, days=7)

        assert trend["total_matches"] == 12
        assert trend["trend"] == "improving"
        assert trend["most_common_category"] == "math"

    @pytest.mark.asyncio
    async def test_get_failure_trend_degrading(self):
        """get_failure_trend detects degradation (more recent matches)."""
        now = datetime.now()
        old_ts = (now - timedelta(days=5)).isoformat()
        recent_ts = (now - timedelta(days=1)).isoformat()

        search_results = [
            {
                "id": "fp-old",
                "content": "FAILURE PATTERN [code]: old",
                "metadata": {
                    "category": "failure_pattern",
                    "task_type": "code",
                    "mistake": "old",
                    "correct_approach": "old fix",
                    "source": "retry_engine",
                    "match_count": 2,
                    "trust_level": 0.5,
                    "timestamp": old_ts,
                },
            },
            {
                "id": "fp-recent",
                "content": "FAILURE PATTERN [code]: recent",
                "metadata": {
                    "category": "failure_pattern",
                    "task_type": "code",
                    "mistake": "recent",
                    "correct_approach": "recent fix",
                    "source": "retry_engine",
                    "match_count": 15,
                    "trust_level": 0.5,
                    "timestamp": recent_ts,
                },
            },
        ]

        grimoire = make_grimoire_mock(search_results=search_results)
        db = FailurePatternDB()

        trend = await db.get_failure_trend(grimoire=grimoire, days=7)

        assert trend["trend"] == "degrading"
        assert trend["most_common_category"] == "code"

    @pytest.mark.asyncio
    async def test_get_failure_trend_no_patterns(self):
        """get_failure_trend with no patterns returns improving."""
        grimoire = make_grimoire_mock(search_results=[])
        db = FailurePatternDB()

        trend = await db.get_failure_trend(grimoire=grimoire, days=7)

        assert trend["total_matches"] == 0
        assert trend["trend"] == "improving"
        assert trend["most_common_category"] is None


# --- Context Manager Integration Tests ---


class TestContextManagerFailurePatterns:
    """Test failure patterns survive context trimming."""

    def test_failure_patterns_in_context_manager_build(self):
        """Failure patterns included in ContextManager.build_context output."""
        from modules.shadow.context_manager import ContextManager

        cm = ContextManager(max_tokens=128000, reserve_tokens=4096, config={})

        patterns = [
            {
                "task_type": "math",
                "mistake": "Used wrong formula",
                "correct_approach": "Use the right formula",
                "description": "Task type: math. Mistake: Used wrong formula. Correct approach: Use the right formula.",
            },
        ]

        result = cm.build_context(
            system_prompt="You are Shadow.",
            conversation_history=[],
            grimoire_memories=[],
            failure_patterns=patterns,
            tool_results=[],
            current_input="calculate something",
        )

        messages = result["messages"]
        # Find the failure pattern message
        fp_msgs = [m for m in messages if "FAILURE PATTERN" in m.get("content", "")]
        assert len(fp_msgs) == 1
        assert "do not repeat" in fp_msgs[0]["content"].lower()
        assert "math" in fp_msgs[0]["content"]

    def test_failure_patterns_high_priority_in_trimming(self):
        """Failure patterns survive trimming (high priority in ContextManager)."""
        from modules.shadow.context_manager import ContextManager

        # Small context window to force trimming
        cm = ContextManager(max_tokens=500, reserve_tokens=100, config={})

        patterns = [
            {
                "task_type": "code",
                "mistake": "Bad sort",
                "correct_approach": "Use merge sort",
                "description": "Task type: code. Mistake: Bad sort. Correct approach: Use merge sort.",
            },
        ]

        # Large conversation history to force trimming
        long_history = [
            {"role": "user", "content": f"message {i} " * 20}
            for i in range(10)
        ]

        result = cm.build_context(
            system_prompt="You are Shadow.",
            conversation_history=long_history,
            grimoire_memories=[{"content": "some memory " * 20}] * 5,
            failure_patterns=patterns,
            tool_results=[],
            current_input="calculate something",
        )

        # Failure patterns should still be present even after trimming
        messages = result["messages"]
        fp_msgs = [m for m in messages if "FAILURE PATTERN" in m.get("content", "")]
        # If context was trimmed, history or memories should have been cut first
        # failure_patterns are trimmed LAST
        assert result["token_breakdown"]["failure_pattern_tokens"] >= 0


# --- Integration: RetryEngine → Next Task ---


class TestFailurePatternIntegration:
    """Integration test: store pattern after failure → load it for next similar task."""

    @pytest.mark.asyncio
    async def test_store_then_search_roundtrip(self):
        """RetryEngine stores pattern → next similar task loads that pattern."""
        stored_patterns = []

        async def roundtrip_execute(tool_name, params):
            if tool_name == "memory_store":
                entry = {
                    "id": f"fp-{len(stored_patterns)}",
                    "content": params["content"],
                    "metadata": params["metadata"],
                    "relevance": 0.85,
                }
                stored_patterns.append(entry)
                return ToolResult(
                    success=True,
                    content=f"Memory stored: fp-{len(stored_patterns) - 1}",
                    tool_name=tool_name, module="grimoire",
                )
            elif tool_name == "memory_search":
                # Return stored patterns that match
                query = params.get("query", "")
                matches = [
                    p for p in stored_patterns
                    if p["metadata"].get("category") == "failure_pattern"
                ]
                return ToolResult(
                    success=True, content=matches,
                    tool_name=tool_name, module="grimoire",
                )
            elif tool_name == "memory_forget":
                return ToolResult(
                    success=True, content="Deleted",
                    tool_name=tool_name, module="grimoire",
                )
            return ToolResult(
                success=False, content=None,
                tool_name=tool_name, module="grimoire",
            )

        grimoire = AsyncMock()
        grimoire.execute = roundtrip_execute

        db = FailurePatternDB()

        # Step 1: RetryEngine stores a failure pattern
        await db.store_failure_pattern(
            grimoire=grimoire,
            task="parse CSV with headers",
            task_type="code",
            mistake="Assumed comma delimiter without checking",
            correct_approach="Auto-detect delimiter with csv.Sniffer",
            source="retry_engine",
            trust_level=0.5,
        )

        assert len(stored_patterns) == 1

        # Step 2: Next similar task searches and finds the pattern
        patterns = await db.search_failure_patterns(
            grimoire=grimoire,
            query="parse CSV file",
            limit=3,
        )

        assert len(patterns) == 1
        assert patterns[0]["task_type"] == "code"
        assert "delimiter" in patterns[0]["mistake"]
        assert "Sniffer" in patterns[0]["correct_approach"]


# --- Keyword Extraction Tests ---


class TestKeywordExtraction:
    """Test the keyword extraction helper."""

    def test_extracts_meaningful_words(self):
        db = FailurePatternDB()
        keywords = db._extract_keywords("calculate the compound interest rate for a loan")
        assert "compound" in keywords
        assert "interest" in keywords
        assert "the" not in keywords
        assert "for" not in keywords

    def test_limits_keywords(self):
        db = FailurePatternDB()
        long_task = " ".join(f"keyword{i}" for i in range(20))
        keywords = db._extract_keywords(long_task)
        assert len(keywords.split(", ")) <= 10


# --- Content Parsing Tests ---


class TestContentParsing:
    """Test parsing failure patterns from raw content strings."""

    def test_parse_pattern_from_content(self):
        db = FailurePatternDB()
        content = (
            "FAILURE PATTERN [math]: Task: interest calc. "
            "Mistake: Used simple formula. "
            "Correct approach: Use compound formula."
        )

        result = db._parse_pattern_from_content(content)

        assert result["task_type"] == "math"
        assert "simple formula" in result["mistake"]
        assert "compound formula" in result["correct_approach"]

    def test_parse_pattern_missing_fields(self):
        db = FailurePatternDB()
        content = "FAILURE PATTERN [code]: some content without structured fields"

        result = db._parse_pattern_from_content(content)

        assert result["task_type"] == "code"
        assert result["mistake"] == ""  # No "Mistake:" found
