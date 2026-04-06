"""
ShadowModule — Task Tracking & System Health
==============================================
Provides MCP tools for creating/managing tracked tasks and querying
module health. This is a BaseModule peer to the Orchestrator — it
handles task persistence in SQLite and delegates health queries to
the ModuleRegistry.

The Orchestrator is NOT a module — it IS the agent. ShadowModule
provides the tool interface for task management that the Orchestrator
can route to like any other module.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleRegistry, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.shadow_module")


class ShadowModule(BaseModule):
    """Task tracking and module health tools for the orchestrator.

    Manages a tasks table in SQLite for persistent task tracking.
    Queries the ModuleRegistry for module health information.
    """

    VALID_STATUSES = {"pending", "in_progress", "completed", "failed", "cancelled"}

    def __init__(self, config: dict[str, Any], registry: ModuleRegistry) -> None:
        super().__init__(
            name="shadow",
            description="Task tracking, system health — the orchestrator's toolbelt",
        )
        self._config = config
        self._registry = registry
        self._db_path = Path(config.get("db_path", "data/shadow_tasks.db"))
        self._db: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        """Create/open the tasks database."""
        self.status = ModuleStatus.STARTING
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self._db_path))
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA busy_timeout=5000")
            self._db.row_factory = sqlite3.Row
            self._create_tables()
            self.status = ModuleStatus.ONLINE
            logger.info("ShadowModule online. Tasks DB: %s", self._db_path)
        except Exception as e:
            self.status = ModuleStatus.ERROR
            logger.error("ShadowModule failed to initialize: %s", e)
            raise

    def _create_tables(self) -> None:
        """Create the tasks table if it doesn't exist."""
        cursor = self._db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                assigned_module TEXT NOT NULL,
                priority INTEGER DEFAULT 3,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                result TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status
            ON tasks(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_priority
            ON tasks(priority)
        """)
        self._db.commit()

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Route tool calls to task/health handlers."""
        start = time.time()
        try:
            if tool_name == "task_create":
                result = self._task_create(params)
            elif tool_name == "task_status":
                result = self._task_status(params)
            elif tool_name == "task_list":
                result = self._task_list(params)
            elif tool_name == "module_health":
                result = self._module_health(params)
            else:
                self._record_call(False)
                return ToolResult(
                    success=False,
                    content=None,
                    tool_name=tool_name,
                    module=self.name,
                    error=f"Unknown Shadow tool: {tool_name}",
                    execution_time_ms=(time.time() - start) * 1000,
                )

            result.execution_time_ms = (time.time() - start) * 1000
            self._record_call(result.success)
            return result

        except Exception as e:
            self._record_call(False)
            logger.error("ShadowModule execution error: %s", e)
            return ToolResult(
                success=False,
                content=None,
                tool_name=tool_name,
                module=self.name,
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
            )

    def _task_create(self, params: dict[str, Any]) -> ToolResult:
        """Create a tracked task in SQLite."""
        description = params.get("description", "")
        assigned_module = params.get("assigned_module", "")
        priority = params.get("priority", 3)

        if not description:
            return ToolResult(
                success=False, content=None,
                tool_name="task_create", module=self.name,
                error="description is required",
            )
        if not assigned_module:
            return ToolResult(
                success=False, content=None,
                tool_name="task_create", module=self.name,
                error="assigned_module is required",
            )
        if not isinstance(priority, int) or priority < 1 or priority > 5:
            return ToolResult(
                success=False, content=None,
                tool_name="task_create", module=self.name,
                error="priority must be an integer between 1 and 5",
            )

        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        cursor = self._db.cursor()
        cursor.execute("""
            INSERT INTO tasks (id, description, assigned_module, priority, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (task_id, description, assigned_module, priority, now, now))
        self._db.commit()

        task = {
            "task_id": task_id,
            "description": description,
            "assigned_module": assigned_module,
            "priority": priority,
            "status": "pending",
            "created_at": now,
        }

        return ToolResult(
            success=True, content=task,
            tool_name="task_create", module=self.name,
        )

    def _task_status(self, params: dict[str, Any]) -> ToolResult:
        """Get status of a specific task by ID."""
        task_id = params.get("task_id", "")
        if not task_id:
            return ToolResult(
                success=False, content=None,
                tool_name="task_status", module=self.name,
                error="task_id is required",
            )

        cursor = self._db.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

        if row is None:
            return ToolResult(
                success=False, content=None,
                tool_name="task_status", module=self.name,
                error=f"Task not found: {task_id}",
            )

        return ToolResult(
            success=True, content=dict(row),
            tool_name="task_status", module=self.name,
        )

    def _task_list(self, params: dict[str, Any]) -> ToolResult:
        """List tasks, optionally filtered by status."""
        status_filter = params.get("status_filter")
        cursor = self._db.cursor()

        if status_filter:
            if status_filter not in self.VALID_STATUSES:
                return ToolResult(
                    success=False, content=None,
                    tool_name="task_list", module=self.name,
                    error=f"Invalid status filter: {status_filter}. "
                          f"Valid: {sorted(self.VALID_STATUSES)}",
                )
            cursor.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY priority ASC, created_at DESC",
                (status_filter,),
            )
        else:
            cursor.execute(
                "SELECT * FROM tasks ORDER BY priority ASC, created_at DESC"
            )

        tasks = [dict(row) for row in cursor.fetchall()]
        return ToolResult(
            success=True, content=tasks,
            tool_name="task_list", module=self.name,
        )

    def _module_health(self, params: dict[str, Any]) -> ToolResult:
        """Check if a module is online and responsive."""
        module_name = params.get("module_name", "")
        if not module_name:
            return ToolResult(
                success=False, content=None,
                tool_name="module_health", module=self.name,
                error="module_name is required",
            )

        try:
            target = self._registry.get_module(module_name)
        except KeyError:
            return ToolResult(
                success=False, content=None,
                tool_name="module_health", module=self.name,
                error=f"Module not found: {module_name}",
            )

        return ToolResult(
            success=True, content=target.info,
            tool_name="module_health", module=self.name,
        )

    async def shutdown(self) -> None:
        """Close the tasks database."""
        if self._db is not None:
            self._db.close()
            self._db = None
        logger.info("ShadowModule shutting down. Tasks persist on disk.")
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        """ShadowModule's MCP tools."""
        return [
            {
                "name": "task_create",
                "description": "Create a tracked task assigned to a module",
                "parameters": {
                    "description": "str — what needs to be done",
                    "assigned_module": "str — which module handles this task",
                    "priority": "int — 1 (highest) to 5 (lowest), default 3",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "task_status",
                "description": "Get the current status of a tracked task",
                "parameters": {
                    "task_id": "str — UUID of the task to check",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "task_list",
                "description": "List tracked tasks, optionally filtered by status",
                "parameters": {
                    "status_filter": "str | None — pending, in_progress, completed, failed, cancelled",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "module_health",
                "description": "Check if a module is online and get its health metrics",
                "parameters": {
                    "module_name": "str — name of the module to check",
                },
                "permission_level": "autonomous",
            },
        ]
