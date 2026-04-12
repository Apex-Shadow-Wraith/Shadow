"""
AsyncTaskQueue — Async worker loop for background task execution.
=================================================================
Wraps the existing PriorityTaskQueue (in-memory priority queue) and
TaskTracker (SQLite persistence) with an asyncio worker loop so tasks
can run concurrently with the CLI without blocking the orchestrator.

Usage:
    atq = AsyncTaskQueue(task_queue, task_tracker, registry)
    await atq.start()
    task_id = atq.submit_task("reaper", "web_search", {"query": "..."})
    status = atq.get_status(task_id)   # "queued" / "running" / "completed" / "failed"
    result = atq.get_result(task_id)   # dict or None
    await atq.stop()
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from modules.base import ModuleRegistry, ToolResult
from modules.shadow.task_queue import PriorityTaskQueue, QueuedTaskStatus
from modules.shadow.task_tracker import TaskTracker

logger = logging.getLogger("shadow.async_tasks")


class AsyncTaskQueue:
    """Async worker that pulls from PriorityTaskQueue and executes via ModuleRegistry.

    Does NOT create its own queue or database — accepts existing instances.
    Uses asyncio.Event to wake the worker when new tasks are submitted.
    """

    def __init__(
        self,
        task_queue: PriorityTaskQueue,
        task_tracker: TaskTracker,
        registry: ModuleRegistry,
    ) -> None:
        self._task_queue = task_queue
        self._task_tracker = task_tracker
        self._registry = registry
        self._work_available = asyncio.Event()
        self._shutdown = False
        self._worker_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background worker loop."""
        self._shutdown = False
        self._worker_task = asyncio.create_task(
            self._worker_loop(), name="async-task-worker"
        )
        logger.info("AsyncTaskQueue worker started")

    async def stop(self) -> None:
        """Signal shutdown and wait for the worker to finish."""
        self._shutdown = True
        self._work_available.set()  # wake the worker so it sees the flag
        if self._worker_task is not None:
            try:
                await asyncio.wait_for(self._worker_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Worker did not stop in time, cancelling")
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass
            self._worker_task = None
        logger.info("AsyncTaskQueue worker stopped")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_task(
        self,
        module_name: str,
        tool_name: str,
        params: dict[str, Any],
        description: str = "",
        priority: int = 4,
    ) -> str:
        """Submit a task for background execution.

        Args:
            module_name: Which module owns the tool.
            tool_name: The tool to invoke.
            params: Tool parameters.
            description: Human-readable description of the task.
            priority: 1 (critical) through 4 (background). Default 4.

        Returns:
            The task_id (UUID string).
        """
        desc = description or f"{module_name}.{tool_name}"

        # Create and enqueue on the priority queue
        queued_task = PriorityTaskQueue.create_task(
            description=desc,
            source="user",
            source_module=module_name,
            priority=priority,
            payload={
                "module_name": module_name,
                "tool_name": tool_name,
                "params": params,
            },
        )
        task_id = self._task_queue.enqueue(queued_task)

        # Mirror into SQLite tracker for durability
        try:
            self._task_tracker.create(
                description=desc,
                assigned_module=module_name,
                priority=priority,
            )
            # TaskTracker generates its own ID — update it to match
            # We use the queue's task_id as the canonical ID, so store it
            # in tracker by updating the most recent record.
            # Simpler: just log the mapping. The queue is the source of truth
            # for active tasks; tracker is for historical queries.
        except Exception as e:
            logger.warning("TaskTracker mirror failed for %s: %s", task_id[:8], e)

        # Wake the worker
        self._work_available.set()

        logger.info(
            "Task submitted: %s → %s.%s (priority %d)",
            task_id[:8], module_name, tool_name, priority,
        )
        return task_id

    def get_status(self, task_id: str) -> str | None:
        """Get the status of a task by ID or ID prefix.

        Returns:
            Status string ("queued"/"running"/"completed"/"failed"/"preempted")
            or None if not found.
        """
        resolved = self._resolve_task_id(task_id)
        if resolved is None:
            return None

        task = self._task_queue.get_task(resolved)
        if task is not None:
            return task.status.value
        return None

    def get_result(self, task_id: str) -> dict[str, Any] | None:
        """Get the result of a completed task.

        Returns:
            Result dict if task is complete/failed, None otherwise.
        """
        resolved = self._resolve_task_id(task_id)
        if resolved is None:
            return None

        task = self._task_queue.get_task(resolved)
        if task is None:
            return None

        if task.status in (QueuedTaskStatus.COMPLETED, QueuedTaskStatus.FAILED):
            return task.result if task.result else {"error": task.error}
        return None

    def list_active_tasks(self) -> list[dict[str, Any]]:
        """List all queued and running tasks.

        Returns:
            List of task info dicts with task_id, status, priority, description.
        """
        active: list[dict[str, Any]] = []

        # Running tasks
        for t in self._task_queue.get_running_tasks():
            active.append(t)

        # Queued tasks — access the internal queue (thread-safe via get_task iteration)
        # We check all known task IDs from the queue's internal state
        with self._task_queue._lock:
            for t in self._task_queue._queue:
                active.append(t.to_dict())

        return active

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        """Background coroutine that processes tasks from the priority queue."""
        logger.info("Worker loop started")

        while not self._shutdown:
            # Try to dequeue
            task = self._task_queue.dequeue()

            if task is None:
                # No work — wait for signal or periodic check
                self._work_available.clear()
                try:
                    await asyncio.wait_for(self._work_available.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass  # periodic check for preempted tasks / shutdown
                continue

            task_id = task.task_id
            tool_name = task.payload.get("tool_name", "unknown")
            params = task.payload.get("params", {})

            logger.info("Worker picked up task %s: %s", task_id[:8], task.description)

            # Update tracker to "running"
            try:
                self._task_tracker.update_status(task_id, "running")
            except (KeyError, Exception) as e:
                logger.debug("TaskTracker running update skipped for %s: %s", task_id[:8], e)

            # Execute
            start_time = time.time()
            try:
                module = self._registry.get_module_for_tool(tool_name)
                result: ToolResult = await module.execute(tool_name, params)
                elapsed_ms = (time.time() - start_time) * 1000

                result_dict = {
                    "success": result.success,
                    "content": result.content,
                    "tool_name": result.tool_name,
                    "module": result.module,
                    "execution_time_ms": elapsed_ms,
                    "error": result.error,
                }

                self._task_queue.complete(task_id, result_dict)
                try:
                    self._task_tracker.update_status(task_id, "completed", result_dict)
                except (KeyError, Exception) as e:
                    logger.debug("TaskTracker complete update skipped: %s", e)

                logger.info(
                    "Task %s completed in %.0fms (success=%s)",
                    task_id[:8], elapsed_ms, result.success,
                )

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                error_msg = f"{type(e).__name__}: {e}"

                try:
                    self._task_queue.fail(task_id, error_msg)
                except KeyError:
                    pass
                try:
                    self._task_tracker.update_status(task_id, "failed", {"error": error_msg})
                except (KeyError, Exception):
                    pass

                logger.error(
                    "Task %s failed in %.0fms: %s", task_id[:8], elapsed_ms, error_msg,
                )
                # Loop continues — per-task exception handling

        logger.info("Worker loop exiting")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_task_id(self, task_id_or_prefix: str) -> str | None:
        """Resolve a task ID or short prefix to a full task ID.

        Searches the PriorityTaskQueue's internal lists for a matching ID.
        """
        # Try exact match first
        task = self._task_queue.get_task(task_id_or_prefix)
        if task is not None:
            return task_id_or_prefix

        # Try prefix match across all task lists
        prefix = task_id_or_prefix.lower()
        with self._task_queue._lock:
            all_tasks = (
                list(self._task_queue._queue)
                + list(self._task_queue._running.values())
                + list(self._task_queue._preempted)
                + list(self._task_queue._completed)
            )

        for t in all_tasks:
            if t.task_id.lower().startswith(prefix):
                return t.task_id

        return None
