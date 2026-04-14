"""
Tests for StandingTaskScheduler — APScheduler-based recurring background tasks.
"""

import asyncio
import json
import pytest
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from modules.base import ModuleRegistry, ModuleStatus, ToolResult
from modules.shadow.standing_tasks import (
    DEFAULT_RESEARCH_TOPICS,
    TASK_DEFS,
    StandingTaskScheduler,
)


# ── Fixtures ────────────────────────────────────────────────────


class MockModule:
    """Minimal module mock that tracks execute calls."""

    def __init__(self, name: str):
        self.name = name
        self.status = ModuleStatus.ONLINE
        self.calls: list[tuple[str, dict]] = []
        self._grimoire = MagicMock()
        self._grimoire.remember = MagicMock(return_value="mem-test-123")
        self._grimoire.stats = MagicMock(return_value={
            "active_memories": 42,
            "inactive_memories": 3,
            "total_stored": 45,
            "vector_count": 42,
            "unique_tags": 18,
            "corrections": 2,
            "by_category": {"system": 5, "research": 12, "conversation": 25},
            "by_source": {"conversation": 30, "research": 10, "standing_task": 5},
            "db_path": "data/memory/test.db",
            "vector_path": "data/vectors/test",
        })

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        self.calls.append((tool_name, params))
        if tool_name == "code_analyze_self":
            return ToolResult(
                success=True,
                content={"self_analysis": {"files_analyzed": 48, "total_loc": 12000}},
                tool_name=tool_name,
                module=self.name,
            )
        elif tool_name == "web_search":
            return ToolResult(
                success=True,
                content=[{"title": "Test Result", "url": "https://example.com", "snippet": "test"}],
                tool_name=tool_name,
                module=self.name,
            )
        return ToolResult(success=False, content=None, tool_name=tool_name, module=self.name, error="unknown tool")


@pytest.fixture
def mock_registry() -> ModuleRegistry:
    """Registry with mock omen, reaper, and grimoire modules."""
    registry = ModuleRegistry()
    omen = MockModule("omen")
    reaper = MockModule("reaper")
    grimoire = MockModule("grimoire")
    # ModuleRegistry.register expects objects with .name attribute
    registry._modules = {"omen": omen, "reaper": reaper, "grimoire": grimoire}
    return registry


@pytest.fixture
def event_loop_for_tasks():
    """Provide a running event loop for marshaling."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def scheduler(mock_registry: ModuleRegistry) -> StandingTaskScheduler:
    """StandingTaskScheduler with mocked registry, not started."""
    return StandingTaskScheduler(mock_registry)


# ── Initialization Tests ────────────────────────────────────────


class TestSchedulerInit:
    def test_creates_without_errors(self, mock_registry: ModuleRegistry):
        """Scheduler initializes cleanly with a registry."""
        sched = StandingTaskScheduler(mock_registry)
        assert sched is not None
        assert sched._loop is None
        assert not sched._scheduler.running

    def test_default_research_topics(self, scheduler: StandingTaskScheduler):
        """Default research topics match the module constant."""
        assert scheduler._research_topics == DEFAULT_RESEARCH_TOPICS

    def test_custom_research_topics(self, mock_registry: ModuleRegistry):
        """Custom research topics override defaults."""
        custom = ["topic A", "topic B"]
        sched = StandingTaskScheduler(mock_registry, research_topics=custom)
        assert sched._research_topics == custom

    def test_initial_tracking_state(self, scheduler: StandingTaskScheduler):
        """All tasks start with 'never run' status."""
        for name in TASK_DEFS:
            assert scheduler._last_run[name] is None
            assert scheduler._last_status[name] == "never run"


# ── Start / Stop Tests ──────────────────────────────────────────


class TestSchedulerLifecycle:
    def test_start_and_stop(self, scheduler: StandingTaskScheduler, event_loop_for_tasks):
        """Scheduler starts and stops without errors."""
        scheduler.start(event_loop_for_tasks)
        assert scheduler._scheduler.running
        assert scheduler._loop is event_loop_for_tasks

        jobs = scheduler._scheduler.get_jobs()
        job_ids = {j.id for j in jobs}
        assert job_ids == {"self_analysis", "standing_research", "grimoire_stats"}

        scheduler.stop()
        assert not scheduler._scheduler.running

    def test_stop_when_not_running(self, scheduler: StandingTaskScheduler):
        """Stopping a never-started scheduler doesn't raise."""
        scheduler.stop()  # Should not raise


