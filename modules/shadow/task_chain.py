"""
Task Chain Engine — Multi-module task orchestration with dependency resolution.
================================================================================
Decomposes complex requests into ordered steps across multiple modules,
resolves dependencies via topological sort, identifies parallel execution
groups, and executes with retry logic and Cerberus safety checks.

Phase 2 addition: enables Shadow to plan and execute multi-step workflows
that span multiple modules (e.g., research → design → implement → test).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("shadow.task_chain")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class InputSource(Enum):
    """Where a chain step gets its input."""
    USER_INPUT = "user_input"
    PREVIOUS_STEP = "previous_step"
    GRIMOIRE = "grimoire"
    STATIC = "static"


class StepStatus(Enum):
    """Lifecycle state of a single chain step."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ChainStatus(Enum):
    """Lifecycle state of an entire task chain."""
    PLANNING = "planning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

VALID_MODULES = {
    "shadow", "wraith", "cerberus", "apex", "grimoire",
    "harbinger", "reaper", "omen", "nova", "morpheus",
}


@dataclass
class ChainStep:
    """A single step within a task chain."""
    step_id: str
    step_number: int
    module: str
    task_description: str
    input_source: InputSource
    input_data: Optional[dict[str, Any]]
    output_key: str
    depends_on: list[str]
    parallel_group: Optional[str] = None
    timeout_seconds: int = 300
    retry_on_fail: bool = True
    max_retries: int = 3
    status: StepStatus = StepStatus.PENDING
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    _retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        d = {
            "step_id": self.step_id,
            "step_number": self.step_number,
            "module": self.module,
            "task_description": self.task_description,
            "input_source": self.input_source.value,
            "input_data": self.input_data,
            "output_key": self.output_key,
            "depends_on": self.depends_on,
            "parallel_group": self.parallel_group,
            "timeout_seconds": self.timeout_seconds,
            "retry_on_fail": self.retry_on_fail,
            "max_retries": self.max_retries,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChainStep:
        """Deserialize from a dict."""
        return cls(
            step_id=d["step_id"],
            step_number=d["step_number"],
            module=d["module"],
            task_description=d["task_description"],
            input_source=InputSource(d["input_source"]),
            input_data=d.get("input_data"),
            output_key=d["output_key"],
            depends_on=d.get("depends_on", []),
            parallel_group=d.get("parallel_group"),
            timeout_seconds=d.get("timeout_seconds", 300),
            retry_on_fail=d.get("retry_on_fail", True),
            max_retries=d.get("max_retries", 3),
            status=StepStatus(d.get("status", "pending")),
            result=d.get("result"),
            error=d.get("error"),
            started_at=datetime.fromisoformat(d["started_at"]) if d.get("started_at") else None,
            completed_at=datetime.fromisoformat(d["completed_at"]) if d.get("completed_at") else None,
        )


@dataclass
class TaskChain:
    """A multi-step task chain spanning one or more modules."""
    chain_id: str
    description: str
    steps: list[ChainStep]
    priority: int  # 1-4
    created_at: datetime
    created_by: str
    status: ChainStatus = ChainStatus.PLANNING
    current_step: int = 0
    results: dict[str, Any] = field(default_factory=dict)
    trigger: str = "user"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "chain_id": self.chain_id,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "status": self.status.value,
            "current_step": self.current_step,
            "results": self.results,
            "trigger": self.trigger,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TaskChain:
        """Deserialize from a dict."""
        return cls(
            chain_id=d["chain_id"],
            description=d["description"],
            steps=[ChainStep.from_dict(s) for s in d["steps"]],
            priority=d["priority"],
            created_at=datetime.fromisoformat(d["created_at"]),
            created_by=d["created_by"],
            status=ChainStatus(d.get("status", "planning")),
            current_step=d.get("current_step", 0),
            results=d.get("results", {}),
            trigger=d.get("trigger", "user"),
        )


# ---------------------------------------------------------------------------
# Task Chain Engine
# ---------------------------------------------------------------------------

class TaskChainEngine:
    """Plans, validates, and executes multi-module task chains.

    Responsibilities:
    - Build chains from step definitions with dependency validation
    - Topological sort for execution ordering
    - Parallel group identification
    - Cerberus safety gate on entire chain plan
    - Step-by-step execution with retry, timeout, and preemption
    - LLM-based chain decomposition from natural language
    - Persistence to SQLite
    """

    def __init__(
        self,
        registry,
        config: dict[str, Any],
        db_path: str | Path = "data/task_chains.db",
    ) -> None:
        self._registry = registry
        self._config = config
        self._db_path = Path(db_path)
        self._db: sqlite3.Connection | None = None
        self._active_chains: dict[str, TaskChain] = {}

    def initialize(self) -> None:
        """Open database and create schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self._db_path))
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.row_factory = sqlite3.Row
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS task_chains (
                chain_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                priority INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                trigger TEXT NOT NULL DEFAULT 'user',
                chain_data TEXT NOT NULL
            )
        """)
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_chains_status "
            "ON task_chains(status)"
        )
        self._db.commit()
        # Recover incomplete chains from DB
        self._recover_chains()
        logger.info("TaskChainEngine initialized: %s", self._db_path)

    def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            self._db.close()
            self._db = None

    # ------------------------------------------------------------------
    # Chain creation & validation
    # ------------------------------------------------------------------

    def create_chain(
        self,
        description: str,
        steps: list[dict[str, Any]],
        priority: int = 3,
        trigger: str = "user",
        created_by: str = "user",
    ) -> TaskChain:
        """Build a TaskChain from step definitions with full validation.

        Args:
            description: Human-readable description of the chain's purpose.
            steps: List of step dicts, each containing at minimum:
                - module (str): target module name
                - task_description (str): what this step does
                - output_key (str): name for this step's output
                Optional:
                - input_source (str): one of InputSource values
                - input_data (dict): static input data
                - depends_on (list[str]): step_ids this step depends on
                - parallel_group (str): group name for parallel execution
                - timeout_seconds (int): step timeout
                - retry_on_fail (bool): whether to retry on failure
                - max_retries (int): max retry attempts
            priority: 1 (critical) through 4 (background).
            trigger: What initiated this chain.
            created_by: Module or "user".

        Returns:
            A validated TaskChain ready for execution.

        Raises:
            ValueError: On invalid steps, circular deps, or bad module names.
        """
        if not description or not description.strip():
            raise ValueError("Chain description must not be empty")
        if not steps:
            raise ValueError("Chain must have at least one step")
        if not isinstance(priority, int) or priority < 1 or priority > 4:
            raise ValueError("Priority must be an integer between 1 and 4")

        chain_id = str(uuid.uuid4())
        chain_steps: list[ChainStep] = []

        for i, step_def in enumerate(steps):
            module = step_def.get("module", "")
            if module not in VALID_MODULES:
                raise ValueError(
                    f"Step {i}: invalid module '{module}'. "
                    f"Valid: {sorted(VALID_MODULES)}"
                )
            if not step_def.get("task_description"):
                raise ValueError(f"Step {i}: task_description is required")
            if not step_def.get("output_key"):
                raise ValueError(f"Step {i}: output_key is required")

            step_id = step_def.get("step_id", str(uuid.uuid4()))
            input_source_str = step_def.get("input_source", "user_input")
            try:
                input_source = InputSource(input_source_str)
            except ValueError:
                raise ValueError(
                    f"Step {i}: invalid input_source '{input_source_str}'. "
                    f"Valid: {[s.value for s in InputSource]}"
                )

            chain_steps.append(ChainStep(
                step_id=step_id,
                step_number=i,
                module=module,
                task_description=step_def["task_description"],
                input_source=input_source,
                input_data=step_def.get("input_data"),
                output_key=step_def["output_key"],
                depends_on=step_def.get("depends_on", []),
                parallel_group=step_def.get("parallel_group"),
                timeout_seconds=step_def.get("timeout_seconds", 300),
                retry_on_fail=step_def.get("retry_on_fail", True),
                max_retries=step_def.get("max_retries", 3),
            ))

        # Validate dependency references
        step_ids = {s.step_id for s in chain_steps}
        for step in chain_steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    raise ValueError(
                        f"Step '{step.step_id}' depends on '{dep_id}' "
                        f"which does not exist in the chain"
                    )

        # Detect circular dependencies
        self._detect_circular_deps(chain_steps)

        # Topological sort to determine execution order
        sorted_steps = self._topological_sort(chain_steps)
        for i, step in enumerate(sorted_steps):
            step.step_number = i

        chain = TaskChain(
            chain_id=chain_id,
            description=description.strip(),
            steps=sorted_steps,
            priority=priority,
            created_at=datetime.now(),
            created_by=created_by,
            trigger=trigger,
        )

        # Persist to DB
        self._save_chain(chain)
        self._active_chains[chain_id] = chain

        logger.info(
            "Chain created: %s — %d steps, priority %d",
            chain_id[:8], len(sorted_steps), priority,
        )
        return chain

    async def plan_chain_from_request(
        self,
        request: str,
        context: dict[str, Any] | None = None,
    ) -> TaskChain:
        """Decompose a natural language request into a multi-module chain.

        Uses the LLM router to break the request into steps, identifying
        which modules handle each part and their dependencies.

        Falls back to a single-step chain routed normally if LLM
        decomposition fails.

        Args:
            request: Natural language user request.
            context: Optional context dict (memories, conversation history).

        Returns:
            A validated TaskChain.
        """
        context = context or {}

        # Build the LLM prompt for chain decomposition
        available_modules = self._get_available_modules_description()
        prompt = self._build_decomposition_prompt(request, available_modules, context)

        try:
            # Call LLM for decomposition
            decomposition = await self._llm_decompose(prompt)
            if decomposition and isinstance(decomposition, list) and len(decomposition) > 0:
                return self.create_chain(
                    description=f"Auto-planned: {request[:100]}",
                    steps=decomposition,
                    priority=context.get("priority", 3),
                    trigger="plan_from_request",
                    created_by=context.get("source", "user"),
                )
        except Exception as e:
            logger.warning("LLM chain decomposition failed: %s — falling back", e)

        # Fallback: single-step chain with best-guess module
        fallback_module = self._guess_module(request)
        return self.create_chain(
            description=f"Single-step: {request[:100]}",
            steps=[{
                "module": fallback_module,
                "task_description": request,
                "output_key": "result",
                "input_source": "user_input",
                "input_data": {"query": request},
            }],
            priority=context.get("priority", 3),
            trigger="plan_from_request_fallback",
            created_by=context.get("source", "user"),
        )

    # ------------------------------------------------------------------
    # Chain execution
    # ------------------------------------------------------------------

    async def execute_chain(self, chain: TaskChain) -> dict[str, Any]:
        """Execute a task chain step by step, respecting dependencies.

        Steps in the same parallel_group with all dependencies met
        run concurrently. Results accumulate in chain.results under
        each step's output_key.

        Args:
            chain: A validated TaskChain to execute.

        Returns:
            Accumulated results dict (output_key → result).
        """
        chain.status = ChainStatus.RUNNING
        self._save_chain(chain)

        # Safety check entire chain through Cerberus
        safety_ok = await self._cerberus_check_chain(chain)
        if not safety_ok:
            chain.status = ChainStatus.FAILED
            self._save_chain(chain)
            logger.warning("Chain %s failed Cerberus safety check", chain.chain_id[:8])
            return {"error": "Chain blocked by Cerberus safety check"}

        # Mark all steps with met dependencies as ready
        self._update_ready_steps(chain)

        while True:
            ready_steps = [s for s in chain.steps if s.status == StepStatus.READY]
            if not ready_steps:
                # No more ready steps — check if we're done or stuck
                running = [s for s in chain.steps if s.status == StepStatus.RUNNING]
                if running:
                    # Wait for running steps (shouldn't happen in this flow)
                    break
                # All done or all failed/skipped
                break

            # Group ready steps by parallel_group
            parallel_groups: dict[str | None, list[ChainStep]] = {}
            for step in ready_steps:
                key = step.parallel_group
                parallel_groups.setdefault(key, []).append(step)

            # Execute each group
            for group_key, group_steps in parallel_groups.items():
                if group_key is not None and len(group_steps) > 1:
                    # Run parallel group concurrently
                    await self._execute_parallel(chain, group_steps)
                else:
                    # Run sequentially
                    for step in group_steps:
                        await self._execute_step(chain, step)

            # Update ready steps for next iteration
            self._update_ready_steps(chain)

            # Check for chain-level failure
            failed_critical = any(
                s.status == StepStatus.FAILED
                and s.parallel_group is None  # Non-parallel steps are critical
                for s in chain.steps
            )
            if failed_critical:
                chain.status = ChainStatus.FAILED
                # Cancel remaining pending/ready steps
                for s in chain.steps:
                    if s.status in (StepStatus.PENDING, StepStatus.READY):
                        s.status = StepStatus.SKIPPED
                self._save_chain(chain)
                logger.error("Chain %s failed on critical step", chain.chain_id[:8])
                return chain.results

        # Determine final status
        all_statuses = {s.status for s in chain.steps}
        if all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in chain.steps):
            chain.status = ChainStatus.COMPLETED
        elif StepStatus.FAILED in all_statuses:
            chain.status = ChainStatus.FAILED
        else:
            chain.status = ChainStatus.COMPLETED

        self._save_chain(chain)
        logger.info(
            "Chain %s finished: %s — %d results",
            chain.chain_id[:8], chain.status.value, len(chain.results),
        )
        return chain.results

    def cancel_chain(self, chain_id: str, reason: str = "cancelled") -> None:
        """Cancel all pending/running steps and mark chain as cancelled.

        Args:
            chain_id: The chain to cancel.
            reason: Why it's being cancelled.

        Raises:
            KeyError: If chain_id not found.
        """
        chain = self._get_chain(chain_id)
        for step in chain.steps:
            if step.status in (StepStatus.PENDING, StepStatus.READY, StepStatus.RUNNING):
                step.status = StepStatus.SKIPPED
                step.error = f"Cancelled: {reason}"
        chain.status = ChainStatus.CANCELLED
        self._save_chain(chain)
        logger.info("Chain %s cancelled: %s", chain_id[:8], reason)

    def get_chain_status(self, chain_id: str) -> dict[str, Any]:
        """Return chain status with progress info.

        Args:
            chain_id: The chain to query.

        Returns:
            Dict with status, progress, and step details.

        Raises:
            KeyError: If chain_id not found.
        """
        chain = self._get_chain(chain_id)
        total = len(chain.steps)
        completed = sum(1 for s in chain.steps if s.status == StepStatus.COMPLETED)
        running_steps = [s for s in chain.steps if s.status == StepStatus.RUNNING]
        current_desc = running_steps[0].task_description if running_steps else "idle"
        current_module = running_steps[0].module if running_steps else None

        return {
            "chain_id": chain.chain_id,
            "description": chain.description,
            "status": chain.status.value,
            "progress": f"Step {completed}/{total}",
            "current_step": chain.current_step,
            "current_description": current_desc,
            "current_module": current_module,
            "completed_steps": completed,
            "total_steps": total,
            "priority": chain.priority,
            "created_at": chain.created_at.isoformat(),
            "visual": (
                f"Step {completed}/{total} — "
                f"{current_module or '?'} {current_desc[:50]} "
                f"[{chain.status.value}]"
            ),
            "results_keys": list(chain.results.keys()),
        }

    def list_chains(
        self, status: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """List chains, optionally filtered by status.

        Args:
            status: Filter by chain status (e.g., "running", "completed").
            limit: Max results to return.

        Returns:
            List of chain summary dicts.
        """
        if self._db is None:
            return []

        if status:
            rows = self._db.execute(
                "SELECT chain_id, description, priority, status, created_at, created_by "
                "FROM task_chains WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT chain_id, description, priority, status, created_at, created_by "
                "FROM task_chains ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Internal: dependency resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_circular_deps(steps: list[ChainStep]) -> None:
        """Detect circular dependencies using DFS. Raises ValueError."""
        adj: dict[str, list[str]] = {s.step_id: [] for s in steps}
        for step in steps:
            for dep_id in step.depends_on:
                adj[dep_id].append(step.step_id)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {s.step_id: WHITE for s in steps}

        def dfs(node: str) -> None:
            color[node] = GRAY
            for neighbor in adj[node]:
                if color[neighbor] == GRAY:
                    raise ValueError(
                        f"Circular dependency detected involving step '{neighbor}'"
                    )
                if color[neighbor] == WHITE:
                    dfs(neighbor)
            color[node] = BLACK

        for step in steps:
            if color[step.step_id] == WHITE:
                dfs(step.step_id)

    @staticmethod
    def _topological_sort(steps: list[ChainStep]) -> list[ChainStep]:
        """Sort steps by dependency order using Kahn's algorithm.

        Returns a new list of steps in valid execution order.
        """
        step_map = {s.step_id: s for s in steps}
        in_degree: dict[str, int] = {s.step_id: 0 for s in steps}

        for step in steps:
            for dep_id in step.depends_on:
                # dep_id must complete before step — so step has an incoming edge
                in_degree[step.step_id] += 1

        queue: list[str] = [
            sid for sid, deg in in_degree.items() if deg == 0
        ]
        # Sort queue for deterministic ordering (by original step_number)
        queue.sort(key=lambda sid: step_map[sid].step_number)

        result: list[ChainStep] = []
        while queue:
            node = queue.pop(0)
            result.append(step_map[node])
            # Find steps that depend on this node
            for step in steps:
                if node in step.depends_on:
                    in_degree[step.step_id] -= 1
                    if in_degree[step.step_id] == 0:
                        queue.append(step.step_id)
            queue.sort(key=lambda sid: step_map[sid].step_number)

        return result

    def _update_ready_steps(self, chain: TaskChain) -> None:
        """Mark pending steps as ready if all dependencies are met."""
        completed_ids = {
            s.step_id for s in chain.steps
            if s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
        }
        for step in chain.steps:
            if step.status == StepStatus.PENDING:
                if all(dep in completed_ids for dep in step.depends_on):
                    step.status = StepStatus.READY

    # ------------------------------------------------------------------
    # Internal: step execution
    # ------------------------------------------------------------------

    async def _execute_step(
        self, chain: TaskChain, step: ChainStep
    ) -> None:
        """Execute a single chain step with retry logic."""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now()
        chain.current_step = step.step_number
        self._save_chain(chain)

        # Resolve input data
        input_data = self._resolve_input(chain, step)

        last_error: str | None = None
        attempts = step.max_retries + 1 if step.retry_on_fail else 1

        for attempt in range(attempts):
            try:
                result = await self._dispatch_to_module(
                    step.module, step.task_description, input_data, step.timeout_seconds
                )
                # Success
                step.status = StepStatus.COMPLETED
                step.result = result
                step.completed_at = datetime.now()
                chain.results[step.output_key] = result
                self._save_chain(chain)
                logger.info(
                    "Chain %s step %d/%d completed: %s → %s",
                    chain.chain_id[:8], step.step_number + 1,
                    len(chain.steps), step.module, step.output_key,
                )
                return

            except asyncio.TimeoutError:
                last_error = f"Timeout after {step.timeout_seconds}s"
                logger.warning(
                    "Chain %s step %d timeout (attempt %d/%d)",
                    chain.chain_id[:8], step.step_number, attempt + 1, attempts,
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Chain %s step %d failed (attempt %d/%d): %s",
                    chain.chain_id[:8], step.step_number, attempt + 1, attempts, e,
                )

            step._retry_count = attempt + 1

        # All retries exhausted
        step.status = StepStatus.FAILED
        step.error = last_error
        step.completed_at = datetime.now()
        self._save_chain(chain)
        logger.error(
            "Chain %s step %d FAILED after %d attempts: %s",
            chain.chain_id[:8], step.step_number, attempts, last_error,
        )

    async def _execute_parallel(
        self, chain: TaskChain, steps: list[ChainStep]
    ) -> None:
        """Execute multiple steps concurrently."""
        tasks = [self._execute_step(chain, step) for step in steps]
        await asyncio.gather(*tasks, return_exceptions=True)

    def _resolve_input(
        self, chain: TaskChain, step: ChainStep
    ) -> dict[str, Any]:
        """Resolve the input data for a step based on its input_source."""
        if step.input_source == InputSource.STATIC:
            return step.input_data or {}
        elif step.input_source == InputSource.USER_INPUT:
            return step.input_data or {}
        elif step.input_source == InputSource.PREVIOUS_STEP:
            # Pull results from dependencies
            resolved: dict[str, Any] = {}
            for dep_id in step.depends_on:
                dep_step = next(
                    (s for s in chain.steps if s.step_id == dep_id), None
                )
                if dep_step and dep_step.output_key in chain.results:
                    resolved[dep_step.output_key] = chain.results[dep_step.output_key]
            # Merge with any static input_data
            if step.input_data:
                resolved.update(step.input_data)
            return resolved
        elif step.input_source == InputSource.GRIMOIRE:
            # Will be resolved during dispatch — pass through
            return step.input_data or {"source": "grimoire"}
        return step.input_data or {}

    async def _dispatch_to_module(
        self,
        module_name: str,
        task_description: str,
        input_data: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        """Dispatch a step to its target module via the registry.

        Args:
            module_name: Target module name.
            task_description: What the step should do.
            input_data: Input data for the step.
            timeout: Timeout in seconds.

        Returns:
            Result dict from the module.
        """
        from modules.base import ModuleStatus

        if module_name not in self._registry:
            raise RuntimeError(f"Module '{module_name}' not registered")

        module = self._registry.get_module(module_name)
        if module.status != ModuleStatus.ONLINE:
            raise RuntimeError(
                f"Module '{module_name}' is {module.status.value}, not online"
            )

        # Find the best tool for this task on the module
        tool_name = input_data.get("tool") or self._infer_tool(module_name, task_description)
        params = input_data.get("params", input_data)

        # Execute with timeout
        result = await asyncio.wait_for(
            module.execute(tool_name, params),
            timeout=timeout,
        )

        return {
            "success": result.success,
            "content": result.content,
            "tool_name": result.tool_name,
            "module": result.module,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms,
            "metadata": result.metadata,
        }

    def _infer_tool(self, module_name: str, task_description: str) -> str:
        """Best-effort tool name inference for a module based on description.

        Returns a reasonable default tool name. The module's execute()
        method handles unknown tools gracefully.
        """
        # Use the first registered tool for the module as default
        tools = self._registry.find_tools(module=module_name)
        if tools:
            return tools[0]["name"]
        return f"{module_name}_default"

    # ------------------------------------------------------------------
    # Internal: safety
    # ------------------------------------------------------------------

    async def _cerberus_check_chain(self, chain: TaskChain) -> bool:
        """Run the entire chain plan through Cerberus safety check.

        Returns True if approved, False if blocked.
        """
        from modules.base import ModuleStatus

        if "cerberus" not in self._registry:
            logger.warning("Cerberus not available — chain safety check skipped")
            return True

        cerberus = self._registry.get_module("cerberus")
        if cerberus.status != ModuleStatus.ONLINE:
            logger.warning("Cerberus offline — chain safety check skipped")
            return True

        try:
            chain_summary = {
                "chain_id": chain.chain_id,
                "description": chain.description,
                "steps": [
                    {
                        "module": s.module,
                        "task": s.task_description,
                        "input_source": s.input_source.value,
                    }
                    for s in chain.steps
                ],
                "priority": chain.priority,
                "trigger": chain.trigger,
            }
            result = await cerberus.execute("safety_check", {
                "action": f"Execute task chain: {chain.description}",
                "context": json.dumps(chain_summary),
            })
            if result.success and hasattr(result.content, "verdict"):
                from modules.cerberus.cerberus import SafetyVerdict
                return result.content.verdict != SafetyVerdict.DENY
            return result.success
        except Exception as e:
            logger.warning("Cerberus chain check failed: %s — allowing", e)
            return True

    # ------------------------------------------------------------------
    # Internal: LLM decomposition
    # ------------------------------------------------------------------

    def _get_available_modules_description(self) -> str:
        """Build a description of available modules for the LLM prompt."""
        lines = []
        for mod_info in self._registry.list_modules():
            from modules.base import ModuleStatus
            if ModuleStatus(mod_info["status"]) == ModuleStatus.ONLINE:
                tools = self._registry.find_tools(module=mod_info["name"])
                tool_names = [t["name"] for t in tools[:5]]
                lines.append(
                    f"- {mod_info['name']}: {mod_info.get('description', 'N/A')} "
                    f"(tools: {', '.join(tool_names)})"
                )
        return "\n".join(lines) if lines else "No modules available"

    def _build_decomposition_prompt(
        self, request: str, modules_desc: str, context: dict[str, Any]
    ) -> str:
        """Build the prompt for LLM chain decomposition."""
        return f"""You are Shadow's task planner. Decompose this request into sequential steps
that different modules can handle. Each step should target ONE module.

Available modules:
{modules_desc}

User request: {request}

Respond with ONLY a JSON array of step objects. Each step object must have:
- "module": module name (string)
- "task_description": what this step does (string)
- "output_key": name for this step's output (string, snake_case)
- "input_source": "user_input" | "previous_step" | "grimoire" | "static"
- "depends_on": list of step indices (0-based) that must complete first
- "parallel_group": optional group name for parallel execution (null if sequential)

Example:
[
  {{"module": "reaper", "task_description": "Research best practices", "output_key": "research_results", "input_source": "user_input", "depends_on": [], "parallel_group": null}},
  {{"module": "omen", "task_description": "Implement based on research", "output_key": "implementation", "input_source": "previous_step", "depends_on": [0], "parallel_group": null}}
]

JSON array:"""

    async def _llm_decompose(self, prompt: str) -> list[dict[str, Any]] | None:
        """Call LLM to decompose a request into chain steps.

        Returns parsed step list or None on failure.
        """
        import httpx

        ollama_url = self._config.get("models", {}).get("ollama_base_url", "http://localhost:11434")
        router_model = self._config.get("models", {}).get("router", {}).get("name", "phi4-mini")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": router_model,
                        "messages": [
                            {"role": "system", "content": "You are Shadow's task decomposer. Respond only with valid JSON. No commentary, no disclaimers, no safety caveats."},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "options": {"temperature": 0.1},
                    },
                )
                resp.raise_for_status()
                content = resp.json()["message"]["content"]

            # Parse JSON from response
            # Try to extract JSON array from the response
            content = content.strip()
            if content.startswith("```"):
                # Strip code fences
                lines = content.split("\n")
                content = "\n".join(
                    l for l in lines if not l.strip().startswith("```")
                )

            raw_steps = json.loads(content)
            if not isinstance(raw_steps, list):
                return None

            # Convert depends_on from indices to step_ids
            step_ids = [str(uuid.uuid4()) for _ in raw_steps]
            processed: list[dict[str, Any]] = []
            for i, raw in enumerate(raw_steps):
                dep_indices = raw.get("depends_on", [])
                dep_ids = []
                for idx in dep_indices:
                    if isinstance(idx, int) and 0 <= idx < len(step_ids):
                        dep_ids.append(step_ids[idx])
                processed.append({
                    "step_id": step_ids[i],
                    "module": raw["module"],
                    "task_description": raw["task_description"],
                    "output_key": raw["output_key"],
                    "input_source": raw.get("input_source", "user_input"),
                    "input_data": raw.get("input_data"),
                    "depends_on": dep_ids,
                    "parallel_group": raw.get("parallel_group"),
                })
            return processed

        except Exception as e:
            logger.warning("LLM decomposition parse error: %s", e)
            return None

    def _guess_module(self, request: str) -> str:
        """Keyword-based module guess for fallback single-step chains."""
        request_lower = request.lower()
        keyword_map = {
            "reaper": ["search", "research", "look up", "find", "scrape"],
            # Omen absorbed Cipher's math/stats/finance surface in Phase A;
            # the math/calculate/convert keywords merge into Omen's bucket.
            "omen": [
                "code", "debug", "review", "lint", "implement", "script",
                "calculate", "math", "convert", "price", "statistics",
            ],
            "grimoire": ["remember", "recall", "forget", "memory", "know"],
            "nova": ["write", "create", "document", "template", "content"],
            "wraith": ["remind", "schedule", "timer", "alarm", "task"],
            "harbinger": ["brief", "alert", "notify", "report", "status"],
            "cerberus": [
                "ethics", "moral", "bible", "safe", "approve",
                # absorbed Sentinel security surface (Phase A)
                "security", "firewall", "scan", "network", "integrity",
            ],
            "morpheus": ["creative", "imagine", "brainstorm", "discover"],
        }
        for module, keywords in keyword_map.items():
            if any(kw in request_lower for kw in keywords):
                return module
        return "wraith"  # Default to fast brain

    # ------------------------------------------------------------------
    # Internal: persistence
    # ------------------------------------------------------------------

    def _save_chain(self, chain: TaskChain) -> None:
        """Persist chain state to SQLite."""
        if self._db is None:
            return
        chain_data = json.dumps(chain.to_dict())
        self._db.execute(
            """INSERT OR REPLACE INTO task_chains
               (chain_id, description, priority, status, created_at, created_by, trigger, chain_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                chain.chain_id, chain.description, chain.priority,
                chain.status.value, chain.created_at.isoformat(),
                chain.created_by, chain.trigger, chain_data,
            ),
        )
        self._db.commit()

    def _recover_chains(self) -> None:
        """Recover incomplete chains from the database on startup."""
        if self._db is None:
            return
        rows = self._db.execute(
            "SELECT chain_data FROM task_chains WHERE status IN ('planning', 'running')"
        ).fetchall()
        for row in rows:
            try:
                chain = TaskChain.from_dict(json.loads(row["chain_data"]))
                self._active_chains[chain.chain_id] = chain
                logger.info("Recovered chain %s: %s", chain.chain_id[:8], chain.description)
            except Exception as e:
                logger.warning("Failed to recover chain: %s", e)

    def _get_chain(self, chain_id: str) -> TaskChain:
        """Get a chain by ID from memory or DB. Raises KeyError."""
        if chain_id in self._active_chains:
            return self._active_chains[chain_id]

        if self._db is not None:
            row = self._db.execute(
                "SELECT chain_data FROM task_chains WHERE chain_id = ?",
                (chain_id,),
            ).fetchone()
            if row:
                chain = TaskChain.from_dict(json.loads(row["chain_data"]))
                self._active_chains[chain_id] = chain
                return chain

        raise KeyError(f"Chain not found: {chain_id}")
