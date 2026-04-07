"""
Priority Task Queue — Queue-based task processing with preemption.
====================================================================
Manages all incoming tasks (user requests, module-to-module, scheduled,
events) through a priority queue. Critical tasks preempt lower-priority
running work. State persists to JSON for crash recovery.

Priority levels:
  1 — CRITICAL: Security alerts, emergency shutdown, creator direct commands
  2 — HIGH: Creator requests, time-sensitive module requests
  3 — NORMAL: Routine module-to-module, scheduled tasks
  4 — BACKGROUND: Growth Engine, autonomous learning, overnight work
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("shadow.task_queue")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskSource(Enum):
    """Where the task originated."""
    USER = "user"
    MODULE = "module"
    SCHEDULED = "scheduled"
    EVENT = "event"


class TaskKind(Enum):
    """Whether this is a single task or a multi-step chain."""
    SINGLE = "single"
    CHAIN = "chain"


class QueuedTaskStatus(Enum):
    """Lifecycle state of a queued task."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PREEMPTED = "preempted"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class QueuedTask:
    """A task waiting in or being processed by the priority queue."""
    task_id: str
    description: str
    source: TaskSource
    source_module: Optional[str]
    priority: int  # 1=critical, 2=high, 3=normal, 4=background
    task_type: TaskKind
    chain_id: Optional[str]
    payload: dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: QueuedTaskStatus = QueuedTaskStatus.QUEUED
    preempted_by: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    _saved_state: Optional[dict[str, Any]] = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "source": self.source.value,
            "source_module": self.source_module,
            "priority": self.priority,
            "task_type": self.task_type.value,
            "chain_id": self.chain_id,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "preempted_by": self.preempted_by,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> QueuedTask:
        """Deserialize from a dict."""
        return cls(
            task_id=d["task_id"],
            description=d["description"],
            source=TaskSource(d["source"]),
            source_module=d.get("source_module"),
            priority=d["priority"],
            task_type=TaskKind(d["task_type"]),
            chain_id=d.get("chain_id"),
            payload=d.get("payload", {}),
            created_at=datetime.fromisoformat(d["created_at"]),
            started_at=datetime.fromisoformat(d["started_at"]) if d.get("started_at") else None,
            completed_at=datetime.fromisoformat(d["completed_at"]) if d.get("completed_at") else None,
            status=QueuedTaskStatus(d.get("status", "queued")),
            preempted_by=d.get("preempted_by"),
            result=d.get("result"),
            error=d.get("error"),
        )


# ---------------------------------------------------------------------------
# Priority Task Queue
# ---------------------------------------------------------------------------

