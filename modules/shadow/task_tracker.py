"""
TaskTracker — SQLite-backed task persistence for the Shadow orchestrator.
=========================================================================
Tracks tasks assigned to modules with priority, status transitions,
and cleanup of stale entries.

Schema: shadow_tasks table
- task_id (TEXT PK, uuid4)
- description (TEXT NOT NULL)
- assigned_module (TEXT NOT NULL)
- priority (INTEGER DEFAULT 5, 1=highest)
- status (TEXT DEFAULT 'queued')
- created_at (REAL, epoch seconds)
- updated_at (REAL, epoch seconds)
- result (TEXT, nullable JSON)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.task_tracker")

VALID_STATUSES = {"queued", "running", "completed", "failed", "cancelled"}

VALID_MODULES = {
    "shadow", "wraith", "cerberus", "apex", "grimoire",
    "harbinger", "reaper", "cipher", "omen", "nova", "morpheus",
}


class TaskTracker:
    """SQLite-backed task tracker for the Shadow orchestrator."""

    def __init__(self, db_path: str | Path = "data/shadow_tasks.db") -> None:
        self._db_path = Path(db_path)
        self._db: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """Open database and create schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self._db_path))
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.row_factory = sqlite3.Row
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS shadow_tasks (
                task_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                assigned_module TEXT NOT NULL,
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'queued',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                result TEXT
            )
        """)
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_shadow_tasks_status ON shadow_tasks(status)"
        )
        self._db.commit()
        logger.info("TaskTracker initialized: %s", self._db_path)

    def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            self._db.close()
            self._db = None

    def create(self, description: str, assigned_module: str, priority: int = 5) -> str:
        """Create a new task. Returns the task_id (uuid4).

        Raises ValueError for empty description, invalid module, or bad priority.
        """
        if not description or not description.strip():
            raise ValueError("description must not be empty")
        if assigned_module not in VALID_MODULES:
            raise ValueError(
                f"Invalid module '{assigned_module}'. "
                f"Valid: {sorted(VALID_MODULES)}"
            )
        if not isinstance(priority, int) or priority < 1 or priority > 10:
            raise ValueError("priority must be an integer between 1 and 10")

        task_id = str(uuid.uuid4())
        now = time.time()

        self._db.execute(
            """INSERT INTO shadow_tasks
               (task_id, description, assigned_module, priority, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'queued', ?, ?)""",
            (task_id, description.strip(), assigned_module, priority, now, now),
        )
        self._db.commit()
        logger.info("Task created: %s → %s (priority %d)", task_id[:8], assigned_module, priority)
        return task_id

    def get_status(self, task_id: str) -> dict[str, Any]:
        """Get full task record by ID. Raises KeyError if not found."""
        row = self._db.execute(
            "SELECT * FROM shadow_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Task not found: {task_id}")
        return self._row_to_dict(row)

    def list_tasks(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        """List tasks, optionally filtered by status.

        Raises ValueError for invalid status_filter.
        """
        if status_filter is not None and status_filter not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status_filter}'. Valid: {sorted(VALID_STATUSES)}"
            )

        if status_filter:
            rows = self._db.execute(
                "SELECT * FROM shadow_tasks WHERE status = ? ORDER BY priority ASC, created_at DESC",
                (status_filter,),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM shadow_tasks ORDER BY priority ASC, created_at DESC"
            ).fetchall()

        return [self._row_to_dict(r) for r in rows]

    def update_status(self, task_id: str, status: str, result: Any = None) -> None:
        """Update a task's status and optionally set its result (as JSON).

        Raises KeyError if task not found, ValueError for invalid status.
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Valid: {sorted(VALID_STATUSES)}")

        # Verify task exists
        existing = self._db.execute(
            "SELECT task_id FROM shadow_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if existing is None:
            raise KeyError(f"Task not found: {task_id}")

        result_json = json.dumps(result) if result is not None else None
        now = time.time()

        self._db.execute(
            "UPDATE shadow_tasks SET status = ?, result = ?, updated_at = ? WHERE task_id = ?",
            (status, result_json, now, task_id),
        )
        self._db.commit()
        logger.info("Task %s → %s", task_id[:8], status)

    def cancel(self, task_id: str) -> bool:
        """Cancel a task. Only queued or running tasks can be cancelled.

        Returns True if cancelled, False if task is in a terminal state.
        Raises KeyError if task not found.
        """
        task = self.get_status(task_id)
        if task["status"] not in ("queued", "running"):
            return False

        self.update_status(task_id, "cancelled")
        return True

    def cleanup(self, older_than_days: int = 30) -> int:
        """Delete completed/failed/cancelled tasks older than N days.

        Returns the number of deleted rows.
        """
        cutoff = time.time() - (older_than_days * 86400)
        cursor = self._db.execute(
            """DELETE FROM shadow_tasks
               WHERE status IN ('completed', 'failed', 'cancelled')
               AND created_at < ?""",
            (cutoff,),
        )
        self._db.commit()
        deleted = cursor.rowcount
        if deleted:
            logger.info("Cleaned up %d stale tasks (older than %d days)", deleted, older_than_days)
        return deleted

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a sqlite3.Row to a plain dict, parsing result JSON."""
        d = dict(row)
        if d.get("result") is not None:
            try:
                d["result"] = json.loads(d["result"])
            except (json.JSONDecodeError, TypeError):
                pass  # Leave as raw string
        return d
