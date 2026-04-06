"""
Apex — API Fallback and Active Learning
=========================================
Bridge between today's local capabilities and tomorrow's.
Every API call is a learning opportunity.

Design Principle: Every API call is a learning opportunity. The goal
is to make Apex progressively less necessary over time. If Shadow
keeps escalating the same task type, that's a training signal, not
an acceptable dependency.

Phase 1: Apex Basic — simple API fallback with logging. No teaching
cycle yet. Every call logged with full metadata for future training.

Phase 1.5: Escalation-Learning Cycle — structured logging of every
escalation, teaching signal extraction, Grimoire storage. The loop:
escalate → extract signal → store → reuse → reduce escalations.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.apex")


class EscalationLog:
    """SQLite-backed log of every Apex escalation.

    Tracks what was escalated, why, to which API, at what cost,
    and what teaching signal was extracted. Over time, this log
    reveals which task types keep escalating (learning priorities)
    and whether stored teaching signals actually reduce future
    escalations.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize escalation log.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create the escalation log table if it doesn't exist."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS apex_escalation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    task_summary TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    api_provider TEXT NOT NULL,
                    api_model TEXT NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cost_usd REAL,
                    response_quality TEXT,
                    teaching_signal TEXT,
                    grimoire_memory_id TEXT,
                    local_retry_success INTEGER DEFAULT 0
                )
            """)

    def log_escalation(
        self,
        task_type: str,
        task_summary: str,
        reason: str,
        api_provider: str,
        api_model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> str:
        """Log an escalation event.

        Args:
            task_type: Category of the task (e.g. "code_generation").
            task_summary: Brief description of the task.
            reason: Why the local model couldn't handle it.
            api_provider: Which API was used ("claude" or "openai").
            api_model: Specific model name.
            input_tokens: Tokens sent to the API.
            output_tokens: Tokens received from the API.
            cost_usd: Cost of this call in USD.

        Returns:
            The string ID of the new log entry.
        """
        now = datetime.now().isoformat()
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO apex_escalation_log
                   (timestamp, task_type, task_summary, reason,
                    api_provider, api_model, input_tokens, output_tokens,
                    cost_usd)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (now, task_type, task_summary, reason,
                 api_provider, api_model, input_tokens, output_tokens,
                 cost_usd),
            )
            return str(cursor.lastrowid)

    def update_teaching_signal(
        self,
        log_id: str,
        teaching_signal: str,
        grimoire_memory_id: str | None = None,
    ) -> None:
        """Attach a teaching signal to an existing escalation log entry.

        Args:
            log_id: The escalation log entry ID.
            teaching_signal: JSON-encoded teaching signal.
            grimoire_memory_id: Optional Grimoire memory ID where
                the teaching signal was stored.
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """UPDATE apex_escalation_log
                   SET teaching_signal = ?, grimoire_memory_id = ?
                   WHERE id = ?""",
                (teaching_signal, grimoire_memory_id, int(log_id)),
            )

    def mark_local_retry_success(self, log_id: str) -> None:
        """Mark that a similar task was later handled locally.

        This is the key metric: proof that the teaching cycle works.

        Args:
            log_id: The escalation log entry ID.
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """UPDATE apex_escalation_log
                   SET local_retry_success = 1
                   WHERE id = ?""",
                (int(log_id),),
            )

    def get_escalation_stats(self, days: int = 7) -> dict[str, Any]:
        """Get escalation statistics for the given time window.

        Args:
            days: Number of days to look back.

        Returns:
            Dict with total_escalations, by_task_type, total_cost,
            top_reasons, and local_retry_success_rate.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Total escalations
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM apex_escalation_log WHERE timestamp >= ?",
                (cutoff,),
            ).fetchone()
            total = row["cnt"]

            # By task type
            rows = conn.execute(
                """SELECT task_type, COUNT(*) as cnt
                   FROM apex_escalation_log WHERE timestamp >= ?
                   GROUP BY task_type ORDER BY cnt DESC""",
                (cutoff,),
            ).fetchall()
            by_task_type = {r["task_type"]: r["cnt"] for r in rows}

            # Total cost
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) as total FROM apex_escalation_log WHERE timestamp >= ?",
                (cutoff,),
            ).fetchone()
            total_cost = round(row["total"], 4)

            # Top 3 reasons
            rows = conn.execute(
                """SELECT reason, COUNT(*) as cnt
                   FROM apex_escalation_log WHERE timestamp >= ?
                   GROUP BY reason ORDER BY cnt DESC LIMIT 3""",
                (cutoff,),
            ).fetchall()
            top_reasons = [r["reason"] for r in rows]

            # Local retry success rate
            row = conn.execute(
                """SELECT
                     COUNT(*) as total,
                     SUM(local_retry_success) as successes
                   FROM apex_escalation_log WHERE timestamp >= ?""",
                (cutoff,),
            ).fetchone()
            success_rate = 0.0
            if row["total"] > 0:
                success_rate = round(
                    (row["successes"] or 0) / row["total"], 4
                )

        return {
            "total_escalations": total,
            "by_task_type": by_task_type,
            "total_cost": total_cost,
            "top_reasons": top_reasons,
            "local_retry_success_rate": success_rate,
            "window_days": days,
        }

    def get_frequent_escalation_types(
        self, min_count: int = 3, days: int = 14
    ) -> list[str]:
        """Get task types that keep escalating — learning priorities.

        Args:
            min_count: Minimum escalation count to be considered frequent.
            days: Number of days to look back.

        Returns:
            List of task type strings sorted by frequency (descending).
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT task_type, COUNT(*) as cnt
                   FROM apex_escalation_log WHERE timestamp >= ?
                   GROUP BY task_type HAVING cnt >= ?
                   ORDER BY cnt DESC""",
                (cutoff, min_count),
            ).fetchall()
        return [r["task_type"] for r in rows]

    def get_recent_teaching_signals(
        self, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Get recent escalations that have teaching signals.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of dicts with id, timestamp, task_type, task_summary,
            teaching_signal, and grimoire_memory_id.
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT id, timestamp, task_type, task_summary,
                          teaching_signal, grimoire_memory_id
                   FROM apex_escalation_log
                   WHERE teaching_signal IS NOT NULL
                   ORDER BY timestamp DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


class TeachingExtractor:
    """Extract teaching signals from API escalation responses.

    Phase 1: Simple structured extraction without LLM analysis.
    Phase 2 (future): Use local model to identify reusable patterns.
    """

    def extract_teaching_signal(
        self,
        task_input: str,
        api_response: str,
        task_type: str,
    ) -> dict[str, Any]:
        """Extract a teaching signal from an escalation.

        Phase 1 implementation: structures the escalation data for
        storage without LLM analysis. The key_patterns list is empty
        for now — Phase 2 will use the local model to populate it.

        Args:
            task_input: The original task sent to the API.
            api_response: The API's response.
            task_type: Category of the task.

        Returns:
            Dict with task_type, input_summary, approach, key_patterns.
        """
        return {
            "task_type": task_type,
            "input_summary": task_input[:200],
            "approach": api_response[:500],
            "key_patterns": [],  # Phase 2: LLM-extracted patterns
        }


class Apex(BaseModule):
    """API fallback to Claude/OpenAI when local models fail.

    Apex tracks every call for cost analysis and training data.
    Claude is the primary API, OpenAI is the fallback.
    """

    # Approximate costs per 1K tokens (as of early 2026)
    COST_PER_1K = {
        "claude": {"input": 0.015, "output": 0.075},
        "openai": {"input": 0.01, "output": 0.03},
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Apex.

        Args:
            config: Module configuration from shadow_config.yaml.
        """
        super().__init__(
            name="apex",
            description="API fallback — Claude/GPT with cost tracking and learning",
        )
        self._config = config or {}
        self._anthropic_key: str | None = None
        self._openai_key: str | None = None
        self._call_log: list[dict[str, Any]] = []
        self._total_cost: float = 0.0
        self._daily_cost: float = 0.0
        self._daily_cost_date: str = ""
        self._log_file = Path(
            self._config.get("log_file", "data/apex_log.json")
        )

        # Escalation-learning infrastructure
        self._escalation_log: EscalationLog | None = None
        self._teaching_extractor: TeachingExtractor | None = None
        self._grimoire: Any = None  # Injected via set_grimoire()

    async def initialize(self) -> None:
        """Start Apex. Load API keys from environment."""
        self.status = ModuleStatus.STARTING
        try:
            self._anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
            self._openai_key = os.environ.get("OPENAI_API_KEY")

            if not self._anthropic_key and not self._openai_key:
                logger.warning(
                    "No API keys found. Apex will run in dry-run mode."
                )

            self._load_log()

            # Initialize escalation-learning infrastructure
            escalation_db = Path(
                self._config.get(
                    "escalation_db", "data/apex_escalation.db"
                )
            )
            self._escalation_log = EscalationLog(escalation_db)
            self._teaching_extractor = TeachingExtractor()
            logger.info("Escalation-learning cycle initialized.")

            self.status = ModuleStatus.ONLINE
            api_status = []
            if self._anthropic_key:
                api_status.append("Claude")
            if self._openai_key:
                api_status.append("OpenAI")
            logger.info(
                "Apex online. APIs available: %s. Total cost to date: $%.4f",
                ", ".join(api_status) or "none (dry-run)",
                self._total_cost,
            )
        except Exception as e:
            self.status = ModuleStatus.ERROR
            logger.error("Apex failed to initialize: %s", e)
            raise

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute an Apex tool.

        Args:
            tool_name: Which tool to invoke.
            params: Tool-specific parameters.

        Returns:
            ToolResult with success/failure and content.
        """
        start = time.time()
        try:
            handlers = {
                "apex_query": self._apex_query,
                "apex_teach": self._apex_teach,
                "apex_log": self._apex_log,
                "apex_cost_report": self._apex_cost_report,
                "escalation_stats": self._escalation_stats,
                "escalation_frequent": self._escalation_frequent,
                "teaching_review": self._teaching_review,
            }

            handler = handlers.get(tool_name)
            if handler is None:
                result = ToolResult(
                    success=False, content=None, tool_name=tool_name,
                    module=self.name, error=f"Unknown tool: {tool_name}",
                )
            else:
                result = handler(params)

            result.execution_time_ms = (time.time() - start) * 1000
            self._record_call(result.success)
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._record_call(False)
            logger.error("Apex tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False, content=None, tool_name=tool_name,
                module=self.name, error=str(e), execution_time_ms=elapsed,
            )

    async def shutdown(self) -> None:
        """Shut down Apex. Persist call log."""
        self._save_log()
        self.status = ModuleStatus.OFFLINE
        logger.info("Apex offline. Total cost: $%.4f", self._total_cost)

    def get_tools(self) -> list[dict[str, Any]]:
        """Return Apex's tool definitions."""
        return [
            {
                "name": "apex_query",
                "description": "Send task to Claude/GPT API",
                "parameters": {"task": "str", "model_preference": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "apex_teach",
                "description": "Send teaching request with failure context to API",
                "parameters": {
                    "task": "str",
                    "failed_approaches": "list",
                    "successful_answer": "str",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "apex_log",
                "description": "Log API usage data (cost, reason, assessment)",
                "parameters": {"entry": "dict"},
                "permission_level": "autonomous",
            },
            {
                "name": "apex_cost_report",
                "description": "Generate spending report for Harbinger",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "escalation_stats",
                "description": "Get escalation statistics",
                "parameters": {"days": "int"},
                "permission_level": "autonomous",
            },
            {
                "name": "escalation_frequent",
                "description": "Get task types that frequently escalate",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "teaching_review",
                "description": "Get recent teaching signals for review",
                "parameters": {"limit": "int"},
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _apex_query(self, params: dict[str, Any]) -> ToolResult:
        """Send a task to a frontier API.

        Phase 1: Logs the request. Actual API calls require httpx
        (deferred to avoid test dependencies on live APIs).

        Args:
            params: 'task' (required), 'model_preference' (claude/openai).
        """
        task = params.get("task", "")
        if not task:
            return ToolResult(
                success=False, content=None, tool_name="apex_query",
                module=self.name, error="Task is required",
            )

        preference = params.get("model_preference", "claude")
        api = self._select_api(preference)

        # Log the call
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task": task[:500],  # Truncate for logging
            "api_selected": api,
            "model_preference": preference,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost": 0.0,
            "teaching_triggered": False,
            "status": "dry_run" if api == "none" else "logged",
        }
        self._call_log.append(entry)
        self._save_log()

        if api == "none":
            return ToolResult(
                success=False, content=None, tool_name="apex_query",
                module=self.name,
                error="No API keys available. Configure ANTHROPIC_API_KEY or OPENAI_API_KEY.",
            )

        # Phase 1: Log only, no actual API call
        logger.info("Apex query logged (dry-run): api=%s, task=%s", api, task[:50])

        # Escalation-learning cycle: log, extract, store
        self._record_escalation(
            task_type=params.get("task_type", "general"),
            task_summary=task[:500],
            reason=params.get("reason", "local_model_insufficient"),
            api_provider=api,
            api_model=params.get("model_preference", "claude"),
            api_response=params.get("api_response", ""),
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )

        return ToolResult(
            success=True,
            content={
                "api": api,
                "status": "logged",
                "message": f"Query logged for {api} API. Actual dispatch deferred to Phase 2.",
                "task_preview": task[:200],
            },
            tool_name="apex_query",
            module=self.name,
        )

    def _apex_teach(self, params: dict[str, Any]) -> ToolResult:
        """Request a teaching explanation from the API.

        Architecture: 'Shadow sends a follow-up call to Apex: Here's the
        task, here's my 12 failed approaches, here's your successful answer.
        Explain what I was doing wrong and what principle I should learn.'

        Args:
            params: 'task', 'failed_approaches' (list), 'successful_answer'.
        """
        task = params.get("task", "")
        failed = params.get("failed_approaches", [])
        answer = params.get("successful_answer", "")

        if not task:
            return ToolResult(
                success=False, content=None, tool_name="apex_teach",
                module=self.name, error="Task is required",
            )

        teaching_request = {
            "timestamp": datetime.now().isoformat(),
            "task": task[:500],
            "failed_approaches_count": len(failed),
            "has_successful_answer": bool(answer),
            "status": "logged",
        }
        self._call_log.append({
            **teaching_request,
            "type": "teaching_request",
            "teaching_triggered": True,
            "cost": 0.0,
        })
        self._save_log()

        logger.info(
            "Teaching request logged: task=%s, %d failed approaches",
            task[:50], len(failed),
        )

        return ToolResult(
            success=True,
            content={
                "status": "logged",
                "message": "Teaching request logged. Actual API call deferred to Phase 2.",
                "failed_approaches_count": len(failed),
            },
            tool_name="apex_teach",
            module=self.name,
        )

    def _apex_log(self, params: dict[str, Any]) -> ToolResult:
        """Log an API usage entry manually.

        Args:
            params: 'entry' dict with usage metadata.
        """
        entry = params.get("entry", {})
        if not entry:
            return ToolResult(
                success=False, content=None, tool_name="apex_log",
                module=self.name, error="Entry dict is required",
            )

        entry["logged_at"] = datetime.now().isoformat()
        cost = entry.get("cost", 0.0)
        self._total_cost += cost
        self._update_daily_cost(cost)
        self._call_log.append(entry)
        self._save_log()

        return ToolResult(
            success=True,
            content={"logged": True, "total_cost": self._total_cost},
            tool_name="apex_log",
            module=self.name,
        )

    def _apex_cost_report(self, params: dict[str, Any]) -> ToolResult:
        """Generate a spending report.

        Args:
            params: No required parameters.
        """
        total_calls = len(self._call_log)
        teaching_calls = sum(
            1 for c in self._call_log if c.get("teaching_triggered", False)
        )

        # Aggregate by API
        api_counts: dict[str, int] = {}
        for call in self._call_log:
            api = call.get("api_selected", call.get("type", "unknown"))
            api_counts[api] = api_counts.get(api, 0) + 1

        report = {
            "total_calls": total_calls,
            "teaching_calls": teaching_calls,
            "total_cost": round(self._total_cost, 4),
            "daily_cost": round(self._daily_cost, 4),
            "daily_cost_date": self._daily_cost_date,
            "api_breakdown": api_counts,
            "apis_available": {
                "claude": bool(self._anthropic_key),
                "openai": bool(self._openai_key),
            },
            "generated_at": datetime.now().isoformat(),
        }

        return ToolResult(
            success=True,
            content=report,
            tool_name="apex_cost_report",
            module=self.name,
        )

    # --- Escalation-learning tools ---

    def _escalation_stats(self, params: dict[str, Any]) -> ToolResult:
        """Get escalation statistics.

        Args:
            params: Optional 'days' (int, default 7).
        """
        if self._escalation_log is None:
            return ToolResult(
                success=False, content=None, tool_name="escalation_stats",
                module=self.name, error="Escalation log not initialized",
            )
        days = params.get("days", 7)
        stats = self._escalation_log.get_escalation_stats(days=days)
        return ToolResult(
            success=True, content=stats,
            tool_name="escalation_stats", module=self.name,
        )

    def _escalation_frequent(self, params: dict[str, Any]) -> ToolResult:
        """Get task types that frequently escalate.

        Args:
            params: No required parameters.
        """
        if self._escalation_log is None:
            return ToolResult(
                success=False, content=None,
                tool_name="escalation_frequent",
                module=self.name, error="Escalation log not initialized",
            )
        frequent = self._escalation_log.get_frequent_escalation_types()
        return ToolResult(
            success=True,
            content={"frequent_types": frequent},
            tool_name="escalation_frequent",
            module=self.name,
        )

    def _teaching_review(self, params: dict[str, Any]) -> ToolResult:
        """Get recent teaching signals for review.

        Args:
            params: Optional 'limit' (int, default 5).
        """
        if self._escalation_log is None:
            return ToolResult(
                success=False, content=None, tool_name="teaching_review",
                module=self.name, error="Escalation log not initialized",
            )
        limit = params.get("limit", 5)
        signals = self._escalation_log.get_recent_teaching_signals(
            limit=limit
        )
        return ToolResult(
            success=True, content={"teaching_signals": signals},
            tool_name="teaching_review", module=self.name,
        )

    # --- Escalation-learning internals ---

    def set_grimoire(self, grimoire: Any) -> None:
        """Inject a Grimoire reference for teaching signal storage.

        Called by the orchestrator after both Apex and Grimoire are
        initialized. If never called, Apex still logs escalations
        but skips Grimoire storage.

        Args:
            grimoire: A Grimoire instance with remember() and recall().
        """
        self._grimoire = grimoire
        logger.info("Grimoire linked to Apex for teaching signal storage.")

    def _record_escalation(
        self,
        task_type: str,
        task_summary: str,
        reason: str,
        api_provider: str,
        api_model: str,
        api_response: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Record an escalation and extract/store teaching signal.

        This is the core of the learning cycle:
        1. Log the escalation in SQLite
        2. Extract a teaching signal
        3. Store the signal in the log
        4. If Grimoire available, store as a searchable memory

        Args:
            task_type: Category of the task.
            task_summary: Brief description of the task.
            reason: Why escalation was needed.
            api_provider: Which API was used.
            api_model: Specific model name.
            api_response: The API's response text.
            input_tokens: Tokens sent.
            output_tokens: Tokens received.
            cost_usd: Cost in USD.
        """
        if self._escalation_log is None:
            return

        try:
            # Step 1: Log the escalation
            log_id = self._escalation_log.log_escalation(
                task_type=task_type,
                task_summary=task_summary,
                reason=reason,
                api_provider=api_provider,
                api_model=api_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
            )

            # Step 2: Extract teaching signal
            if self._teaching_extractor is not None:
                signal = self._teaching_extractor.extract_teaching_signal(
                    task_input=task_summary,
                    api_response=api_response,
                    task_type=task_type,
                )
                signal_json = json.dumps(signal)

                # Step 3: Store signal in escalation log
                grimoire_id = None

                # Step 4: Store in Grimoire if available
                if self._grimoire is not None:
                    try:
                        grimoire_id = self._grimoire.remember(
                            content=(
                                f"Apex teaching signal for {task_type}: "
                                f"{signal['input_summary']}"
                            ),
                            source="system",
                            source_module="apex",
                            category="apex_teaching",
                            trust_level=0.5,
                            confidence=0.5,
                            tags=["apex_teaching", task_type],
                            metadata={"escalation_log_id": log_id},
                            content_blocks=[
                                {
                                    "type": "text",
                                    "content": (
                                        f"Task: {signal['input_summary']}"
                                    ),
                                },
                                {
                                    "type": "text",
                                    "content": (
                                        f"Approach: {signal['approach']}"
                                    ),
                                },
                            ],
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to store teaching signal in Grimoire: %s",
                            e,
                        )

                self._escalation_log.update_teaching_signal(
                    log_id, signal_json, grimoire_id
                )

        except Exception as e:
            logger.error("Failed to record escalation: %s", e)

    def check_grimoire_for_prior_learning(
        self, task_input: str, task_type: str
    ) -> str | None:
        """Search Grimoire for prior teaching signals matching this task.

        Called by the orchestrator BEFORE deciding to escalate. If prior
        learning exists, the local model can try with the teaching signal
        as additional context.

        Args:
            task_input: The task description.
            task_type: Category of the task.

        Returns:
            The stored approach/teaching signal as context, or None if
            no relevant prior learning found.
        """
        if self._grimoire is None:
            return None

        try:
            query = f"{task_type}: {task_input[:200]}"
            results = self._grimoire.recall(
                query=query,
                n_results=3,
                category="apex_teaching",
            )
            if not results:
                return None

            # Return the best match's content
            best = results[0]
            content = best.get("content", "")
            if content:
                return content
        except Exception as e:
            logger.warning(
                "Failed to check Grimoire for prior learning: %s", e
            )

        return None

    # --- Internal helpers ---

    def _select_api(self, preference: str) -> str:
        """Select the best available API.

        Claude is default. OpenAI is fallback. Returns 'none' if no keys.
        """
        if preference == "openai" and self._openai_key:
            return "openai"
        if self._anthropic_key:
            return "claude"
        if self._openai_key:
            return "openai"
        return "none"

    def _update_daily_cost(self, cost: float) -> None:
        """Track daily spending."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._daily_cost_date != today:
            self._daily_cost = 0.0
            self._daily_cost_date = today
        self._daily_cost += cost

    def _load_log(self) -> None:
        """Load call log from disk."""
        if self._log_file.exists():
            try:
                with open(self._log_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._call_log = data.get("calls", [])
                self._total_cost = data.get("total_cost", 0.0)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load apex log: %s", e)
                self._call_log = []
                self._total_cost = 0.0

    def _save_log(self) -> None:
        """Persist call log to disk."""
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "calls": self._call_log[-1000:],  # Keep last 1000 entries
            "total_cost": self._total_cost,
            "saved_at": datetime.now().isoformat(),
        }
        try:
            with open(self._log_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error("Failed to save apex log: %s", e)
