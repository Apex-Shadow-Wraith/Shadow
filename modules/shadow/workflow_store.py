"""
Tool Chain Workflow Storage
==============================
When a multi-tool workflow succeeds, store the entire chain as a
reusable pattern in Grimoire. Over time this builds a library of
proven multi-step workflows that Shadow can recall and adapt.

Dual storage:
    - SQLite for fast structured lookup (by type, tools, recency)
    - Grimoire for semantic search (find workflows by task description)

Workflows are NEVER deleted. At most they are flagged as unused
and ranked lower in search results.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.workflow_store")


# =============================================================================
# Data Schemas
# =============================================================================

@dataclass
class WorkflowStep:
    """A single step in a stored workflow."""

    step_number: int
    tool: str
    action: str
    input_source: str       # "user" or "step_{N}"
    output_format: str      # "json", "text", "code", etc.
    transform: str          # how output is transformed before next step


@dataclass
class StoredWorkflow:
    """A complete stored workflow pattern."""

    workflow_id: str
    name: str
    task_type: str
    description: str
    steps: list[WorkflowStep]
    preconditions: list[str]
    tools_required: list[str]
    domain_tags: list[str]
    success_count: int
    last_used: float
    created_at: float
    average_duration: float
    flagged_unused: bool = False


# =============================================================================
# WorkflowStore
# =============================================================================

class WorkflowStore:
    """
    Stores and retrieves reusable multi-tool workflow patterns.

    Usage:
        store = WorkflowStore(grimoire=my_grimoire)

        # Store a successful workflow
        wf_id = store.store_workflow(
            task_type="research",
            description="Search web then summarize findings",
            steps=[{"tool": "reaper", "action": "web_search", ...}],
        )

        # Find workflows for a new task
        matches = store.find_workflow("look up competitor pricing")

        # Record that we used a workflow successfully
        store.record_usage(wf_id, success=True, duration=12.5)
    """

    def __init__(self, grimoire=None, db_path: str = "data/workflows.db"):
        """
        Initialize WorkflowStore.

        Args:
            grimoire: Optional Grimoire instance for semantic search.
                      If None, only SQLite-based lookup is available.
            db_path: Path to the SQLite database for workflow metadata.
        """
        self.grimoire = grimoire
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            self._init_db()
            logger.info("WorkflowStore initialized: %s", self.db_path)
        except Exception as e:
            logger.error("Failed to initialize WorkflowStore DB: %s", e)
            raise

    def _init_db(self):
        """Create the workflows table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                workflow_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                description TEXT NOT NULL,
                steps TEXT NOT NULL,
                preconditions TEXT NOT NULL,
                tools_required TEXT NOT NULL,
                domain_tags TEXT NOT NULL,
                success_count INTEGER DEFAULT 0,
                last_used REAL,
                created_at REAL NOT NULL,
                average_duration REAL DEFAULT 0.0,
                flagged_unused INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    # -------------------------------------------------------------------------
    # Store
    # -------------------------------------------------------------------------

    def store_workflow(
        self,
        task_type: str,
        description: str,
        steps: list[dict],
        domain_tags: list[str] | None = None,
        duration: float = 0,
        name: str | None = None,
    ) -> str:
        """
        Store a successful workflow as a reusable pattern.

        Deduplication: if a workflow with the exact same tool sequence
        already exists, update it instead of creating a duplicate.

        Returns:
            workflow_id of the stored (or updated) workflow.
        """
        try:
            domain_tags = domain_tags or []
            workflow_steps = self._parse_steps(steps)
            tools_required = list(dict.fromkeys(s.tool for s in workflow_steps))

            # Dedup: check for existing workflow with same tools in same order
            existing = self._find_duplicate(tools_required)
            if existing:
                self._update_existing(existing, description, duration)
                logger.info("Updated existing workflow %s", existing)
                return existing

            workflow_id = str(uuid.uuid4())
            now = time.time()
            wf_name = name or self._generate_name(task_type, tools_required)

            self.conn.execute(
                """INSERT INTO workflows
                   (workflow_id, name, task_type, description, steps,
                    preconditions, tools_required, domain_tags,
                    success_count, last_used, created_at, average_duration,
                    flagged_unused)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workflow_id,
                    wf_name,
                    task_type,
                    description,
                    json.dumps([asdict(s) for s in workflow_steps]),
                    json.dumps([]),
                    json.dumps(tools_required),
                    json.dumps(domain_tags),
                    1,
                    now,
                    now,
                    duration,
                    0,
                ),
            )
            self.conn.commit()

            # Also store in Grimoire for semantic search
            self._store_in_grimoire(workflow_id, description, task_type, tools_required)

            logger.info("Stored new workflow %s: %s", workflow_id, wf_name)
            return workflow_id

        except Exception as e:
            logger.error("Failed to store workflow: %s", e)
            raise

    # -------------------------------------------------------------------------
    # Find
    # -------------------------------------------------------------------------

    def find_workflow(
        self,
        task_description: str,
        task_type: str | None = None,
        required_tools: list[str] | None = None,
    ) -> list[StoredWorkflow]:
        """
        Search for matching workflows.

        Uses Grimoire semantic search when available, falls back to
        SQLite text search. Results are ranked by relevance * log(success_count + 1).

        Returns:
            Top 5 matching StoredWorkflow objects.
        """
        try:
            candidates = self._search_candidates(task_description, task_type)

            # Filter by required_tools
            if required_tools:
                candidates = [
                    wf for wf in candidates
                    if all(t in wf.tools_required for t in required_tools)
                ]

            # Rank: prefer proven workflows, deprioritize flagged ones
            def rank_key(wf: StoredWorkflow) -> float:
                base = math.log(wf.success_count + 1)
                if wf.flagged_unused:
                    base *= 0.1
                return base

            candidates.sort(key=rank_key, reverse=True)
            return candidates[:5]

        except Exception as e:
            logger.error("Failed to find workflow: %s", e)
            return []

    # -------------------------------------------------------------------------
    # Adapt
    # -------------------------------------------------------------------------

    def adapt_workflow(
        self, workflow: StoredWorkflow, new_task: str
    ) -> list[dict]:
        """
        Take an existing workflow and adapt it for a new similar task.

        Preserves the tool sequence and structure. Updates action
        descriptions for the new task context. Returns steps as
        list of dicts ready for ExecutionPlanner.
        """
        try:
            adapted = []
            for step in workflow.steps:
                adapted.append({
                    "step_number": step.step_number,
                    "tool": step.tool,
                    "action": f"{step.action} (adapted for: {new_task})",
                    "input_source": step.input_source,
                    "output_format": step.output_format,
                    "transform": step.transform,
                })
            return adapted

        except Exception as e:
            logger.error("Failed to adapt workflow: %s", e)
            return []

    # -------------------------------------------------------------------------
    # Record Usage
    # -------------------------------------------------------------------------

    def record_usage(
        self, workflow_id: str, success: bool, duration: float = 0
    ) -> bool:
        """
        Record that a workflow was used.

        On success: increment success_count, update last_used and average_duration.
        On failure: only log — don't decrement success_count.

        Returns:
            True if the record was updated.
        """
        try:
            row = self.conn.execute(
                "SELECT success_count, average_duration FROM workflows WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()

            if not row:
                logger.warning("Workflow %s not found for usage recording", workflow_id)
                return False

            now = time.time()

            if success:
                old_count = row["success_count"]
                old_avg = row["average_duration"]
                new_count = old_count + 1
                # Running average
                new_avg = ((old_avg * old_count) + duration) / new_count if duration else old_avg

                self.conn.execute(
                    """UPDATE workflows
                       SET success_count = ?, last_used = ?, average_duration = ?
                       WHERE workflow_id = ?""",
                    (new_count, now, new_avg, workflow_id),
                )
            else:
                # Failure: update last_used only, don't decrement
                self.conn.execute(
                    "UPDATE workflows SET last_used = ? WHERE workflow_id = ?",
                    (now, workflow_id),
                )
                logger.info("Workflow %s used but failed — logged, not decremented", workflow_id)

            self.conn.commit()
            return True

        except Exception as e:
            logger.error("Failed to record usage for %s: %s", workflow_id, e)
            return False

    # -------------------------------------------------------------------------
    # Popular / Stats
    # -------------------------------------------------------------------------

    def get_popular_workflows(self, limit: int = 10) -> list[StoredWorkflow]:
        """Return most-used workflows, ordered by success_count descending."""
        try:
            rows = self.conn.execute(
                "SELECT * FROM workflows ORDER BY success_count DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_workflow(r) for r in rows]

        except Exception as e:
            logger.error("Failed to get popular workflows: %s", e)
            return []

    def get_workflow_stats(self) -> dict:
        """
        Return aggregate stats for Harbinger briefings.

        Keys: total_workflows, total_usages, avg_success_rate,
              most_used_tools, avg_steps_per_workflow.
        """
        try:
            rows = self.conn.execute("SELECT * FROM workflows").fetchall()

            if not rows:
                return {
                    "total_workflows": 0,
                    "total_usages": 0,
                    "avg_success_rate": 0.0,
                    "most_used_tools": [],
                    "avg_steps_per_workflow": 0.0,
                }

            total_workflows = len(rows)
            total_usages = sum(r["success_count"] for r in rows)

            # Count tool frequency
            tool_counts: dict[str, int] = {}
            total_steps = 0
            for r in rows:
                tools = json.loads(r["tools_required"])
                for t in tools:
                    tool_counts[t] = tool_counts.get(t, 0) + 1
                steps = json.loads(r["steps"])
                total_steps += len(steps)

            most_used = sorted(tool_counts, key=tool_counts.get, reverse=True)[:5]
            avg_steps = total_steps / total_workflows

            return {
                "total_workflows": total_workflows,
                "total_usages": total_usages,
                "avg_success_rate": total_usages / total_workflows if total_workflows else 0.0,
                "most_used_tools": most_used,
                "avg_steps_per_workflow": round(avg_steps, 2),
            }

        except Exception as e:
            logger.error("Failed to get workflow stats: %s", e)
            return {
                "total_workflows": 0,
                "total_usages": 0,
                "avg_success_rate": 0.0,
                "most_used_tools": [],
                "avg_steps_per_workflow": 0.0,
            }

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def cleanup_unused(self, days: int = 90) -> int:
        """
        Flag workflows not used in N days. NEVER deletes.

        Returns:
            Count of newly flagged workflows.
        """
        try:
            cutoff = time.time() - (days * 86400)
            cursor = self.conn.execute(
                """UPDATE workflows
                   SET flagged_unused = 1
                   WHERE last_used < ? AND flagged_unused = 0""",
                (cutoff,),
            )
            self.conn.commit()
            count = cursor.rowcount
            if count:
                logger.info("Flagged %d unused workflows (>%d days)", count, days)
            return count

        except Exception as e:
            logger.error("Failed to cleanup unused workflows: %s", e)
            return 0

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _parse_steps(self, steps: list[dict]) -> list[WorkflowStep]:
        """Convert list of dicts to WorkflowStep objects."""
        result = []
        for i, s in enumerate(steps):
            result.append(WorkflowStep(
                step_number=s.get("step_number", i + 1),
                tool=s.get("tool", "unknown"),
                action=s.get("action", ""),
                input_source=s.get("input_source", "user"),
                output_format=s.get("output_format", "text"),
                transform=s.get("transform", ""),
            ))
        return result

    def _find_duplicate(self, tools_required: list[str]) -> str | None:
        """Find existing workflow with the exact same tool sequence."""
        rows = self.conn.execute("SELECT workflow_id, tools_required FROM workflows").fetchall()
        tools_json = json.dumps(tools_required)
        for r in rows:
            if r["tools_required"] == tools_json:
                return r["workflow_id"]
        return None

    def _update_existing(self, workflow_id: str, description: str, duration: float):
        """Update an existing workflow on dedup match."""
        now = time.time()
        self.conn.execute(
            """UPDATE workflows
               SET description = ?, last_used = ?, success_count = success_count + 1,
                   flagged_unused = 0
               WHERE workflow_id = ?""",
            (description, now, workflow_id),
        )
        self.conn.commit()

    def _generate_name(self, task_type: str, tools: list[str]) -> str:
        """Generate a human-readable name for a workflow."""
        tool_str = " -> ".join(tools[:4])
        if len(tools) > 4:
            tool_str += f" (+{len(tools) - 4} more)"
        return f"{task_type}: {tool_str}"

    def _store_in_grimoire(
        self, workflow_id: str, description: str, task_type: str, tools: list[str]
    ):
        """Store workflow in Grimoire for semantic search."""
        if not self.grimoire:
            logger.debug("No Grimoire available — skipping semantic storage")
            return

        try:
            content = f"Workflow [{task_type}]: {description}. Tools: {', '.join(tools)}"
            self.grimoire.remember(
                content=content,
                source="system",
                source_module="workflow_store",
                category="workflow",
                trust_level=0.8,
                tags=["workflow", task_type] + tools,
                metadata={"workflow_id": workflow_id},
            )
        except Exception as e:
            logger.warning("Grimoire storage failed (SQLite still has it): %s", e)

    def _search_candidates(
        self, task_description: str, task_type: str | None
    ) -> list[StoredWorkflow]:
        """Search for candidate workflows via Grimoire or SQLite fallback."""
        # Try Grimoire semantic search first
        if self.grimoire:
            try:
                results = self.grimoire.recall(
                    query=task_description,
                    n_results=20,
                    category="workflow",
                )
                if results:
                    return self._grimoire_results_to_workflows(results, task_type)
            except Exception as e:
                logger.warning("Grimoire search failed, falling back to SQLite: %s", e)

        # SQLite fallback: text search on description
        return self._sqlite_search(task_description, task_type)

    def _grimoire_results_to_workflows(
        self, results: list, task_type: str | None
    ) -> list[StoredWorkflow]:
        """Convert Grimoire recall results to StoredWorkflow objects."""
        workflows = []
        for r in results:
            metadata = r.get("metadata", {}) if isinstance(r, dict) else {}
            wf_id = metadata.get("workflow_id")
            if not wf_id:
                continue
            row = self.conn.execute(
                "SELECT * FROM workflows WHERE workflow_id = ?", (wf_id,)
            ).fetchone()
            if row:
                wf = self._row_to_workflow(row)
                if task_type and wf.task_type != task_type:
                    continue
                workflows.append(wf)
        return workflows

    def _sqlite_search(
        self, task_description: str, task_type: str | None
    ) -> list[StoredWorkflow]:
        """Fallback: search SQLite by description keywords and task_type."""
        query = "SELECT * FROM workflows WHERE 1=1"
        params: list[Any] = []

        if task_type:
            query += " AND task_type = ?"
            params.append(task_type)

        # Simple keyword matching on description
        keywords = task_description.lower().split()[:5]
        for kw in keywords:
            if len(kw) > 2:
                query += " AND LOWER(description) LIKE ?"
                params.append(f"%{kw}%")

        query += " ORDER BY success_count DESC LIMIT 20"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_workflow(r) for r in rows]

    def _row_to_workflow(self, row: sqlite3.Row) -> StoredWorkflow:
        """Convert a database row to a StoredWorkflow object."""
        steps_data = json.loads(row["steps"])
        return StoredWorkflow(
            workflow_id=row["workflow_id"],
            name=row["name"],
            task_type=row["task_type"],
            description=row["description"],
            steps=[WorkflowStep(**s) for s in steps_data],
            preconditions=json.loads(row["preconditions"]),
            tools_required=json.loads(row["tools_required"]),
            domain_tags=json.loads(row["domain_tags"]),
            success_count=row["success_count"],
            last_used=row["last_used"],
            created_at=row["created_at"],
            average_duration=row["average_duration"],
            flagged_unused=bool(row["flagged_unused"]),
        )

    def close(self):
        """Close the database connection."""
        try:
            self.conn.close()
        except Exception:
            pass
