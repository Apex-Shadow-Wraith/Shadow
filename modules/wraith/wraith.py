"""
Wraith — Shadow's Fast Brain & Daily Workhorse
================================================
Handles 80% of daily tasks: Q&A routing, reminders, file management
routing, email triage routing, proactive intelligence stubs.

Design Principle: Wraith is not a basic assistant. He is a senior
employee who handles everything that doesn't need the CEO's attention.
Smart enough for 80% of tasks. Fast enough to respond in 2-5 seconds.
Honest enough to hand off what he can't handle.

Phase 1: Rule-based routing, reminder system with persistence,
proactive intelligence stubs. No LLM calls — pure logic.
"""

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.wraith")


class Wraith(BaseModule):
    """Shadow's fast brain. Handles routine tasks, reminders, and routing.

    Wraith doesn't generate text via LLM in Phase 1. He manages reminders,
    classifies tasks for routing, and runs proactive checks. The orchestrator
    handles LLM-based response generation.
    """

    # Dismiss escalation schedule: dismiss_count → days until re-surface
    DISMISS_SCHEDULE = {
        0: 1,    # 1st dismiss → next day
        1: 3,    # 2nd dismiss → 3 days
        2: 7,    # 3rd dismiss → 1 week
    }
    DEFAULT_RESURFACE_DAYS = 7  # 4th+ dismiss → weekly

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Wraith.

        Args:
            config: Module configuration from shadow_config.yaml.
        """
        super().__init__(
            name="wraith",
            description="Fast brain — handles 80% of daily tasks, reminders, routing",
        )
        self._config = config or {}
        self._reminders: list[dict[str, Any]] = []
        self._reminder_file = Path(
            self._config.get("reminder_file", "data/wraith_reminders.json")
        )
        self._next_reminder_id = 1

    async def initialize(self) -> None:
        """Start Wraith. Load persisted reminders."""
        self.status = ModuleStatus.STARTING
        try:
            self._load_reminders()
            self.status = ModuleStatus.ONLINE
            logger.info(
                "Wraith online. %d active reminders loaded.", len(self._active_reminders)
            )
        except Exception as e:
            self.status = ModuleStatus.ERROR
            logger.error("Wraith failed to initialize: %s", e)
            raise

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a Wraith tool.

        Args:
            tool_name: Which tool to invoke.
            params: Tool-specific parameters.

        Returns:
            ToolResult with success/failure and content.
        """
        start = time.time()
        try:
            if tool_name == "quick_answer":
                result = self._quick_answer(params)
            elif tool_name == "reminder_create":
                result = self._reminder_create(params)
            elif tool_name == "reminder_list":
                result = self._reminder_list(params)
            elif tool_name == "reminder_dismiss":
                result = self._reminder_dismiss(params)
            elif tool_name == "reminder_kill":
                result = self._reminder_kill(params)
            elif tool_name == "classify_task":
                result = self._classify_task(params)
            elif tool_name == "proactive_check":
                result = self._proactive_check(params)
            elif tool_name == "ask_user":
                result = self._ask_user(params)
            else:
                result = ToolResult(
                    success=False,
                    content=None,
                    tool_name=tool_name,
                    module=self.name,
                    error=f"Unknown tool: {tool_name}",
                )

            result.execution_time_ms = (time.time() - start) * 1000
            self._record_call(result.success)
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._record_call(False)
            logger.error("Wraith tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False,
                content=None,
                tool_name=tool_name,
                module=self.name,
                error=str(e),
                execution_time_ms=elapsed,
            )

    async def shutdown(self) -> None:
        """Shut down Wraith. Persist reminders."""
        self._save_reminders()
        self.status = ModuleStatus.OFFLINE
        logger.info("Wraith offline. Reminders saved.")

    def get_tools(self) -> list[dict[str, Any]]:
        """Return Wraith's tool definitions."""
        return [
            {
                "name": "quick_answer",
                "description": "Answer a question using loaded context and memory",
                "parameters": {"query": "str", "context": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "reminder_create",
                "description": "Create a reminder with importance level (1-5)",
                "parameters": {"content": "str", "importance": "int"},
                "permission_level": "autonomous",
            },
            {
                "name": "reminder_list",
                "description": "List all active reminders sorted by importance",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "reminder_dismiss",
                "description": "Dismiss a reminder (re-surfaces on escalating schedule)",
                "parameters": {"reminder_id": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "reminder_kill",
                "description": "Permanently remove a reminder",
                "parameters": {"reminder_id": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "classify_task",
                "description": "Classify and suggest routing for a user task",
                "parameters": {"input_text": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "proactive_check",
                "description": "Check for proactive suggestions based on patterns",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "ask_user",
                "description": "Prompt user for clarification with optional choices",
                "parameters": {
                    "question": "str — the question to ask the user",
                    "options": "list[str] | None — optional multiple-choice options",
                },
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _quick_answer(self, params: dict[str, Any]) -> ToolResult:
        """Provide a quick answer from context.

        In Phase 1, this returns the context as-is. In later phases,
        Wraith's LLM brain will synthesize an answer.

        Args:
            params: Must contain 'query'. Optional 'context'.
        """
        query = params.get("query", "")
        context = params.get("context", "")

        if not query:
            return ToolResult(
                success=False,
                content=None,
                tool_name="quick_answer",
                module=self.name,
                error="No query provided",
            )

        return ToolResult(
            success=True,
            content={
                "query": query,
                "context_provided": bool(context),
                "answer": context if context else "No context available for this query.",
                "source": "wraith_quick_answer",
            },
            tool_name="quick_answer",
            module=self.name,
        )

    def _reminder_create(self, params: dict[str, Any]) -> ToolResult:
        """Create a new reminder.

        Args:
            params: Must contain 'content'. Optional 'importance' (1-5, default 3).
        """
        content = params.get("content", "")
        if not content:
            return ToolResult(
                success=False,
                content=None,
                tool_name="reminder_create",
                module=self.name,
                error="Reminder content is required",
            )

        importance = params.get("importance", 3)
        if not isinstance(importance, int) or importance < 1 or importance > 5:
            return ToolResult(
                success=False,
                content=None,
                tool_name="reminder_create",
                module=self.name,
                error="Importance must be an integer between 1 and 5",
            )

        reminder_id = str(self._next_reminder_id)
        self._next_reminder_id += 1

        reminder = {
            "id": reminder_id,
            "content": content,
            "importance": importance,
            "created_at": datetime.now().isoformat(),
            "dismiss_count": 0,
            "next_surface": datetime.now().isoformat(),
            "killed": False,
        }
        self._reminders.append(reminder)
        self._save_reminders()

        logger.info("Reminder created: id=%s, importance=%d", reminder_id, importance)

        return ToolResult(
            success=True,
            content=reminder,
            tool_name="reminder_create",
            module=self.name,
        )

    def _reminder_list(self, params: dict[str, Any]) -> ToolResult:
        """List all active reminders sorted by importance (highest first).

        Args:
            params: Optional 'include_killed' (bool) to include killed reminders.
        """
        include_killed = params.get("include_killed", False)

        if include_killed:
            reminders = sorted(self._reminders, key=lambda r: r["importance"], reverse=True)
        else:
            reminders = sorted(
                self._active_reminders, key=lambda r: r["importance"], reverse=True
            )

        return ToolResult(
            success=True,
            content={
                "reminders": reminders,
                "total": len(reminders),
                "active": len(self._active_reminders),
                "killed": len(self._reminders) - len(self._active_reminders),
            },
            tool_name="reminder_list",
            module=self.name,
        )

    def _reminder_dismiss(self, params: dict[str, Any]) -> ToolResult:
        """Dismiss a reminder. It will re-surface on an escalating schedule.

        Architecture: 'Dismissed means not now, not never. Wraith keeps
        reminding until the user acts or explicitly tells him to stop.'

        Args:
            params: Must contain 'reminder_id'.
        """
        reminder_id = str(params.get("reminder_id", ""))
        if not reminder_id:
            return ToolResult(
                success=False,
                content=None,
                tool_name="reminder_dismiss",
                module=self.name,
                error="reminder_id is required",
            )

        reminder = self._find_reminder(reminder_id)
        if reminder is None:
            return ToolResult(
                success=False,
                content=None,
                tool_name="reminder_dismiss",
                module=self.name,
                error=f"Reminder {reminder_id} not found",
            )

        if reminder["killed"]:
            return ToolResult(
                success=False,
                content=None,
                tool_name="reminder_dismiss",
                module=self.name,
                error=f"Reminder {reminder_id} is already killed",
            )

        # Escalating re-surface schedule
        dismiss_count = reminder["dismiss_count"]
        days = self.DISMISS_SCHEDULE.get(dismiss_count, self.DEFAULT_RESURFACE_DAYS)
        next_surface = datetime.now() + timedelta(days=days)

        reminder["dismiss_count"] = dismiss_count + 1
        reminder["next_surface"] = next_surface.isoformat()

        self._save_reminders()
        logger.info(
            "Reminder %s dismissed (count=%d). Re-surfaces in %d days.",
            reminder_id,
            reminder["dismiss_count"],
            days,
        )

        return ToolResult(
            success=True,
            content={
                "reminder_id": reminder_id,
                "dismiss_count": reminder["dismiss_count"],
                "next_surface": reminder["next_surface"],
                "resurface_days": days,
            },
            tool_name="reminder_dismiss",
            module=self.name,
        )

    def _reminder_kill(self, params: dict[str, Any]) -> ToolResult:
        """Permanently kill a reminder. It will never re-surface.

        Args:
            params: Must contain 'reminder_id'.
        """
        reminder_id = str(params.get("reminder_id", ""))
        if not reminder_id:
            return ToolResult(
                success=False,
                content=None,
                tool_name="reminder_kill",
                module=self.name,
                error="reminder_id is required",
            )

        reminder = self._find_reminder(reminder_id)
        if reminder is None:
            return ToolResult(
                success=False,
                content=None,
                tool_name="reminder_kill",
                module=self.name,
                error=f"Reminder {reminder_id} not found",
            )

        reminder["killed"] = True
        self._save_reminders()
        logger.info("Reminder %s killed.", reminder_id)

        return ToolResult(
            success=True,
            content={"reminder_id": reminder_id, "status": "killed"},
            tool_name="reminder_kill",
            module=self.name,
        )

    def _classify_task(self, params: dict[str, Any]) -> ToolResult:
        """Classify a task and suggest which module should handle it.

        Phase 1: keyword-based classification. Phase 2+: LLM routing.

        Args:
            params: Must contain 'input_text'.
        """
        input_text = params.get("input_text", "")
        if not input_text:
            return ToolResult(
                success=False,
                content=None,
                tool_name="classify_task",
                module=self.name,
                error="input_text is required",
            )

        lower = input_text.lower()

        # Keyword-based classification
        if any(kw in lower for kw in ["remember", "forget", "recall", "what do you know"]):
            suggestion = {"module": "grimoire", "task_type": "memory", "confidence": 0.9}
        elif any(kw in lower for kw in ["search", "look up", "find", "research", "what is"]):
            suggestion = {"module": "reaper", "task_type": "research", "confidence": 0.8}
        elif any(kw in lower for kw in ["calculate", "math", "compute", "how much", "percent"]):
            suggestion = {"module": "cipher", "task_type": "analysis", "confidence": 0.8}
        elif any(kw in lower for kw in ["write code", "debug", "script", "program", "function"]):
            suggestion = {"module": "omen", "task_type": "creation", "confidence": 0.8}
        elif any(kw in lower for kw in ["security", "threat", "breach", "hack", "protect"]):
            suggestion = {"module": "sentinel", "task_type": "analysis", "confidence": 0.7}
        elif any(kw in lower for kw in ["system", "cpu", "memory", "disk", "health", "status"]):
            suggestion = {"module": "void", "task_type": "system", "confidence": 0.7}
        elif any(kw in lower for kw in ["write", "document", "report", "format", "template"]):
            suggestion = {"module": "nova", "task_type": "creation", "confidence": 0.7}
        elif any(kw in lower for kw in ["email", "calendar", "schedule", "remind"]):
            suggestion = {"module": "wraith", "task_type": "action", "confidence": 0.8}
        else:
            suggestion = {"module": "wraith", "task_type": "conversation", "confidence": 0.5}

        return ToolResult(
            success=True,
            content=suggestion,
            tool_name="classify_task",
            module=self.name,
        )

    def _proactive_check(self, params: dict[str, Any]) -> ToolResult:
        """Check for proactive suggestions.

        Phase 1: Returns due reminders only. Phase 2+: temporal patterns,
        behavioral patterns, neglect detection, calendar awareness.

        Args:
            params: No required parameters.
        """
        now = datetime.now()
        due_reminders = []

        for reminder in self._active_reminders:
            try:
                next_surface = datetime.fromisoformat(reminder["next_surface"])
                if next_surface <= now:
                    due_reminders.append(reminder)
            except (ValueError, KeyError):
                continue

        # Sort by importance (highest first)
        due_reminders.sort(key=lambda r: r["importance"], reverse=True)

        suggestions: list[dict[str, Any]] = []
        for reminder in due_reminders:
            suggestions.append({
                "type": "due_reminder",
                "content": reminder["content"],
                "importance": reminder["importance"],
                "reminder_id": reminder["id"],
                "dismiss_count": reminder["dismiss_count"],
            })

        return ToolResult(
            success=True,
            content={
                "suggestions": suggestions,
                "count": len(suggestions),
                "checked_at": now.isoformat(),
            },
            tool_name="proactive_check",
            module=self.name,
        )

    def _ask_user(self, params: dict[str, Any]) -> ToolResult:
        """Format a structured question for the user.

        Phase 1: Returns a prompt dict for the orchestrator to display.
        This is NOT a blocking interactive call — it formats the question
        and the orchestrator handles delivery.

        Args:
            params: Must contain 'question'. Optional 'options' (list of strings).
        """
        question = params.get("question", "")
        if not question:
            return ToolResult(
                success=False,
                content=None,
                tool_name="ask_user",
                module=self.name,
                error="question is required",
            )

        options = params.get("options")

        prompt = {
            "type": "user_question",
            "question": question,
            "options": options,
            "created_at": datetime.now().isoformat(),
        }

        return ToolResult(
            success=True,
            content=prompt,
            tool_name="ask_user",
            module=self.name,
        )

    # --- Internal helpers ---

    @property
    def _active_reminders(self) -> list[dict[str, Any]]:
        """Return only non-killed reminders."""
        return [r for r in self._reminders if not r.get("killed", False)]

    def _find_reminder(self, reminder_id: str) -> dict[str, Any] | None:
        """Find a reminder by ID."""
        for r in self._reminders:
            if r["id"] == str(reminder_id):
                return r
        return None

    def _load_reminders(self) -> None:
        """Load reminders from disk."""
        if self._reminder_file.exists():
            try:
                with open(self._reminder_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._reminders = data.get("reminders", [])
                self._next_reminder_id = data.get("next_id", 1)
                logger.info("Loaded %d reminders from disk.", len(self._reminders))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load reminders: %s. Starting fresh.", e)
                self._reminders = []
                self._next_reminder_id = 1
        else:
            self._reminders = []
            self._next_reminder_id = 1

    def _save_reminders(self) -> None:
        """Persist reminders to disk."""
        self._reminder_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "reminders": self._reminders,
            "next_id": self._next_reminder_id,
            "saved_at": datetime.now().isoformat(),
        }
        try:
            with open(self._reminder_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error("Failed to save reminders: %s", e)
