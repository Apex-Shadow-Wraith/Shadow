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

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from modules.apex.config import ApexSettings
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
        with sqlite3.connect(self._db_path, timeout=5) as conn:
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
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_apex_log_timestamp "
                "ON apex_escalation_log(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_apex_log_task_type "
                "ON apex_escalation_log(task_type)"
            )

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
        with sqlite3.connect(self._db_path, timeout=5) as conn:
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
        with sqlite3.connect(self._db_path, timeout=5) as conn:
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
        with sqlite3.connect(self._db_path, timeout=5) as conn:
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
        with sqlite3.connect(self._db_path, timeout=5) as conn:
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
        with sqlite3.connect(self._db_path, timeout=5) as conn:
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
        with sqlite3.connect(self._db_path, timeout=5) as conn:
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


# TeachingExtractor lives in its own module now (3-tier extraction).
# Re-export here for backward compatibility.
from modules.apex.teaching_extractor import TeachingExtractor  # noqa: E402
from modules.apex.teaching_extractor import THREE_TIER_TEACHING_TEMPLATE  # noqa: E402
from modules.apex.training_data_pipeline import TrainingDataPipeline  # noqa: E402


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

    def __init__(
        self, config: dict[str, Any] | ApexSettings | None = None
    ) -> None:
        """Initialize Apex.

        Args:
            config: Module configuration. Accepts:
                - `ApexSettings` instance (preferred — used by the singleton).
                - Legacy dict (validated into ApexSettings internally).
                - None (falls back to `shadow.config.config.apex`).
        """
        super().__init__(
            name="apex",
            description="API fallback — Claude/GPT with cost tracking and learning",
        )

        if isinstance(config, ApexSettings):
            self._settings = config
        elif config is None:
            from shadow.config import config as _shadow_config
            self._settings = _shadow_config.apex
        else:
            self._settings = ApexSettings.model_validate(config)

        self._config: dict[str, Any] = self._settings.model_dump(mode="python")
        self._anthropic_key: str | None = (
            self._settings.anthropic_api_key.get_secret_value()
            if self._settings.anthropic_api_key
            else None
        )
        self._openai_key: str | None = (
            self._settings.openai_api_key.get_secret_value()
            if self._settings.openai_api_key
            else None
        )
        self._call_log: list[dict[str, Any]] = []
        self._total_cost: float = 0.0
        self._daily_cost: float = 0.0
        self._daily_cost_date: str = ""
        self._log_file = Path(self._settings.log_file)
        self._dry_run: bool = self._settings.dry_run
        self._claude_model: str = self._settings.claude_model
        self._openai_model: str = self._settings.openai_model
        self._max_response_tokens: int = self._settings.max_response_tokens

        # Conversation history for multi-turn API interactions
        self._conversation_history: list[dict[str, str]] = []
        self._max_turns: int = self._settings.max_turns

        # Escalation-learning infrastructure
        self._escalation_log: EscalationLog | None = None
        self._teaching_extractor: TeachingExtractor | None = None
        self._grimoire: Any = None  # Injected via set_grimoire()
        self._training_pipeline: TrainingDataPipeline | None = None

    async def initialize(self) -> None:
        """Start Apex. API keys were loaded by `shadow.config` at import time."""
        self.status = ModuleStatus.STARTING
        try:
            self._load_log()

            # Initialize escalation-learning infrastructure
            escalation_db = Path(self._settings.escalation_db)
            self._escalation_log = EscalationLog(escalation_db)
            self._teaching_extractor = TeachingExtractor()

            # Training data pipeline for LoRA dataset generation
            self._training_pipeline = TrainingDataPipeline(
                self._settings.training_data_dir
            )
            logger.info("Escalation-learning cycle initialized.")

            self.status = ModuleStatus.ONLINE
            api_status = []
            if self._anthropic_key:
                api_status.append("Claude")
            if self._openai_key:
                api_status.append("OpenAI")
            logger.info(
                "Apex online. APIs available: %s. Total cost to date: $%.4f",
                ", ".join(api_status) or "dry-run (no keys)",
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
                "apex_clear_history": self._apex_clear_history,
                "escalation_stats": self._escalation_stats,
                "escalation_frequent": self._escalation_frequent,
                "teaching_review": self._teaching_review,
                "training_stats": self._training_stats,
                "training_export": self._training_export,
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
        """Shut down Apex. Persist call log and clear conversation history."""
        self.clear_history()
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
                "name": "apex_clear_history",
                "description": "Clear conversation history for multi-turn sessions",
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
            {
                "name": "training_stats",
                "description": "Get training data pipeline statistics",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "training_export",
                "description": "Export all training data as merged LoRA-ready JSONL",
                "parameters": {"output_path": "str"},
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _apex_query(self, params: dict[str, Any]) -> ToolResult:
        """Send a task to a frontier API.

        Makes real API calls when keys are present and dry_run is False.
        Falls back to dry-run logging when keys are missing or dry_run is True.

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

        if api == "none":
            logger.warning("Apex in dry-run mode (no API key)")
            entry = {
                "timestamp": datetime.now().isoformat(),
                "task": task[:500],
                "api_selected": "none",
                "model_preference": preference,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost": 0.0,
                "teaching_triggered": False,
                "status": "dry_run",
            }
            self._call_log.append(entry)
            self._save_log()
            logger.warning("Apex API call FAILED: no API keys configured. No frontier model validation occurred.")
            return ToolResult(
                success=False,
                content={"source": "failed", "status": "no_keys"},
                tool_name="apex_query",
                module=self.name,
                error="No API keys available. Configure ANTHROPIC_API_KEY or OPENAI_API_KEY. This response was NOT validated by a frontier model.",
            )

        if self._dry_run:
            logger.warning("Apex in dry-run mode (config): api=%s, task=%s. No API call was made.", api, task[:50])
            entry = {
                "timestamp": datetime.now().isoformat(),
                "task": task[:500],
                "api_selected": api,
                "model_preference": preference,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost": 0.0,
                "teaching_triggered": False,
                "status": "dry_run",
            }
            self._call_log.append(entry)
            self._save_log()
            return ToolResult(
                success=False,
                content={
                    "api": api,
                    "status": "dry_run",
                    "source": "dry_run",
                    "message": "Apex is in dry-run mode. No API call was made. Enable live mode in config.",
                    "task_preview": task[:200],
                },
                tool_name="apex_query",
                module=self.name,
                error="Apex is in dry-run mode. No API call was made. Enable live mode in config.",
            )

        # Live API dispatch — must either succeed or return explicit failure.
        # NEVER generate a local response pretending to be API results.
        # Append the user message to conversation history before calling
        self._conversation_history.append({"role": "user", "content": task})
        try:
            response_text, input_tokens, output_tokens, model_used = self._call_api(api, task)
        except Exception as api_err:
            # Roll back the user message on failure
            self._conversation_history.pop()
            logger.warning(
                "Apex API call FAILED: %s. No frontier model validation occurred.",
                api_err,
            )
            entry = {
                "timestamp": datetime.now().isoformat(),
                "task": task[:500],
                "api_selected": api,
                "model_preference": preference,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost": 0.0,
                "teaching_triggered": False,
                "status": "failed",
            }
            self._call_log.append(entry)
            self._save_log()
            return ToolResult(
                success=False,
                content={"source": "failed", "status": "api_error", "error_detail": str(api_err)},
                tool_name="apex_query",
                module=self.name,
                error=f"Apex API call failed: {api_err}. This response was NOT validated by a frontier model.",
            )

        cost = self._estimate_cost(api, input_tokens, output_tokens)
        self._total_cost += cost
        self._update_daily_cost(cost)

        source_label = "claude_api" if api == "claude" else "openai_api"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "task": task[:500],
            "api_selected": api,
            "model_preference": preference,
            "model_used": model_used,
            "tokens_in": input_tokens,
            "tokens_out": output_tokens,
            "cost": cost,
            "teaching_triggered": False,
            "status": "completed",
        }
        self._call_log.append(entry)
        self._save_log()

        # Append assistant response to conversation history and trim
        self._conversation_history.append({"role": "assistant", "content": response_text})
        self._trim_history()

        logger.info(
            "Apex API call successful: %s, %s, tokens_used=%d",
            api, model_used, input_tokens + output_tokens,
        )

        # Store transaction in Grimoire for audit trail
        self._store_transaction_in_grimoire(
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            task_summary=task[:200],
            response_summary=response_text[:200],
        )

        # Escalation-learning cycle: log, extract, store
        self._record_escalation(
            task_type=params.get("task_type", "general"),
            task_summary=task[:500],
            reason=params.get("reason", "local_model_insufficient"),
            api_provider=api,
            api_model=model_used,
            api_response=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

        return ToolResult(
            success=True,
            content={
                "api": api,
                "model": model_used,
                "source": source_label,
                "status": "completed",
                "response": response_text,
                "tokens_in": input_tokens,
                "tokens_out": output_tokens,
                "cost": cost,
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
            "teaching_template": THREE_TIER_TEACHING_TEMPLATE,
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

    # --- Conversation history management ---

    def clear_history(self) -> None:
        """Clear the conversation history.

        Call on session end or when the user explicitly requests a fresh context.
        """
        cleared = len(self._conversation_history)
        self._conversation_history.clear()
        logger.info("Apex conversation history cleared (%d turns removed).", cleared)

    def _apex_clear_history(self, params: dict[str, Any]) -> ToolResult:
        """Tool handler: clear conversation history.

        Args:
            params: No required parameters.
        """
        turns_before = len(self._conversation_history)
        self.clear_history()
        return ToolResult(
            success=True,
            content={"cleared": True, "turns_removed": turns_before},
            tool_name="apex_clear_history",
            module=self.name,
        )

    def _trim_history(self) -> None:
        """Trim conversation history to max_turns (pairs of user+assistant).

        Each turn is a user message + assistant response (2 entries).
        When we exceed max_turns, drop the oldest turn (2 entries).
        """
        max_messages = self._max_turns * 2
        while len(self._conversation_history) > max_messages:
            # Remove oldest pair
            self._conversation_history.pop(0)
            self._conversation_history.pop(0)

    def _store_transaction_in_grimoire(
        self,
        model_used: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        task_summary: str,
        response_summary: str,
    ) -> None:
        """Store an Apex transaction record in Grimoire for audit trail.

        Args:
            model_used: The model that handled the request.
            input_tokens: Tokens sent to the API.
            output_tokens: Tokens received from the API.
            cost: Cost in USD.
            task_summary: Brief summary of the prompt.
            response_summary: Brief summary of the response.
        """
        if self._grimoire is None:
            return

        try:
            self._grimoire.remember(
                content=(
                    f"Apex transaction: model={model_used}, "
                    f"tokens_in={input_tokens}, tokens_out={output_tokens}, "
                    f"cost=${cost:.6f}. "
                    f"Prompt: {task_summary[:200]}. "
                    f"Response: {response_summary[:200]}"
                ),
                source="apex_transaction",
                source_module="apex",
                category="apex_log",
                trust_level=1.0,
                confidence=1.0,
                tags=["apex_transaction", model_used],
                metadata={
                    "timestamp": datetime.now().isoformat(),
                    "model": model_used,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost,
                },
            )
        except Exception as e:
            logger.warning("Failed to store Apex transaction in Grimoire: %s", e)

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

    # --- Training data tools ---

    def _training_stats(self, params: dict[str, Any]) -> ToolResult:
        """Get training data pipeline statistics.

        Args:
            params: No required parameters.
        """
        if self._training_pipeline is None:
            return ToolResult(
                success=False, content=None, tool_name="training_stats",
                module=self.name, error="Training pipeline not initialized",
            )
        stats = self._training_pipeline.get_stats()
        return ToolResult(
            success=True, content=stats,
            tool_name="training_stats", module=self.name,
        )

    def _training_export(self, params: dict[str, Any]) -> ToolResult:
        """Export all training data as merged LoRA-ready JSONL.

        Args:
            params: Optional 'output_path' (str, default training_data/lora_ready.jsonl).
        """
        if self._training_pipeline is None:
            return ToolResult(
                success=False, content=None, tool_name="training_export",
                module=self.name, error="Training pipeline not initialized",
            )
        output_path = params.get("output_path", "training_data/lora_ready.jsonl")
        count = self._training_pipeline.export_for_lora(output_path)
        return ToolResult(
            success=True,
            content={
                "exported": count,
                "output_path": output_path,
            },
            tool_name="training_export",
            module=self.name,
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

            # Step 5: Capture as LoRA training data
            if self._training_pipeline is not None and api_response:
                try:
                    entry = self._training_pipeline.capture(
                        user_input=task_summary,
                        shadow_failed_response="",
                        apex_response=api_response,
                        module=task_type,
                        category=task_type,
                        metadata={
                            "model_that_answered": api_model,
                            "model_that_failed": "",
                            "api_provider": api_provider,
                        },
                    )
                    self._training_pipeline.save(entry)
                except Exception as te:
                    logger.warning(
                        "Failed to capture training data: %s", te
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

    def _call_api(self, api: str, task: str) -> tuple[str, int, int, str]:
        """Dispatch a task to the selected API provider.

        Sends the full conversation history (including the current user
        message) to enable multi-turn conversations.

        Args:
            api: "claude" or "openai".
            task: The task/prompt to send.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, model_used).

        Raises:
            RuntimeError: If the API call fails.
        """
        if api == "claude":
            return self._call_claude(task)
        elif api == "openai":
            return self._call_openai(task)
        else:
            raise RuntimeError(f"Unknown API provider: {api}")

    def _call_claude(self, task: str) -> tuple[str, int, int, str]:
        """Call the Anthropic Claude API with conversation history.

        Sends the full conversation history to enable multi-turn context.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, model_used).
        """
        import anthropic

        client = anthropic.Anthropic(api_key=self._anthropic_key)
        model = self._claude_model

        response = client.messages.create(
            model=model,
            max_tokens=self._max_response_tokens,
            messages=list(self._conversation_history),
        )

        response_text = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        return response_text, input_tokens, output_tokens, model

    def _call_openai(self, task: str) -> tuple[str, int, int, str]:
        """Call the OpenAI API with conversation history.

        Sends the full conversation history to enable multi-turn context.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, model_used).
        """
        import openai

        client = openai.OpenAI(api_key=self._openai_key)
        model = self._openai_model

        response = client.chat.completions.create(
            model=model,
            max_tokens=self._max_response_tokens,
            messages=list(self._conversation_history),
        )

        choice = response.choices[0] if response.choices else None
        response_text = choice.message.content if choice else ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        return response_text, input_tokens, output_tokens, model

    def _estimate_cost(self, api: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for an API call.

        Args:
            api: "claude" or "openai".
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Estimated cost in USD.
        """
        rates = self.COST_PER_1K.get(api, {"input": 0.0, "output": 0.0})
        cost = (input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"]
        return round(cost, 6)

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
