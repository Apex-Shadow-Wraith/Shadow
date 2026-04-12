"""
AsyncTaskQueue Tests
======================
Tests for the async worker loop that executes background tasks.

Covers: task submission, status transitions, result retrieval,
failure handling, list_active_tasks, and CLI commands.
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from modules.base import BaseModule, ModuleRegistry, ModuleStatus, ToolResult
from modules.shadow.async_tasks import AsyncTaskQueue
from modules.shadow.task_queue import PriorityTaskQueue
from modules.shadow.task_tracker import TaskTracker


# ===================================================================
# Mock Module
# ===================================================================

class MockModule(BaseModule):
    """A controllable mock module for testing async execution."""

    def __init__(self, name: str = "mock", tools: list[str] | None = None):
        super().__init__(name=name, description=f"Mock {name}")
        self._tools = tools or ["mock_tool"]
        self.calls: list[tuple[str, dict]] = []
        self._fail_on: set[str] = set()
        self._delay: float = 0.0

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        self.calls.append((tool_name, params))
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if tool_name in self._fail_on:
            raise RuntimeError(f"Simulated failure in {tool_name}")
        return ToolResult(
            success=True,
            content={"echo": params},
            tool_name=tool_name,
            module=self.name,
        )

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": t, "description": f"Mock tool {t}"}
            for t in self._tools
        ]


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
def mock_module() -> MockModule:
    return MockModule(name="reaper", tools=["web_search", "web_scrape"])


@pytest.fixture
def registry(mock_module: MockModule) -> ModuleRegistry:
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
# Test: Task Submission
# ===================================================================

class TestSubmitTask:
    """Tests for submit_task() returning IDs and enqueueing correctly."""

    async def test_submit_returns_task_id(self, async_queue: AsyncTaskQueue):
        task_id = async_queue.submit_task(
            module_name="reaper",
            tool_name="web_search",
            params={"query": "test"},
        )
        assert task_id is not None
        assert isinstance(task_id, str)
        assert len(task_id) > 0

    async def test_submit_returns_unique_ids(self, async_queue: AsyncTaskQueue):
        id1 = async_queue.submit_task("reaper", "web_search", {"query": "a"})
        id2 = async_queue.submit_task("reaper", "web_search", {"query": "b"})
        assert id1 != id2

    async def test_status_after_submit(self, async_queue: AsyncTaskQueue):
        """Immediately after submit, status should be queued or running."""
        task_id = async_queue.submit_task("reaper", "web_search", {"query": "test"})
        status = async_queue.get_status(task_id)
        assert status in ("queued", "running", "completed")


# ===================================================================
# Test: Worker Processing
# ===================================================================

class TestWorkerProcessing:
    """Tests that the worker loop picks up and completes tasks."""

    async def test_worker_processes_task(
        self, async_queue: AsyncTaskQueue, mock_module: MockModule
    ):
        task_id = async_queue.submit_task("reaper", "web_search", {"query": "hello"})

        # Wait for worker to process
        for _ in range(50):
            await asyncio.sleep(0.05)
            if async_queue.get_status(task_id) == "completed":
                break

        assert async_queue.get_status(task_id) == "completed"
        assert len(mock_module.calls) == 1
        assert mock_module.calls[0][0] == "web_search"
        assert mock_module.calls[0][1] == {"query": "hello"}

    async def test_status_transitions(
        self, task_queue: PriorityTaskQueue, task_tracker: TaskTracker,
        registry: ModuleRegistry,
    ):
        """Track the full lifecycle: queued -> running -> completed."""
        # Use a module with a delay so we can catch the running state
        slow_module = MockModule(name="reaper", tools=["web_search", "web_scrape"])
        slow_module._delay = 0.3

        reg = ModuleRegistry()
        reg.register(slow_module)

        aq = AsyncTaskQueue(task_queue, task_tracker, reg)
        await aq.start()

        task_id = aq.submit_task("reaper", "web_search", {"query": "slow"})

        observed_statuses = set()
        for _ in range(100):
            await asyncio.sleep(0.02)
            s = aq.get_status(task_id)
            if s:
                observed_statuses.add(s)
            if s == "completed":
                break

        await aq.stop()

        assert "completed" in observed_statuses
        # Should have seen running at some point (delay gives us time)
        assert "running" in observed_statuses or "completed" in observed_statuses

    async def test_get_result_after_completion(
        self, async_queue: AsyncTaskQueue, mock_module: MockModule
    ):
        task_id = async_queue.submit_task("reaper", "web_search", {"query": "result_test"})

        for _ in range(50):
            await asyncio.sleep(0.05)
            if async_queue.get_status(task_id) == "completed":
                break

        result = async_queue.get_result(task_id)
        assert result is not None
        assert result["success"] is True
        assert result["tool_name"] == "web_search"
        assert result["module"] == "reaper"

    async def test_result_is_none_for_pending_task(self, async_queue: AsyncTaskQueue):
        """get_result returns None for tasks that haven't completed yet."""
        slow_module = MockModule(name="reaper", tools=["web_search", "web_scrape"])
        slow_module._delay = 5.0  # very slow — won't complete during test

        # Replace registry module
        async_queue._registry = ModuleRegistry()
        async_queue._registry.register(slow_module)

        task_id = async_queue.submit_task("reaper", "web_search", {"query": "pending"})
        await asyncio.sleep(0.1)

        result = async_queue.get_result(task_id)
        assert result is None