class PriorityTaskQueue:
    """Thread-safe priority task queue with preemption and persistence.

    Tasks are dequeued highest-priority-first (1 before 2 before 3 before 4).
    Within the same priority level, FIFO ordering applies.

    Critical (priority 1) tasks preempt running tasks of priority 3+.
    Preempted tasks are saved and resumed after the preempting task completes.
    """

    def __init__(self, persist_path: str | Path = "data/task_queue.json") -> None:
        self._persist_path = Path(persist_path)
        self._queue: list[QueuedTask] = []
        self._running: dict[str, QueuedTask] = {}  # task_id → running task
        self._completed: list[QueuedTask] = []
        self._preempted: list[QueuedTask] = []  # paused tasks waiting to resume
        self._lock = threading.Lock()
        self._last_persist = 0.0
        self._persist_interval = 30.0  # seconds

    def initialize(self) -> None:
        """Load persisted queue state if available."""
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        if self._persist_path.exists():
            self._load_state()
        logger.info(
            "PriorityTaskQueue initialized: %d queued, %d running, %d completed",
            len(self._queue), len(self._running), len(self._completed),
        )

    def close(self) -> None:
        """Persist final state."""
        self._persist_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, task: QueuedTask) -> str:
        """Add a task to the queue.

        If priority is 1 (critical) and there's a running priority 3+ task,
        the running task will be preempted.

        Args:
            task: The task to enqueue.

        Returns:
            The task_id.
        """
        with self._lock:
            task.status = QueuedTaskStatus.QUEUED
            self._queue.append(task)
            # Sort: priority ascending (1 first), then created_at ascending (FIFO)
            self._queue.sort(key=lambda t: (t.priority, t.created_at))

            # Check for preemption
            if task.priority == 1:
                self._check_preemption(task)

            self._maybe_persist()
            logger.info(
                "Enqueued task %s: priority %d, source %s — '%s'",
                task.task_id[:8], task.priority, task.source.value,
                task.description[:50],
            )
            return task.task_id

    def dequeue(self) -> Optional[QueuedTask]:
        """Return the highest priority task that's ready to run.

        Priority 1 first, then 2, then 3, then 4.
        Within same priority, FIFO (oldest first).

        Returns:
            The next task to process, or None if queue is empty.
        """
        with self._lock:
            if not self._queue:
                # Check if there are preempted tasks to resume
                return self._resume_preempted()
            task = self._queue.pop(0)
            task.status = QueuedTaskStatus.RUNNING
            task.started_at = datetime.now()
            self._running[task.task_id] = task
            self._maybe_persist()
            return task

    def complete(self, task_id: str, result: dict[str, Any] | None = None) -> None:
        """Mark a running task as completed.

        Args:
            task_id: ID of the task to complete.
            result: Optional result data.

        Raises:
            KeyError: If task_id not found in running tasks.
        """
        with self._lock:
            if task_id not in self._running:
                raise KeyError(f"Task {task_id} not in running tasks")
            task = self._running.pop(task_id)
            task.status = QueuedTaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            self._completed.append(task)
            self._maybe_persist()
            logger.info("Task %s completed", task_id[:8])

    def fail(self, task_id: str, error: str) -> None:
        """Mark a running task as failed.

        Args:
            task_id: ID of the task to fail.
            error: Error description.

        Raises:
            KeyError: If task_id not found in running tasks.
        """
        with self._lock:
            if task_id not in self._running:
                raise KeyError(f"Task {task_id} not in running tasks")
            task = self._running.pop(task_id)
            task.status = QueuedTaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = error
            self._completed.append(task)
            self._maybe_persist()
            logger.info("Task %s failed: %s", task_id[:8], error[:50])

    def preempt(self, running_task_id: str, preempting_task_id: str) -> None:
        """Preempt a running task in favor of a higher-priority task.

        The preempted task is saved and will be resumed when the
        preempting task completes.

        Args:
            running_task_id: Task to pause.
            preempting_task_id: Task that's taking over.

        Raises:
            KeyError: If running_task_id not found.
        """
        with self._lock:
            if running_task_id not in self._running:
                raise KeyError(f"Task {running_task_id} not in running tasks")

            paused = self._running.pop(running_task_id)
            paused.status = QueuedTaskStatus.PREEMPTED
            paused.preempted_by = preempting_task_id
            self._preempted.append(paused)
            self._maybe_persist()
            logger.info(
                "Task %s preempted by %s",
                running_task_id[:8], preempting_task_id[:8],
            )

    def peek(self) -> Optional[QueuedTask]:
        """See the next task without removing it.

        Returns:
            The next task, or None if queue is empty.
        """
        with self._lock:
            if self._queue:
                return self._queue[0]
            if self._preempted:
                return self._preempted[0]
            return None

    def get_queue_depth(self) -> int:
        """Total tasks waiting in the queue."""
        with self._lock:
            return len(self._queue)

    def get_running_count(self) -> int:
        """Number of currently running tasks."""
        with self._lock:
            return len(self._running)

    def get_queue_by_priority(self) -> dict[int, int]:
        """Return task count per priority level.

        Returns:
            Dict like {1: 0, 2: 3, 3: 5, 4: 1}.
        """
        with self._lock:
            counts = {1: 0, 2: 0, 3: 0, 4: 0}
            for task in self._queue:
                if task.priority in counts:
                    counts[task.priority] += 1
            return counts

    def get_running_tasks(self) -> list[dict[str, Any]]:
        """Return info about currently running tasks."""
        with self._lock:
            return [t.to_dict() for t in self._running.values()]

    def get_task(self, task_id: str) -> Optional[QueuedTask]:
        """Find a task by ID across all states.

        Args:
            task_id: The task to find.

        Returns:
            The task, or None if not found.
        """
        with self._lock:
            # Check running
            if task_id in self._running:
                return self._running[task_id]
            # Check queue
            for t in self._queue:
                if t.task_id == task_id:
                    return t
            # Check preempted
            for t in self._preempted:
                if t.task_id == task_id:
                    return t
            # Check completed
            for t in self._completed:
                if t.task_id == task_id:
                    return t
            return None

    def cleanup_completed(self, max_age_hours: int = 24) -> int:
        """Remove completed/failed tasks older than max_age_hours.

        Args:
            max_age_hours: Maximum age before cleanup.

        Returns:
            Number of tasks removed.
        """
        with self._lock:
            cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
            before = len(self._completed)
            self._completed = [
                t for t in self._completed
                if t.completed_at and t.completed_at.timestamp() > cutoff
            ]
            removed = before - len(self._completed)
            if removed:
                self._persist_state()
                logger.info("Cleaned up %d completed tasks", removed)
            return removed

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def create_task(
        description: str,
        source: str = "user",
        source_module: str | None = None,
        priority: int = 3,
        task_type: str = "single",
        chain_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> QueuedTask:
        """Convenience factory for creating QueuedTask instances.

        Args:
            description: What this task does.
            source: One of "user", "module", "scheduled", "event".
            source_module: Which module created this task (if source is "module").
            priority: 1 (critical) through 4 (background).
            task_type: "single" or "chain".
            chain_id: Associated chain ID if task_type is "chain".
            payload: Task data/parameters.

        Returns:
            A new QueuedTask ready to enqueue.
        """
        return QueuedTask(
            task_id=str(uuid.uuid4()),
            description=description,
            source=TaskSource(source),
            source_module=source_module,
            priority=priority,
            task_type=TaskKind(task_type),
            chain_id=chain_id,
            payload=payload or {},
            created_at=datetime.now(),
        )

    # ------------------------------------------------------------------
    # Internal: preemption
    # ------------------------------------------------------------------

    def _check_preemption(self, critical_task: QueuedTask) -> None:
        """Check if a critical task should preempt running lower-priority tasks.

        Called inside lock. Only preempts priority 3+ tasks.
        """
        for task_id, running in list(self._running.items()):
            if running.priority >= 3:
                # Preempt this task
                running.status = QueuedTaskStatus.PREEMPTED
                running.preempted_by = critical_task.task_id
                self._preempted.append(running)
                del self._running[task_id]
                logger.info(
                    "Auto-preempted task %s (priority %d) for critical task %s",
                    task_id[:8], running.priority, critical_task.task_id[:8],
                )

    def _resume_preempted(self) -> Optional[QueuedTask]:
        """Resume the highest-priority preempted task.

        Called inside lock when the queue is empty but preempted tasks exist.
        """
        if not self._preempted:
            return None
        # Sort by priority, then by original creation time
        self._preempted.sort(key=lambda t: (t.priority, t.created_at))
        task = self._preempted.pop(0)
        task.status = QueuedTaskStatus.RUNNING
        task.preempted_by = None
        self._running[task.task_id] = task
        logger.info("Resumed preempted task %s (priority %d)", task.task_id[:8], task.priority)
        return task

    # ------------------------------------------------------------------
    # Internal: persistence
    # ------------------------------------------------------------------

    def _maybe_persist(self) -> None:
        """Persist state if enough time has elapsed since last save."""
        now = time.time()
        if now - self._last_persist >= self._persist_interval:
            self._persist_state()

    def _persist_state(self) -> None:
        """Save queue state to JSON file."""
        try:
            state = {
                "queue": [t.to_dict() for t in self._queue],
                "running": [t.to_dict() for t in self._running.values()],
                "preempted": [t.to_dict() for t in self._preempted],
                "completed": [t.to_dict() for t in self._completed[-100:]],  # Keep last 100
                "saved_at": datetime.now().isoformat(),
            }
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._persist_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(state, indent=2))
            tmp_path.replace(self._persist_path)
            self._last_persist = time.time()
        except Exception as e:
            logger.error("Failed to persist queue state: %s", e)

    def _load_state(self) -> None:
        """Load queue state from JSON file."""
        try:
            data = json.loads(self._persist_path.read_text())
            self._queue = [QueuedTask.from_dict(d) for d in data.get("queue", [])]
            # Running tasks from last session are re-queued (they didn't finish)
            for d in data.get("running", []):
                task = QueuedTask.from_dict(d)
                task.status = QueuedTaskStatus.QUEUED
                task.started_at = None
                self._queue.append(task)
            self._preempted = [
                QueuedTask.from_dict(d) for d in data.get("preempted", [])
            ]
            self._completed = [
                QueuedTask.from_dict(d) for d in data.get("completed", [])
            ]
            # Re-sort queue
            self._queue.sort(key=lambda t: (t.priority, t.created_at))
            logger.info(
                "Loaded queue state: %d queued, %d preempted, %d completed",
                len(self._queue), len(self._preempted), len(self._completed),
            )
        except Exception as e:
            logger.warning("Failed to load queue state: %s — starting fresh", e)
            self._queue = []
            self._running = {}
            self._preempted = []
            self._completed = []
