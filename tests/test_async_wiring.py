"""
Async Task Queue Wiring Tests
================================
Integration tests verifying the AsyncTaskQueue is properly wired into
the orchestrator startup path and the CLI command handlers.

Covers:
  (a) AsyncTaskQueue starts during orchestrator/startup init
  (b) Background-flagged tasks get submitted to queue, not executed inline
  (c) /tasks command returns the task list from the live queue
  (d) Submitted tasks eventually complete via the worker loop
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.base import BaseModule, ModuleRegistry, ModuleStatus, ToolResult
from modules.shadow.async_tasks import AsyncTaskQueue
from modules.shadow.task_queue import PriorityTaskQueue
from modules.shadow.task_tracker import TaskTracker


# ===================================================================
# Mock Module
# ===================================================================

class _MockModule(BaseModule):
    """Controllable mock module for wiring tests."""

    def __init__(self, name: str = "reaper", tools: list[str] | None = None):
        super().__init__(name=name, description=f"Mock {name}")
        self._tools = tools or ["web_search"]
        self.calls: list[tuple[str, dict]] = []
        self._delay: float = 0.0

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        self.calls.append((tool_name, params))
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        return ToolResult(
            success=True,
            content={"echo": params},
            tool_name=tool_name,
            module=self.name,
        )

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [{"name": t, "description": f"Mock {t}"} for t in self._tools]


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def task_queue(tmp_path: Path) -> PriorityTaskQueue:
    q = PriorityTaskQueue(persist_path=tmp_path / "queue.json")
    q.initialize()
    return q


@pytest.fixture
def task_tracker(tmp_path: Path) -> TaskTracker:
    t = TaskTracker(db_path=tmp_path / "tasks.db")
    t.initialize()
    yield t
    t.close()


@pytest.fixture
def mock_module() -> _MockModule:
    return _MockModule(name="reaper", tools=["web_search", "web_scrape"])


@pytest.fixture
def registry(mock_module: _MockModule) -> ModuleRegistry:
    reg = ModuleRegistry()
    reg.register(mock_module)
    return reg


@pytest.fixture
async def async_queue(
    task_queue: PriorityTaskQueue,
    task_tracker: TaskTracker,
    registry: ModuleRegistry,
) -> AsyncTaskQueue:
    aq = AsyncTaskQueue(task_queue, task_tracker, registry)
    await aq.start()
    yield aq
    await aq.stop()


# ===================================================================
# (a) AsyncTaskQueue starts on orchestrator init
# ===================================================================

class TestAsyncQueueStartsOnInit:
    """Verify the startup() path in main.py initializes the ATQ."""

    async def test_orchestrator_has_async_task_queue_after_startup(self, tmp_path: Path):
        """After main.startup(), orchestrator.async_task_queue should not be None."""
        # Build a minimal config that satisfies Orchestrator.__init__
        config = _minimal_config(tmp_path)

        # Patch heavy dependencies so we don't need Ollama or real modules
        with patch("modules.shadow.orchestrator.httpx.Client"):
            from modules.shadow.orchestrator import Orchestrator

            orch = Orchestrator(config)

        # Register a mock module so the registry isn't empty
        mock = _MockModule("reaper", ["web_search"])
        await mock.initialize()
        orch.registry.register(mock)

        # Simulate the main.py startup path: init tracker → queue → ATQ
        orch._task_tracker.initialize()
        if orch._task_queue is not None:
            orch._task_queue.initialize()

        orch._async_task_queue = AsyncTaskQueue(
            task_queue=orch._task_queue,
            task_tracker=orch._task_tracker,
            registry=orch.registry,
        )
        await orch._async_task_queue.start()

        try:
            assert orch.async_task_queue is not None
            assert orch._async_task_queue._worker_task is not None
            assert not orch._async_task_queue._shutdown
        finally:
            await orch._async_task_queue.stop()
            orch._task_tracker.close()

    async def test_async_task_queue_property_accessible(
        self, task_queue, task_tracker, registry
    ):
        """The async_task_queue property should expose the running ATQ."""
        # Simulate what main.py now does
        atq = AsyncTaskQueue(task_queue, task_tracker, registry)
        await atq.start()

        try:
            assert atq._worker_task is not None
            assert atq._worker_task.get_name() == "async-task-worker"
        finally:
            await atq.stop()


# ===================================================================
# (b) Background-flagged tasks get submitted, not executed inline
# ===================================================================

class TestBackgroundSubmission:
    """Verify _should_run_async returns True and task is routed to queue."""

    async def test_should_run_async_with_background_flag(self, tmp_path: Path):
        """_should_run_async returns True when _background param is set."""
        config = _minimal_config(tmp_path)

        with patch("modules.shadow.orchestrator.httpx.Client"):
            from modules.shadow.orchestrator import Orchestrator

            orch = Orchestrator(config)

        # ATQ must exist for _should_run_async to return True
        orch._task_tracker.initialize()
        if orch._task_queue is not None:
            orch._task_queue.initialize()

        mock = _MockModule("reaper", ["web_search"])
        await mock.initialize()
        orch.registry.register(mock)

        orch._async_task_queue = AsyncTaskQueue(
            task_queue=orch._task_queue,
            task_tracker=orch._task_tracker,
            registry=orch.registry,
        )
        await orch._async_task_queue.start()

        try:
            classification = MagicMock()
            classification.priority = 2

            # Background flag triggers async
            result = orch._should_run_async(
                "web_search", {"_background": True}, classification
            )
            assert result is True

            # Without flag and low priority, known long-running tool still triggers
            result = orch._should_run_async(
                "web_search", {}, classification
            )
            assert result is True  # web_search is in _LONG_RUNNING_TOOLS
        finally:
            await orch._async_task_queue.stop()
            orch._task_tracker.close()

    async def test_should_run_async_false_without_queue(self, tmp_path: Path):
        """_should_run_async returns False when ATQ is None."""
        config = _minimal_config(tmp_path)

        with patch("modules.shadow.orchestrator.httpx.Client"):
            from modules.shadow.orchestrator import Orchestrator

            orch = Orchestrator(config)

        classification = MagicMock()
        classification.priority = 4

        assert orch._should_run_async("web_search", {"_background": True}, classification) is False
        orch._task_tracker.close()

    async def test_submit_task_returns_id_immediately(
        self, async_queue: AsyncTaskQueue
    ):
        """submit_task() returns a task ID without blocking on execution."""
        task_id = async_queue.submit_task(
            module_name="reaper",
            tool_name="web_search",
            params={"query": "background test"},
            description="Background: web_search",
        )
        assert task_id is not None
        assert isinstance(task_id, str)
        assert len(task_id) > 8


# ===================================================================
# (c) /tasks returns task list from the live queue
# ===================================================================

class TestTasksCommand:
    """Verify /tasks CLI command connects to the live ATQ."""

    async def test_tasks_command_shows_live_tasks(self, async_queue, capsys):
        """Submit a task, then verify /tasks shows it."""
        from main import handle_command

        # Use a slow mock so task stays active
        slow = _MockModule("reaper", ["web_search", "web_scrape"])
        slow._delay = 5.0
        slow_reg = ModuleRegistry()
        slow_reg.register(slow)
        async_queue._registry = slow_reg

        async_queue.submit_task("reaper", "web_search", {"q": "live"})
        await asyncio.sleep(0.1)

        # Build orchestrator mock pointing to the live ATQ
        orch = MagicMock()
        orch.async_task_queue = async_queue

        result = await handle_command("/tasks", orch)
        assert result is True
        captured = capsys.readouterr()
        assert "Active Tasks" in captured.out

    async def test_tasks_command_empty_queue(self, async_queue, capsys):
        """When no tasks are active, /tasks says so."""
        from main import handle_command

        orch = MagicMock()
        orch.async_task_queue = async_queue

        result = await handle_command("/tasks", orch)
        assert result is True
        captured = capsys.readouterr()
        assert "No active background tasks" in captured.out


# ===================================================================
# (d) Submitted task eventually completes
# ===================================================================

class TestTaskCompletion:
    """Verify that submitted tasks are processed by the worker."""

    async def test_submitted_task_completes(
        self, async_queue: AsyncTaskQueue, mock_module: _MockModule
    ):
        """A submitted task should reach 'completed' status."""
        task_id = async_queue.submit_task(
            "reaper", "web_search", {"query": "complete_me"}
        )

        for _ in range(50):
            await asyncio.sleep(0.05)
            if async_queue.get_status(task_id) == "completed":
                break

        assert async_queue.get_status(task_id) == "completed"
        assert len(mock_module.calls) == 1
        assert mock_module.calls[0] == ("web_search", {"query": "complete_me"})

    async def test_completed_task_has_result(
        self, async_queue: AsyncTaskQueue, mock_module: _MockModule
    ):
        """A completed task should have a retrievable result."""
        task_id = async_queue.submit_task(
            "reaper", "web_search", {"query": "result_check"}
        )

        for _ in range(50):
            await asyncio.sleep(0.05)
            if async_queue.get_status(task_id) == "completed":
                break

        result = async_queue.get_result(task_id)
        assert result is not None
        assert result["success"] is True
        assert result["tool_name"] == "web_search"

    async def test_task_status_via_cli_after_completion(
        self, async_queue: AsyncTaskQueue, mock_module: _MockModule, capsys
    ):
        """/task <id> shows completed status after worker finishes."""
        from main import handle_command

        task_id = async_queue.submit_task(
            "reaper", "web_search", {"query": "cli_check"}
        )

        for _ in range(50):
            await asyncio.sleep(0.05)
            if async_queue.get_status(task_id) == "completed":
                break

        orch = MagicMock()
        orch.async_task_queue = async_queue

        result = await handle_command(f"/task {task_id[:8]}", orch)
        assert result is True
        captured = capsys.readouterr()
        assert "completed" in captured.out


# ===================================================================
# (e) Background intent detection — request vs retrieval
# ===================================================================

class TestBackgroundIntentDetection:
    """Verify _detect_background_intent distinguishes new requests from
    retrieval queries about past background work."""

    @pytest.fixture
    def orch(self, tmp_path: Path):
        """Minimal Orchestrator for testing static detection method."""
        config = _minimal_config(tmp_path)
        with patch("modules.shadow.orchestrator.httpx.Client"):
            from modules.shadow.orchestrator import Orchestrator
            o = Orchestrator(config)
        yield o
        o._task_tracker.close()

    def test_imperative_request_triggers_async(self, orch):
        """'search for X in the background' should trigger async."""
        assert orch._detect_background_intent(
            "search for Python tutorials in the background"
        ) is True

    def test_when_you_get_a_chance_triggers_async(self, orch):
        """'when you get a chance' should trigger async."""
        assert orch._detect_background_intent(
            "look up landscaping prices when you get a chance"
        ) is True

    def test_no_rush_triggers_async(self, orch):
        """'no rush' should trigger async."""
        assert orch._detect_background_intent(
            "find me some mulch suppliers, no rush"
        ) is True

    def test_results_query_does_not_trigger_async(self, orch):
        """'what were the results from the background task?' → NOT async."""
        assert orch._detect_background_intent(
            "what were the results from the background task?"
        ) is False

    def test_show_me_what_you_found_does_not_trigger_async(self, orch):
        """'show me what you found in the background' → NOT async."""
        assert orch._detect_background_intent(
            "show me what you found in the background"
        ) is False

    def test_what_are_the_results_does_not_trigger_async(self, orch):
        """'what are the results of the background research?' → NOT async."""
        assert orch._detect_background_intent(
            "what are the results of the background research?"
        ) is False

    def test_that_you_ran_does_not_trigger_async(self, orch):
        """'what are the research results that you ran in the background?' → NOT async."""
        assert orch._detect_background_intent(
            "what are the research results that you ran in the background?"
        ) is False

    def test_what_did_background_task_find_does_not_trigger_async(self, orch):
        """'what did the background task find?' → NOT async."""
        assert orch._detect_background_intent(
            "what did the background task find?"
        ) is False

    def test_no_background_phrase_returns_false(self, orch):
        """Input without any background phrase should return False."""
        assert orch._detect_background_intent(
            "search for Python tutorials"
        ) is False

    def test_status_of_background_does_not_trigger_async(self, orch):
        """'status of the background task' → NOT async."""
        assert orch._detect_background_intent(
            "what's the status of the background task?"
        ) is False


# ===================================================================
# (f) Benchmark source forces synchronous execution
# ===================================================================

class TestBenchmarkForcesSync:
    """Verify that source='benchmark' bypasses async queuing so the
    orchestrator waits for tool results before scoring the response."""

    async def test_should_run_async_false_for_benchmark_source(self, tmp_path: Path):
        """_should_run_async returns False for source='benchmark' even when
        the tool is in _LONG_RUNNING_TOOLS."""
        config = _minimal_config(tmp_path)

        with patch("modules.shadow.orchestrator.httpx.Client"):
            from modules.shadow.orchestrator import Orchestrator

            orch = Orchestrator(config)

        # ATQ must exist (normally it would trigger async)
        orch._task_tracker.initialize()
        if orch._task_queue is not None:
            orch._task_queue.initialize()

        mock = _MockModule("reaper", ["web_search"])
        await mock.initialize()
        orch.registry.register(mock)

        orch._async_task_queue = AsyncTaskQueue(
            task_queue=orch._task_queue,
            task_tracker=orch._task_tracker,
            registry=orch.registry,
        )
        await orch._async_task_queue.start()

        try:
            classification = MagicMock()
            classification.priority = 2

            # web_search + source="benchmark" → must be synchronous
            result = orch._should_run_async(
                "web_search", {}, classification, source="benchmark"
            )
            assert result is False

            # Same tool + source="user" → still async (control)
            result = orch._should_run_async(
                "web_search", {}, classification, source="user"
            )
            assert result is True
        finally:
            await orch._async_task_queue.stop()
            orch._task_tracker.close()

    async def test_should_run_async_false_for_benchmark_even_with_background_flag(
        self, tmp_path: Path
    ):
        """Even an explicit _background=True is overridden by benchmark source."""
        config = _minimal_config(tmp_path)

        with patch("modules.shadow.orchestrator.httpx.Client"):
            from modules.shadow.orchestrator import Orchestrator

            orch = Orchestrator(config)

        orch._task_tracker.initialize()
        if orch._task_queue is not None:
            orch._task_queue.initialize()

        mock = _MockModule("reaper", ["web_search"])
        await mock.initialize()
        orch.registry.register(mock)

        orch._async_task_queue = AsyncTaskQueue(
            task_queue=orch._task_queue,
            task_tracker=orch._task_tracker,
            registry=orch.registry,
        )
        await orch._async_task_queue.start()

        try:
            classification = MagicMock()
            classification.priority = 4  # background priority

            # benchmark overrides both _background flag and priority >= 4
            result = orch._should_run_async(
                "web_search", {"_background": True}, classification,
                source="benchmark",
            )
            assert result is False
        finally:
            await orch._async_task_queue.stop()
            orch._task_tracker.close()

    async def test_synchronous_sources_set_contains_benchmark(self):
        """Sanity check: 'benchmark' is in _SYNCHRONOUS_SOURCES."""
        from modules.shadow.orchestrator import Orchestrator

        assert "benchmark" in Orchestrator._SYNCHRONOUS_SOURCES

    async def test_step5_execute_runs_sync_for_benchmark(self, tmp_path: Path):
        """When source='benchmark', _step5_execute runs tools inline
        instead of submitting to the async queue."""
        config = _minimal_config(tmp_path)

        with patch("modules.shadow.orchestrator.httpx.Client"):
            from modules.shadow.orchestrator import Orchestrator

            orch = Orchestrator(config)

        orch._task_tracker.initialize()
        if orch._task_queue is not None:
            orch._task_queue.initialize()

        mock = _MockModule("reaper", ["web_search"])
        await mock.initialize()
        orch.registry.register(mock)

        orch._async_task_queue = AsyncTaskQueue(
            task_queue=orch._task_queue,
            task_tracker=orch._task_tracker,
            registry=orch.registry,
        )
        await orch._async_task_queue.start()

        try:
            from modules.shadow.orchestrator import (
                ExecutionPlan,
                TaskClassification,
                TaskType,
                BrainType,
            )

            classification = TaskClassification(
                task_type=TaskType.RESEARCH,
                complexity="moderate",
                target_module="reaper",
                brain=BrainType.SMART,
                safety_flag=False,
                priority=3,
                confidence=0.85,
            )

            plan = ExecutionPlan(
                steps=[
                    {
                        "step": 1,
                        "description": "Search for information",
                        "tool": "web_search",
                        "params": {"query": "benchmark sync test"},
                    }
                ],
                cerberus_approved=True,
            )

            results = await orch._step5_execute(
                plan, classification, source="benchmark"
            )

            # Results should contain actual tool output, NOT a task-submitted message
            assert len(results) >= 1
            assert results[0].success is True
            # The content should be the mock module's echo, not a task ID message
            assert "Task submitted" not in str(results[0].content)
            assert mock.calls, "Mock module should have been called inline"
        finally:
            await orch._async_task_queue.stop()
            orch._task_tracker.close()


# ===================================================================
# Helper
# ===================================================================

def _minimal_config(tmp_path: Path) -> dict:
    """Build a minimal config dict that satisfies Orchestrator.__init__."""
    return {
        "models": {
            "ollama_base_url": "http://localhost:11434",
            "router": {"name": "phi4-mini"},
            "fast_brain": {"name": "phi4-mini"},
            "smart_brain": {"name": "phi4-mini"},
        },
        "system": {
            "state_file": str(tmp_path / "state.json"),
            "task_db": str(tmp_path / "tasks.db"),
            "queue_file": str(tmp_path / "queue.json"),
            "data_dir": str(tmp_path),
        },
        "modules": {},
    }