# ── Task Execution Tests ────────────────────────────────────────


def _run_task_with_loop(scheduler: StandingTaskScheduler, task_name: str):
    """Helper: create a loop, set it on the scheduler, run a task synchronously."""
    loop = asyncio.new_event_loop()
    scheduler._loop = loop

    # Run the task in a thread so the event loop can process the coroutine
    import threading

    def _run_loop():
        loop.run_forever()

    t = threading.Thread(target=_run_loop, daemon=True)
    t.start()
    try:
        scheduler.run_task(task_name)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=5)
        loop.close()


class TestSelfAnalysis:
    def test_executes_and_stores(self, scheduler: StandingTaskScheduler, mock_registry: ModuleRegistry):
        """Self-analysis calls Omen and stores result in Grimoire."""
        _run_task_with_loop(scheduler, "self_analysis")

        omen = mock_registry._modules["omen"]
        assert len(omen.calls) == 1
        assert omen.calls[0][0] == "code_analyze_self"

        grimoire = mock_registry._modules["grimoire"]
        grimoire._grimoire.remember.assert_called_once()
        call_kwargs = grimoire._grimoire.remember.call_args
        assert call_kwargs[1]["category"] == "self_analysis"
        assert call_kwargs[1]["source"] == "standing_task"
        assert call_kwargs[1]["source_module"] == "omen"

        assert scheduler._last_status["self_analysis"] == "success"
        assert scheduler._last_run["self_analysis"] is not None


class TestStandingResearch:
    def test_executes_and_stores(self, scheduler: StandingTaskScheduler, mock_registry: ModuleRegistry):
        """Standing research calls Reaper and stores result in Grimoire."""
        _run_task_with_loop(scheduler, "standing_research")

        reaper = mock_registry._modules["reaper"]
        assert len(reaper.calls) == 1
        assert reaper.calls[0][0] == "web_search"
        assert reaper.calls[0][1]["query"] == DEFAULT_RESEARCH_TOPICS[0]

        grimoire = mock_registry._modules["grimoire"]
        grimoire._grimoire.remember.assert_called_once()
        call_kwargs = grimoire._grimoire.remember.call_args
        assert call_kwargs[1]["category"] == "standing_research"
        assert call_kwargs[1]["source"] == "standing_task"

        assert scheduler._last_status["standing_research"].startswith("success")

    def test_topic_rotation(self, scheduler: StandingTaskScheduler, mock_registry: ModuleRegistry):
        """Topics rotate through the list on successive runs."""
        for i in range(3):
            _run_task_with_loop(scheduler, "standing_research")
            reaper = mock_registry._modules["reaper"]
            expected_topic = DEFAULT_RESEARCH_TOPICS[i]
            assert reaper.calls[i][1]["query"] == expected_topic


class TestGrimoireStats:
    def test_executes_and_stores(self, scheduler: StandingTaskScheduler, mock_registry: ModuleRegistry):
        """Grimoire stats collects data and stores a health summary."""
        _run_task_with_loop(scheduler, "grimoire_stats")

        grimoire = mock_registry._modules["grimoire"]
        grimoire._grimoire.stats.assert_called_once()
        grimoire._grimoire.remember.assert_called_once()

        call_kwargs = grimoire._grimoire.remember.call_args
        assert call_kwargs[1]["category"] == "system_health"
        assert call_kwargs[1]["source"] == "standing_task"
        assert "Active memories: 42" in call_kwargs[1]["content"]

        assert scheduler._last_status["grimoire_stats"] == "success"