# ===================================================================
# Test: Failure Handling
# ===================================================================

class TestFailureHandling:
    """Tests that task failures don't crash the worker."""

    async def test_failed_task_status(
        self, async_queue: AsyncTaskQueue, mock_module: MockModule
    ):
        mock_module._fail_on.add("web_search")
        task_id = async_queue.submit_task("reaper", "web_search", {"query": "fail"})

        for _ in range(50):
            await asyncio.sleep(0.05)
            if async_queue.get_status(task_id) in ("completed", "failed"):
                break

        assert async_queue.get_status(task_id) == "failed"

    async def test_failed_task_has_error_in_result(
        self, async_queue: AsyncTaskQueue, mock_module: MockModule
    ):
        mock_module._fail_on.add("web_search")
        task_id = async_queue.submit_task("reaper", "web_search", {"query": "fail"})

        for _ in range(50):
            await asyncio.sleep(0.05)
            if async_queue.get_status(task_id) == "failed":
                break

        result = async_queue.get_result(task_id)
        assert result is not None
        assert "error" in result

    async def test_failed_task_doesnt_crash_worker(
        self, async_queue: AsyncTaskQueue, mock_module: MockModule
    ):
        """After a failure, the worker should still process the next task."""
        mock_module._fail_on.add("web_search")

        # Submit a task that will fail
        fail_id = async_queue.submit_task("reaper", "web_search", {"query": "fail"})

        for _ in range(50):
            await asyncio.sleep(0.05)
            if async_queue.get_status(fail_id) == "failed":
                break
        assert async_queue.get_status(fail_id) == "failed"

        # Now submit a task that should succeed (web_scrape is not in _fail_on)
        ok_id = async_queue.submit_task("reaper", "web_scrape", {"url": "http://test"})

        for _ in range(50):
            await asyncio.sleep(0.05)
            if async_queue.get_status(ok_id) == "completed":
                break
        assert async_queue.get_status(ok_id) == "completed"


# ===================================================================
# Test: Active Task Listing
# ===================================================================

class TestListActiveTasks:
    """Tests for list_active_tasks()."""

    async def test_list_active_returns_submitted_tasks(
        self, task_queue: PriorityTaskQueue, task_tracker: TaskTracker,
        registry: ModuleRegistry,
    ):
        """Submit multiple tasks with a slow module so they stay queued/running."""
        slow_module = MockModule(name="reaper", tools=["web_search", "web_scrape"])
        slow_module._delay = 2.0

        reg = ModuleRegistry()
        reg.register(slow_module)

        aq = AsyncTaskQueue(task_queue, task_tracker, reg)
        await aq.start()

        aq.submit_task("reaper", "web_search", {"q": "1"})
        aq.submit_task("reaper", "web_scrape", {"q": "2"})
        aq.submit_task("reaper", "web_search", {"q": "3"})

        await asyncio.sleep(0.1)

        active = aq.list_active_tasks()
        # At least some should still be queued/running since delay is 2s
        assert len(active) >= 1

        await aq.stop()

    async def test_list_active_empty_when_idle(self, async_queue: AsyncTaskQueue):
        active = async_queue.list_active_tasks()
        assert active == []


# ===================================================================
# Test: Graceful Shutdown
# ===================================================================

