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
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.apex")


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
