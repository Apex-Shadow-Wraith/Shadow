"""
Module State Awareness — Real-Time Module Status Tracking
============================================================
Tracks the current state of all 13 Shadow modules so the orchestrator
and modules themselves know what everyone is doing. Enables:

- Load balancing: route tasks to idle modules
- Capability routing: find which module can handle a specific tool
- Health monitoring: detect overloaded or failing modules
- Dashboard data: feed Harbinger daily briefings

Thread-safe by design — all state mutations happen under a lock.
State persists to disk for restart recovery.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("shadow.module_state")


@dataclass
class ModuleState:
    """Current state of a single Shadow module."""

    module_name: str
    status: str = "offline"  # idle, busy, blocked, error, offline
    current_task: Optional[str] = None
    current_task_id: Optional[str] = None
    task_started_at: Optional[str] = None
    tasks_completed_today: int = 0
    tasks_failed_today: int = 0
    last_active: str = ""
    queue_depth: int = 0
    error_count_last_hour: int = 0
    avg_task_duration_seconds: float = 0.0
    capabilities: list[str] = field(default_factory=list)

    # Internal tracking (not serialized to snapshot)
    _recent_durations: list[float] = field(
        default_factory=list, repr=False
    )
    _error_timestamps: list[str] = field(
        default_factory=list, repr=False
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for snapshot persistence."""
        return {
            "module_name": self.module_name,
            "status": self.status,
            "current_task": self.current_task,
            "current_task_id": self.current_task_id,
            "task_started_at": self.task_started_at,
            "tasks_completed_today": self.tasks_completed_today,
            "tasks_failed_today": self.tasks_failed_today,
            "last_active": self.last_active,
            "queue_depth": self.queue_depth,
            "error_count_last_hour": self.error_count_last_hour,
            "avg_task_duration_seconds": self.avg_task_duration_seconds,
            "capabilities": self.capabilities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModuleState:
        """Restore from snapshot dict."""
        return cls(
            module_name=data["module_name"],
            status=data.get("status", "offline"),
            current_task=data.get("current_task"),
            current_task_id=data.get("current_task_id"),
            task_started_at=data.get("task_started_at"),
            tasks_completed_today=data.get("tasks_completed_today", 0),
            tasks_failed_today=data.get("tasks_failed_today", 0),
            last_active=data.get("last_active", ""),
            queue_depth=data.get("queue_depth", 0),
            error_count_last_hour=data.get("error_count_last_hour", 0),
            avg_task_duration_seconds=data.get("avg_task_duration_seconds", 0.0),
            capabilities=data.get("capabilities", []),
        )


class ModuleStateManager:
    """Manages real-time state for all Shadow modules.

    Thread-safe: all mutations happen under self._lock.
    Persistent: snapshots to data/module_states.json for restart recovery.
    """

    VALID_STATUSES = {"idle", "busy", "blocked", "error", "offline"}

    def __init__(
        self,
        snapshot_path: str = "data/module_states.json",
    ) -> None:
        self._states: dict[str, ModuleState] = {}
        self._lock = threading.Lock()
        self._snapshot_path = Path(snapshot_path)
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    def register_module(
        self,
        module_name: str,
        capabilities: Optional[list[str]] = None,
    ) -> None:
        """Register a module with its capabilities (tool names).

        Args:
            module_name: Module identifier.
            capabilities: List of tool names this module provides.
        """
        with self._lock:
            if module_name not in self._states:
                self._states[module_name] = ModuleState(
                    module_name=module_name,
                    capabilities=capabilities or [],
                    last_active=datetime.now().isoformat(),
                )
            else:
                # Update capabilities if re-registering
                self._states[module_name].capabilities = capabilities or []

    def update_state(
        self,
        module_name: str,
        status: str,
        current_task: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Update a module's state. Called by modules on start/finish/fail.

        Args:
            module_name: Which module is updating.
            status: New status (idle, busy, blocked, error, offline).
            current_task: Description of current work (None when idle).
            task_id: Optional task identifier.
        """
        if status not in self.VALID_STATUSES:
            logger.warning(
                "Invalid status '%s' for module '%s'",
                status,
                module_name,
            )
            return

        now = datetime.now()
        now_iso = now.isoformat()

        with self._lock:
            if module_name not in self._states:
                self._states[module_name] = ModuleState(module_name=module_name)

            state = self._states[module_name]
            previous_status = state.status

            # Track task completion/failure
            if previous_status == "busy" and status == "idle":
                state.tasks_completed_today += 1
                # Track duration for rolling average
                if state.task_started_at:
                    try:
                        started = datetime.fromisoformat(state.task_started_at)
                        duration = (now - started).total_seconds()
                        state._recent_durations.append(duration)
                        # Keep last 50 durations for rolling average
                        if len(state._recent_durations) > 50:
                            state._recent_durations = state._recent_durations[-50:]
                        state.avg_task_duration_seconds = (
                            sum(state._recent_durations) / len(state._recent_durations)
                        )
                    except (ValueError, TypeError):
                        pass

            elif previous_status == "busy" and status == "error":
                state.tasks_failed_today += 1

            # Track errors for rate limiting
            if status == "error":
                state._error_timestamps.append(now_iso)
                # Prune old error timestamps (keep last hour only)
                one_hour_ago = (now - timedelta(hours=1)).isoformat()
                state._error_timestamps = [
                    ts for ts in state._error_timestamps if ts >= one_hour_ago
                ]
                state.error_count_last_hour = len(state._error_timestamps)

            # Update state fields
            state.status = status
            state.last_active = now_iso

            if status == "busy":
                state.current_task = current_task
                state.current_task_id = task_id
                state.task_started_at = now_iso
            else:
                state.current_task = None
                state.current_task_id = None
                if status != "error":
                    state.task_started_at = None

    def get_state(self, module_name: str) -> ModuleState:
        """Return current state of a specific module.

        Returns a copy to prevent external mutation.
        Raises KeyError if module not registered.
        """
        with self._lock:
            if module_name not in self._states:
                raise KeyError(f"Module '{module_name}' not registered")
            state = self._states[module_name]
            # Return a copy
            copy = ModuleState(
                module_name=state.module_name,
                status=state.status,
                current_task=state.current_task,
                current_task_id=state.current_task_id,
                task_started_at=state.task_started_at,
                tasks_completed_today=state.tasks_completed_today,
                tasks_failed_today=state.tasks_failed_today,
                last_active=state.last_active,
                queue_depth=state.queue_depth,
                error_count_last_hour=state.error_count_last_hour,
                avg_task_duration_seconds=state.avg_task_duration_seconds,
                capabilities=list(state.capabilities),
            )
            return copy

    def get_all_states(self) -> dict[str, ModuleState]:
        """Return states of all registered modules."""
        with self._lock:
            return {
                name: ModuleState(
                    module_name=s.module_name,
                    status=s.status,
                    current_task=s.current_task,
                    current_task_id=s.current_task_id,
                    task_started_at=s.task_started_at,
                    tasks_completed_today=s.tasks_completed_today,
                    tasks_failed_today=s.tasks_failed_today,
                    last_active=s.last_active,
                    queue_depth=s.queue_depth,
                    error_count_last_hour=s.error_count_last_hour,
                    avg_task_duration_seconds=s.avg_task_duration_seconds,
                    capabilities=list(s.capabilities),
                )
                for name, s in self._states.items()
            }

    def get_available_modules(self) -> list[str]:
        """Return module names with status 'idle' — ready for work."""
        with self._lock:
            return [
                name
                for name, state in self._states.items()
                if state.status == "idle"
            ]

    def get_busy_modules(self) -> list[str]:
        """Return module names currently working."""
        with self._lock:
            return [
                name
                for name, state in self._states.items()
                if state.status == "busy"
            ]

    def find_capable_module(self, capability: str) -> Optional[str]:
        """Find which module can handle a given capability (tool name).

        If multiple modules can do it, prefer idle ones.
        If all capable modules are busy, return the one with shortest queue.

        Args:
            capability: Tool name or capability to search for.

        Returns:
            Module name, or None if no module has this capability.
        """
        with self._lock:
            idle_candidates = []
            busy_candidates = []

            for name, state in self._states.items():
                if capability in state.capabilities:
                    if state.status == "idle":
                        idle_candidates.append((name, state))
                    elif state.status != "offline":
                        busy_candidates.append((name, state))

            # Prefer idle modules
            if idle_candidates:
                return idle_candidates[0][0]

            # Fall back to busy module with shortest queue
            if busy_candidates:
                busy_candidates.sort(key=lambda x: x[1].queue_depth)
                return busy_candidates[0][0]

            return None

    def get_system_overview(self) -> dict[str, Any]:
        """High-level dashboard for Harbinger briefings.

        Returns:
            Dict with: modules_online, modules_busy, total_tasks_today,
            total_failures_today, busiest_module, most_idle_module, module_states.
        """
        with self._lock:
            if not self._states:
                return {
                    "modules_online": 0,
                    "modules_busy": 0,
                    "modules_idle": 0,
                    "modules_error": 0,
                    "modules_offline": 0,
                    "total_tasks_today": 0,
                    "total_failures_today": 0,
                    "busiest_module": None,
                    "most_idle_module": None,
                    "module_states": {},
                }

            online = sum(
                1 for s in self._states.values() if s.status not in ("offline",)
            )
            busy = sum(1 for s in self._states.values() if s.status == "busy")
            idle = sum(1 for s in self._states.values() if s.status == "idle")
            error = sum(1 for s in self._states.values() if s.status == "error")
            offline = sum(
                1 for s in self._states.values() if s.status == "offline"
            )

            total_tasks = sum(s.tasks_completed_today for s in self._states.values())
            total_failures = sum(s.tasks_failed_today for s in self._states.values())

            # Busiest = most tasks completed today
            busiest = max(
                self._states.values(),
                key=lambda s: s.tasks_completed_today,
            )
            # Most idle = fewest tasks completed today (among non-offline)
            active_states = [
                s for s in self._states.values() if s.status != "offline"
            ]
            most_idle = (
                min(active_states, key=lambda s: s.tasks_completed_today)
                if active_states
                else None
            )

            return {
                "modules_online": online,
                "modules_busy": busy,
                "modules_idle": idle,
                "modules_error": error,
                "modules_offline": offline,
                "total_tasks_today": total_tasks,
                "total_failures_today": total_failures,
                "busiest_module": busiest.module_name,
                "most_idle_module": most_idle.module_name if most_idle else None,
                "module_states": {
                    name: state.to_dict()
                    for name, state in self._states.items()
                },
            }

    def should_defer(self, module_name: str) -> bool:
        """Check if a module is overloaded and tasks should be deferred.

        Returns True if queue_depth > 10 or error_count_last_hour > 5.

        Args:
            module_name: Module to check.

        Returns:
            True if the module is overloaded.
        """
        with self._lock:
            if module_name not in self._states:
                return False
            state = self._states[module_name]
            return state.queue_depth > 10 or state.error_count_last_hour > 5

    def increment_queue(self, module_name: str) -> None:
        """Increment a module's queue depth (message waiting)."""
        with self._lock:
            if module_name in self._states:
                self._states[module_name].queue_depth += 1

    def decrement_queue(self, module_name: str) -> None:
        """Decrement a module's queue depth (message processed)."""
        with self._lock:
            if module_name in self._states:
                state = self._states[module_name]
                state.queue_depth = max(0, state.queue_depth - 1)

    def reset_daily_counters(self) -> None:
        """Reset tasks_completed_today and tasks_failed_today at midnight."""
        with self._lock:
            for state in self._states.values():
                state.tasks_completed_today = 0
                state.tasks_failed_today = 0
            logger.info("Daily counters reset for all modules")

    def snapshot(self) -> None:
        """Persist current states to disk for restart recovery."""
        with self._lock:
            data = {
                "snapshot_time": datetime.now().isoformat(),
                "modules": {
                    name: state.to_dict()
                    for name, state in self._states.items()
                },
            }

        try:
            with open(self._snapshot_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug("State snapshot saved to %s", self._snapshot_path)
        except Exception as e:
            logger.error("Failed to save state snapshot: %s", e)

    def restore_snapshot(self) -> bool:
        """Restore states from disk snapshot.

        Returns:
            True if snapshot was loaded successfully.
        """
        if not self._snapshot_path.exists():
            logger.debug("No snapshot file found at %s", self._snapshot_path)
            return False

        try:
            with open(self._snapshot_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            with self._lock:
                for name, state_data in data.get("modules", {}).items():
                    restored = ModuleState.from_dict(state_data)
                    # Set restored modules to offline until they check in
                    restored.status = "offline"
                    restored.current_task = None
                    restored.current_task_id = None
                    restored.task_started_at = None
                    self._states[name] = restored

            logger.info(
                "Restored state snapshot from %s (%d modules)",
                self._snapshot_path,
                len(data.get("modules", {})),
            )
            return True

        except Exception as e:
            logger.error("Failed to restore state snapshot: %s", e)
            return False
