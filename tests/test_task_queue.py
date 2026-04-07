"""Tests for PriorityTaskQueue — priority queue with preemption and persistence."""

import json
import time
import uuid
from datetime import datetime, timedelta

import pytest

from modules.shadow.task_queue import (
    PriorityTaskQueue,
    QueuedTask,
    QueuedTaskStatus,
    TaskKind,
    TaskSource,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def queue(tmp_path):
    """Create a PriorityTaskQueue with temp persistence."""
    q = PriorityTaskQueue(persist_path=tmp_path / "test_queue.json")
    q.initialize()
    yield q
    q.close()


def _make_task(
    description="Test task",
    priority=3,
    source="user",
    task_type="single",
    created_at=None,
):
    """Helper to create a QueuedTask."""
    return PriorityTaskQueue.create_task(
        description=description,
        priority=priority,
        source=source,
        task_type=task_type,
    )


# ---------------------------------------------------------------------------
# Enqueue / Dequeue basics
# ---------------------------------------------------------------------------


class TestEnqueueDequeue:
    """Tests for basic queue operations."""

    def test_enqueue_returns_task_id(self, queue):
        """Enqueue returns the task_id."""
        task = _make_task()
        task_id = queue.enqueue(task)
        assert task_id == task.task_id
        uuid.UUID(task_id, version=4)  # Valid UUID

    def test_dequeue_returns_highest_priority(self, queue):
        """Dequeue returns highest priority task first."""
        low = _make_task("Low", priority=4)
        high = _make_task("High", priority=1)
        normal = _make_task("Normal", priority=3)

        queue.enqueue(low)
        queue.enqueue(high)
        queue.enqueue(normal)

        task = queue.dequeue()
        assert task.description == "High"
        assert task.priority == 1
        assert task.status == QueuedTaskStatus.RUNNING

    def test_fifo_within_same_priority(self, queue):
        """Tasks with equal priority dequeue in FIFO order."""
        first = _make_task("First", priority=3)
        second = _make_task("Second", priority=3)
        third = _make_task("Third", priority=3)

        # Ensure ordering by slightly adjusting created_at
        first.created_at = datetime(2026, 1, 1, 12, 0, 0)
        second.created_at = datetime(2026, 1, 1, 12, 0, 1)
        third.created_at = datetime(2026, 1, 1, 12, 0, 2)

        queue.enqueue(first)
        queue.enqueue(second)
        queue.enqueue(third)

        assert queue.dequeue().description == "First"
        assert queue.dequeue().description == "Second"
        assert queue.dequeue().description == "Third"

    def test_dequeue_empty_returns_none(self, queue):
        """Dequeue on empty queue returns None."""
        assert queue.dequeue() is None

    def test_dequeue_marks_task_running(self, queue):
        """Dequeued task has RUNNING status and started_at set."""
        task = _make_task()
        queue.enqueue(task)
        dequeued = queue.dequeue()
        assert dequeued.status == QueuedTaskStatus.RUNNING
        assert dequeued.started_at is not None


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    """Tests for priority-based dequeue ordering."""

    def test_priority_1_before_2(self, queue):
        """Priority 1 dequeues before priority 2."""
        queue.enqueue(_make_task("P2", priority=2))
        queue.enqueue(_make_task("P1", priority=1))
        assert queue.dequeue().description == "P1"

    def test_priority_2_before_3(self, queue):
        """Priority 2 dequeues before priority 3."""
        queue.enqueue(_make_task("P3", priority=3))
        queue.enqueue(_make_task("P2", priority=2))
        assert queue.dequeue().description == "P2"

    def test_priority_3_before_4(self, queue):
        """Priority 3 dequeues before priority 4."""
        queue.enqueue(_make_task("P4", priority=4))
        queue.enqueue(_make_task("P3", priority=3))
        assert queue.dequeue().description == "P3"

    def test_full_priority_ordering(self, queue):
        """All four priority levels dequeue in correct order."""
        for p in [4, 2, 1, 3]:
            queue.enqueue(_make_task(f"P{p}", priority=p))

        for expected in [1, 2, 3, 4]:
            task = queue.dequeue()
            assert task.priority == expected


# ---------------------------------------------------------------------------
# Preemption
# ---------------------------------------------------------------------------


class TestPreemption:
    """Tests for task preemption."""

    def test_preempt_lower_priority_for_critical(self, queue):
        """Enqueueing critical (P1) task auto-preempts running P3+ tasks."""
        # Start a P3 task running
        normal = _make_task("Normal task", priority=3)
        queue.enqueue(normal)
        running = queue.dequeue()
        assert running.status == QueuedTaskStatus.RUNNING

        # Enqueue critical task — should auto-preempt
        critical = _make_task("CRITICAL", priority=1)
        queue.enqueue(critical)

        # The normal task should now be preempted
        found = queue.get_task(running.task_id)
        assert found.status == QueuedTaskStatus.PREEMPTED
        assert found.preempted_by == critical.task_id

    def test_preempt_does_not_affect_p2(self, queue):
        """Critical task does NOT preempt P2 tasks (only P3+)."""
        high = _make_task("High priority", priority=2)
        queue.enqueue(high)
        running = queue.dequeue()

        critical = _make_task("CRITICAL", priority=1)
        queue.enqueue(critical)

        # P2 task should still be running
        found = queue.get_task(running.task_id)
        assert found.status == QueuedTaskStatus.RUNNING

    def test_manual_preempt(self, queue):
        """Explicit preempt() pauses a running task."""
        task_a = _make_task("Task A", priority=3)
        task_b = _make_task("Task B", priority=1)

        queue.enqueue(task_a)
        running = queue.dequeue()
        queue.enqueue(task_b)

        # Manually preempt if not auto-preempted already
        if running.status == QueuedTaskStatus.RUNNING:
            queue.preempt(running.task_id, task_b.task_id)

        found = queue.get_task(running.task_id)
        assert found.status == QueuedTaskStatus.PREEMPTED

    def test_preempted_task_resumes(self, queue):
        """Preempted tasks resume when queue is empty."""
        normal = _make_task("Normal", priority=3)
        queue.enqueue(normal)
        running = queue.dequeue()

        critical = _make_task("Critical", priority=1)
        queue.enqueue(critical)

        # Dequeue the critical task
        crit = queue.dequeue()
        assert crit.description == "Critical"

        # Complete the critical task
        queue.complete(crit.task_id)

        # Now dequeue should resume the preempted task
        resumed = queue.dequeue()
        assert resumed is not None
        assert resumed.task_id == normal.task_id
        assert resumed.status == QueuedTaskStatus.RUNNING

    def test_preempt_raises_on_unknown(self, queue):
        """Preempting a nonexistent task raises KeyError."""
        with pytest.raises(KeyError):
            queue.preempt("nonexistent", "other")


# ---------------------------------------------------------------------------
# Complete / Fail
# ---------------------------------------------------------------------------


class TestCompleteAndFail:
    """Tests for task completion and failure."""

    def test_complete_task(self, queue):
        """Complete a task with result data."""
        task = _make_task()
        queue.enqueue(task)
        running = queue.dequeue()

        queue.complete(running.task_id, result={"data": "done"})
        found = queue.get_task(running.task_id)
        assert found.status == QueuedTaskStatus.COMPLETED
        assert found.result == {"data": "done"}
        assert found.completed_at is not None

    def test_fail_task(self, queue):
        """Fail a task with error description."""
        task = _make_task()
        queue.enqueue(task)
        running = queue.dequeue()

        queue.fail(running.task_id, error="Something broke")
        found = queue.get_task(running.task_id)
        assert found.status == QueuedTaskStatus.FAILED
        assert found.error == "Something broke"

    def test_complete_raises_on_unknown(self, queue):
        """Completing a nonexistent task raises KeyError."""
        with pytest.raises(KeyError):
            queue.complete("nonexistent")

    def test_fail_raises_on_unknown(self, queue):
        """Failing a nonexistent task raises KeyError."""
        with pytest.raises(KeyError):
            queue.fail("nonexistent", "error")


# ---------------------------------------------------------------------------
# Queue inspection
# ---------------------------------------------------------------------------


class TestQueueInspection:
    """Tests for queue depth, peek, and status queries."""

    def test_get_queue_depth(self, queue):
        """Queue depth reflects waiting tasks."""
        assert queue.get_queue_depth() == 0
        queue.enqueue(_make_task("A"))
        queue.enqueue(_make_task("B"))
        assert queue.get_queue_depth() == 2
        queue.dequeue()
        assert queue.get_queue_depth() == 1

    def test_peek(self, queue):
        """Peek returns next task without removing it."""
        queue.enqueue(_make_task("First", priority=2))
        queue.enqueue(_make_task("Second", priority=1))

        peeked = queue.peek()
        assert peeked.description == "Second"
        # Still in queue
        assert queue.get_queue_depth() == 2

    def test_peek_empty(self, queue):
        """Peek on empty queue returns None."""
        assert queue.peek() is None

    def test_get_queue_by_priority(self, queue):
        """Priority breakdown is accurate."""
        queue.enqueue(_make_task("A", priority=1))
        queue.enqueue(_make_task("B", priority=3))
        queue.enqueue(_make_task("C", priority=3))
        queue.enqueue(_make_task("D", priority=4))

        counts = queue.get_queue_by_priority()
        assert counts == {1: 1, 2: 0, 3: 2, 4: 1}

    def test_get_running_count(self, queue):
        """Running count reflects active tasks."""
        assert queue.get_running_count() == 0
        queue.enqueue(_make_task())
        queue.dequeue()
        assert queue.get_running_count() == 1

    def test_get_task_finds_across_states(self, queue):
        """get_task finds tasks in any state."""
        task = _make_task()
        queue.enqueue(task)
        assert queue.get_task(task.task_id) is not None

        running = queue.dequeue()
        assert queue.get_task(running.task_id) is not None

        queue.complete(running.task_id)
        assert queue.get_task(running.task_id) is not None

    def test_get_task_returns_none_for_unknown(self, queue):
        """get_task returns None for nonexistent task."""
        assert queue.get_task("nonexistent") is None


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    """Tests for completed task cleanup."""

    def test_cleanup_old_completed(self, queue):
        """Cleanup removes old completed tasks."""
        task = _make_task()
        queue.enqueue(task)
        running = queue.dequeue()
        queue.complete(running.task_id)

        # Artificially age the task
        completed = queue.get_task(running.task_id)
        completed.completed_at = datetime.now() - timedelta(hours=25)

        removed = queue.cleanup_completed(max_age_hours=24)
        assert removed == 1

    def test_cleanup_keeps_recent(self, queue):
        """Cleanup keeps recently completed tasks."""
        task = _make_task()
        queue.enqueue(task)
        running = queue.dequeue()
        queue.complete(running.task_id)

        removed = queue.cleanup_completed(max_age_hours=24)
        assert removed == 0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestQueuePersistence:
    """Tests for queue state persistence and recovery."""

    def test_persist_and_recover(self, tmp_path):
        """Queue state survives save/load cycle."""
        path = tmp_path / "persist_test.json"

        # Create and populate queue
        q1 = PriorityTaskQueue(persist_path=path)
        q1.initialize()
        q1.enqueue(_make_task("Task A", priority=2))
        q1.enqueue(_make_task("Task B", priority=3))
        q1._persist_state()  # Force persist
        q1.close()

        # Load into new queue
        q2 = PriorityTaskQueue(persist_path=path)
        q2.initialize()

        assert q2.get_queue_depth() == 2
        task = q2.dequeue()
        assert task.description == "Task A"  # P2 first
        q2.close()

    def test_running_tasks_requeued_on_recovery(self, tmp_path):
        """Tasks that were running when saved are re-queued on recovery."""
        path = tmp_path / "requeue_test.json"

        q1 = PriorityTaskQueue(persist_path=path)
        q1.initialize()
        q1.enqueue(_make_task("Running task", priority=2))
        q1.dequeue()  # Now running
        q1._persist_state()
        q1.close()

        q2 = PriorityTaskQueue(persist_path=path)
        q2.initialize()
        # Running task should be back in queue
        assert q2.get_queue_depth() == 1
        task = q2.dequeue()
        assert task.description == "Running task"
        q2.close()

    def test_queued_task_serialization(self):
        """QueuedTask survives to_dict/from_dict round trip."""
        task = QueuedTask(
            task_id="test-id",
            description="Test task",
            source=TaskSource.MODULE,
            source_module="reaper",
            priority=2,
            task_type=TaskKind.CHAIN,
            chain_id="chain-123",
            payload={"key": "value"},
            created_at=datetime(2026, 1, 1, 12, 0),
            started_at=datetime(2026, 1, 1, 12, 1),
            status=QueuedTaskStatus.RUNNING,
        )

        d = task.to_dict()
        restored = QueuedTask.from_dict(d)

        assert restored.task_id == task.task_id
        assert restored.source == TaskSource.MODULE
        assert restored.source_module == "reaper"
        assert restored.task_type == TaskKind.CHAIN
        assert restored.chain_id == "chain-123"
        assert restored.priority == 2


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


class TestCreateTaskFactory:
    """Tests for the create_task convenience factory."""

    def test_create_task_defaults(self):
        """Factory sets reasonable defaults."""
        task = PriorityTaskQueue.create_task("Quick task")
        assert task.description == "Quick task"
        assert task.source == TaskSource.USER
        assert task.priority == 3
        assert task.task_type == TaskKind.SINGLE
        assert task.status == QueuedTaskStatus.QUEUED
        assert task.chain_id is None
        uuid.UUID(task.task_id, version=4)

    def test_create_task_custom(self):
        """Factory accepts custom parameters."""
        task = PriorityTaskQueue.create_task(
            description="Module task",
            source="module",
            source_module="reaper",
            priority=1,
            task_type="chain",
            chain_id="chain-abc",
            payload={"data": "stuff"},
        )
        assert task.source == TaskSource.MODULE
        assert task.source_module == "reaper"
        assert task.priority == 1
        assert task.task_type == TaskKind.CHAIN
        assert task.chain_id == "chain-abc"
        assert task.payload == {"data": "stuff"}


# ---------------------------------------------------------------------------
# Integration: queue + chain flow
# ---------------------------------------------------------------------------


class TestQueueChainIntegration:
    """Integration tests simulating the full flow."""

    def test_user_request_to_queue_to_chain(self, tmp_path):
        """Simulate: user request → enqueue → dequeue → chain execution."""
        from modules.shadow.task_chain import TaskChainEngine

        registry = _make_mock_registry()
        config = {"models": {"ollama_base_url": "http://localhost:11434",
                              "router": {"name": "phi4-mini"}}}

        # Set up queue
        queue = PriorityTaskQueue(persist_path=tmp_path / "integ_queue.json")
        queue.initialize()

        # Set up chain engine
        engine = TaskChainEngine(registry=registry, config=config,
                                 db_path=tmp_path / "integ_chains.db")
        engine.initialize()

        # User submits a request
        task = PriorityTaskQueue.create_task(
            description="Research and implement firewall",
            source="user",
            priority=2,
            task_type="chain",
        )
        queue.enqueue(task)

        # Dequeue it
        dequeued = queue.dequeue()
        assert dequeued.description == "Research and implement firewall"

        # Create a chain from it
        chain = engine.create_chain(
            dequeued.description,
            steps=[
                {"module": "reaper", "task_description": "Research",
                 "output_key": "research"},
                {"module": "omen", "task_description": "Implement",
                 "output_key": "code", "input_source": "previous_step",
                 "depends_on": []},  # Simplified for test
            ],
            priority=dequeued.priority,
            trigger="user_request",
        )
        assert chain is not None
        assert len(chain.steps) == 2

        # Mark queue task as completed
        queue.complete(dequeued.task_id, result={"chain_id": chain.chain_id})

        found = queue.get_task(dequeued.task_id)
        assert found.status == QueuedTaskStatus.COMPLETED
        assert found.result["chain_id"] == chain.chain_id

        engine.close()
        queue.close()


def _make_mock_registry(online_modules=None):
    """Create a mock ModuleRegistry."""
    from unittest.mock import AsyncMock, MagicMock
    from modules.base import ModuleStatus, ToolResult

    if online_modules is None:
        online_modules = ["reaper", "omen", "sentinel", "wraith", "cerberus", "grimoire"]

    registry = MagicMock()
    registry.__contains__ = lambda self, name: name in online_modules

    def _get_module(name):
        mod = MagicMock()
        mod.name = name
        mod.status = ModuleStatus.ONLINE
        mod.get_tools = MagicMock(return_value=[{"name": f"{name}_default"}])

        async def _execute(tool_name, params):
            return ToolResult(success=True, content=f"Result from {name}/{tool_name}",
                              tool_name=tool_name, module=name)
        mod.execute = AsyncMock(side_effect=_execute)
        return mod

    registry.get_module = MagicMock(side_effect=_get_module)
    registry.find_tools = MagicMock(return_value=[{"name": "default_tool"}])
    registry.list_modules = MagicMock(return_value=[
        {"name": m, "status": "online", "description": f"{m} module"}
        for m in online_modules
    ])
    return registry