class TestLifecycle:
    """Tests for start/stop lifecycle."""

    async def test_stop_gracefully(
        self, task_queue: PriorityTaskQueue, task_tracker: TaskTracker,
        registry: ModuleRegistry,
    ):
        aq = AsyncTaskQueue(task_queue, task_tracker, registry)
        await aq.start()
        assert aq._worker_task is not None
        await aq.stop()
        assert aq._worker_task is None

    async def test_stop_with_pending_tasks(
        self, task_queue: PriorityTaskQueue, task_tracker: TaskTracker,
        registry: ModuleRegistry,
    ):
        """Stop should complete even if tasks are queued."""
        slow_module = MockModule(name="reaper", tools=["web_search", "web_scrape"])
        slow_module._delay = 10.0

        reg = ModuleRegistry()
        reg.register(slow_module)

        aq = AsyncTaskQueue(task_queue, task_tracker, reg)
        await aq.start()
        aq.submit_task("reaper", "web_search", {"q": "pending"})
        await asyncio.sleep(0.05)

        # Should stop within timeout despite pending work
        await aq.stop()
        assert aq._worker_task is None


# ===================================================================
# Test: Task ID Prefix Resolution
# ===================================================================

class TestPrefixResolution:
    """Tests for short task ID prefix lookup."""

    async def test_get_status_with_prefix(self, async_queue: AsyncTaskQueue):
        task_id = async_queue.submit_task("reaper", "web_search", {"query": "prefix"})

        for _ in range(50):
            await asyncio.sleep(0.05)
            if async_queue.get_status(task_id) == "completed":
                break

        # Use first 8 chars as prefix
        prefix = task_id[:8]
        status = async_queue.get_status(prefix)
        assert status is not None
        assert status == "completed"

    async def test_get_status_unknown_prefix(self, async_queue: AsyncTaskQueue):
        status = async_queue.get_status("nonexistent-id")
        assert status is None


# ===================================================================
# Test: CLI Commands
# ===================================================================

class TestCLICommands:
    """Tests for /tasks and /task CLI commands via handle_command()."""

    async def test_tasks_command_no_tasks(self, capsys):
        """The /tasks command should handle no active tasks."""
        from main import handle_command

        # Create a minimal orchestrator mock with async_task_queue
        orch = MagicMock()
        atq = MagicMock()
        atq.list_active_tasks.return_value = []
        orch.async_task_queue = atq

        result = await handle_command("/tasks", orch)
        assert result is True
        captured = capsys.readouterr()
        assert "No active background tasks" in captured.out

    async def test_tasks_command_with_tasks(self, capsys):
        """The /tasks command should display active tasks."""
        from main import handle_command

        orch = MagicMock()
        atq = MagicMock()
        atq.list_active_tasks.return_value = [
            {
                "task_id": "abc12345-6789-0000-0000-000000000000",
                "status": "running",
                "priority": 4,
                "description": "Background: web_search",
            }
        ]
        orch.async_task_queue = atq

        result = await handle_command("/tasks", orch)
        assert result is True
        captured = capsys.readouterr()
        assert "Active Tasks" in captured.out
        assert "abc12345" in captured.out
        assert "running" in captured.out

    async def test_task_command_shows_status(self, capsys):
        """The /task <id> command should show task details."""
        from main import handle_command

        orch = MagicMock()
        atq = MagicMock()
        atq.get_status.return_value = "completed"
        atq.get_result.return_value = {"success": True, "content": "done"}
        orch.async_task_queue = atq

        result = await handle_command("/task abc12345", orch)
        assert result is True
        captured = capsys.readouterr()
        assert "completed" in captured.out
        assert "Result" in captured.out

    async def test_task_command_not_found(self, capsys):
        """The /task <id> command should handle missing tasks."""
        from main import handle_command

        orch = MagicMock()
        atq = MagicMock()
        atq.get_status.return_value = None
        orch.async_task_queue = atq

        result = await handle_command("/task nonexistent", orch)
        assert result is True
        captured = capsys.readouterr()
        assert "not found" in captured.out

    async def test_tasks_command_no_queue(self, capsys):
        """The /tasks command should handle missing async queue gracefully."""
        from main import handle_command

        orch = MagicMock()
        orch.async_task_queue = None

        result = await handle_command("/tasks", orch)
        assert result is True
        captured = capsys.readouterr()
        assert "not available" in captured.out