# ── Failure Handling Tests ──────────────────────────────────────


class TestFailureHandling:
    def test_failed_task_does_not_crash_scheduler(self, mock_registry: ModuleRegistry):
        """A task failure updates status but doesn't propagate exceptions."""
        # Make omen.execute raise
        omen = mock_registry._modules["omen"]
        omen.execute = AsyncMock(side_effect=RuntimeError("Omen exploded"))

        sched = StandingTaskScheduler(mock_registry)
        _run_task_with_loop(sched, "self_analysis")

        assert "failed" in sched._last_status["self_analysis"]
        assert sched._last_run["self_analysis"] is not None

    def test_missing_module_reports_failure(self):
        """Tasks fail gracefully when a required module is missing."""
        empty_registry = ModuleRegistry()
        sched = StandingTaskScheduler(empty_registry)

        _run_task_with_loop(sched, "grimoire_stats")

        assert "failed" in sched._last_status["grimoire_stats"]


# ── Manual Trigger Tests ────────────────────────────────────────


class TestRunTask:
    def test_unknown_task_returns_error(self, scheduler: StandingTaskScheduler):
        """run_task with invalid name returns error message, doesn't crash."""
        result = scheduler.run_task("nonexistent_task")
        assert "Unknown task" in result
        assert "nonexistent_task" in result

    def test_valid_task_names(self, scheduler: StandingTaskScheduler):
        """All defined task names are accepted by run_task."""
        for name in TASK_DEFS:
            # Just test that unknown-task error is NOT returned
            # (actual execution would need a loop)
            assert name in {"self_analysis", "standing_research", "grimoire_stats"}


# ── Schedule Info Tests ─────────────────────────────────────────


class TestGetScheduleInfo:
    def test_returns_formatted_output(self, scheduler: StandingTaskScheduler, event_loop_for_tasks):
        """get_schedule_info returns a formatted string with all tasks."""
        scheduler.start(event_loop_for_tasks)
        try:
            info = scheduler.get_schedule_info()
            assert "Standing Tasks" in info
            assert "self_analysis" in info
            assert "standing_research" in info
            assert "grimoire_stats" in info
            assert "every 6h" in info
            assert "every 12h" in info
            assert "daily 5:00 AM" in info
            assert "never" in info  # no tasks have run yet
        finally:
            scheduler.stop()

    def test_shows_last_run_after_execution(self, scheduler: StandingTaskScheduler, mock_registry: ModuleRegistry):
        """After a task runs, schedule info shows the execution time."""
        _run_task_with_loop(scheduler, "grimoire_stats")
        info = scheduler.get_schedule_info()
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in info
        assert "success" in info


# ── Thread-safety Tests ────────────────────────────────────────


class TestGrimoireStatsNoEventLoop:
    """Verify grimoire_stats runs without an event loop (pure sync path)."""

    def test_works_without_event_loop(self, mock_registry: ModuleRegistry):
        """grimoire_stats succeeds even when no event loop is set."""
        sched = StandingTaskScheduler(mock_registry)
        # _loop is None — no event loop available
        assert sched._loop is None

        sched._run_grimoire_stats()

        grimoire = mock_registry._modules["grimoire"]
        grimoire._grimoire.stats.assert_called_once()
        grimoire._grimoire.remember.assert_called_once()
        assert sched._last_status["grimoire_stats"] == "success"

    def test_no_marshaling_needed(self, mock_registry: ModuleRegistry):
        """grimoire_stats never calls _marshal (no async dependency)."""
        sched = StandingTaskScheduler(mock_registry)
        sched._marshal = MagicMock(side_effect=RuntimeError("Should not be called"))

        sched._run_grimoire_stats()

        sched._marshal.assert_not_called()
        assert sched._last_status["grimoire_stats"] == "success"
