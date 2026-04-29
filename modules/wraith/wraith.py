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

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.wraith")


class TemporalTracker:
    """Tracks temporal events and detects recurring patterns in user behavior.

    Stores events in a SQLite database and analyzes them to find daily and
    weekly patterns. Results are cached with a 6-hour TTL to avoid
    recomputing on every call.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._pattern_cache: list[dict[str, Any]] | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl = timedelta(hours=6)

    def initialize(self) -> None:
        """Open database and create schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS wraith_temporal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                day_of_week INTEGER,
                hour_of_day INTEGER
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_temporal_event_type "
            "ON wraith_temporal_events(event_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_temporal_timestamp "
            "ON wraith_temporal_events(timestamp)"
        )
        self._conn.commit()
        logger.info("TemporalTracker initialized: %s", self._db_path)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def record_event(self, event_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Record a temporal event.

        Args:
            event_type: Category of the event (e.g. 'weather_check', 'email_summary').
            metadata: Optional additional data stored as JSON.

        Returns:
            Dict with recorded event details.
        """
        now = datetime.now()
        meta_json = json.dumps(metadata) if metadata else None

        self._conn.execute(
            "INSERT INTO wraith_temporal_events "
            "(event_type, timestamp, metadata, day_of_week, hour_of_day) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_type, now.isoformat(), meta_json, now.weekday(), now.hour),
        )
        self._conn.commit()

        # Invalidate pattern cache
        self._pattern_cache = None
        self._cache_time = None

        logger.info("Temporal event recorded: %s", event_type)
        return {
            "event_type": event_type,
            "timestamp": now.isoformat(),
            "metadata": metadata,
            "day_of_week": now.weekday(),
            "hour_of_day": now.hour,
        }

    def detect_patterns(
        self, min_occurrences: int = 3, time_window_days: int = 14
    ) -> list[dict[str, Any]]:
        """Analyze events within a time window to find recurring patterns.

        Detects two pattern types:
        - daily_time: same event_type at similar hour on 3+ different days
        - weekly: same event_type on same day of week 3+ times

        Args:
            min_occurrences: Minimum occurrences to qualify as a pattern.
            time_window_days: How far back to look for events.

        Returns:
            List of pattern dicts with event_type, pattern type, confidence, etc.
        """
        cutoff = (datetime.now() - timedelta(days=time_window_days)).isoformat()
        rows = self._conn.execute(
            "SELECT event_type, timestamp, day_of_week, hour_of_day "
            "FROM wraith_temporal_events WHERE timestamp >= ? "
            "ORDER BY event_type, timestamp",
            (cutoff,),
        ).fetchall()

        # Group by event_type
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            et = row["event_type"]
            if et not in groups:
                groups[et] = []
            groups[et].append(dict(row))

        patterns: list[dict[str, Any]] = []

        for event_type, events in groups.items():
            if len(events) < min_occurrences:
                continue

            # Check daily_time patterns: group by hour_of_day
            hour_counts: dict[int, int] = {}
            for e in events:
                h = e["hour_of_day"]
                hour_counts[h] = hour_counts.get(h, 0) + 1

            for hour, count in hour_counts.items():
                if count >= min_occurrences:
                    confidence = min(1.0, count / (min_occurrences * 2))
                    patterns.append({
                        "event_type": event_type,
                        "pattern": "daily_time",
                        "typical_time": f"{hour:02d}:00",
                        "occurrences": count,
                        "confidence": confidence,
                    })

            # Check weekly patterns: group by day_of_week
            dow_counts: dict[int, int] = {}
            for e in events:
                d = e["day_of_week"]
                dow_counts[d] = dow_counts.get(d, 0) + 1

            for dow, count in dow_counts.items():
                if count >= min_occurrences:
                    confidence = min(1.0, count / (min_occurrences * 2))
                    day_names = [
                        "Monday", "Tuesday", "Wednesday", "Thursday",
                        "Friday", "Saturday", "Sunday",
                    ]
                    patterns.append({
                        "event_type": event_type,
                        "pattern": "weekly",
                        "typical_time": day_names[dow],
                        "occurrences": count,
                        "confidence": confidence,
                    })

        return patterns

    def get_patterns(self) -> list[dict[str, Any]]:
        """Return detected patterns, using cache if fresh (< 6 hours old)."""
        now = datetime.now()
        if (
            self._pattern_cache is not None
            and self._cache_time is not None
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._pattern_cache

        self._pattern_cache = self.detect_patterns()
        self._cache_time = now
        return self._pattern_cache


class NeglectDetector:
    """Detects neglected tasks and decision queue items by age.

    Stateless — receives a TaskTracker instance and/or decision queue list
    on each call. Gracefully skips sources that aren't provided.

    Severity levels:
        1 = 24-72 hours (mention in briefing)
        2 = 72 hours to 7 days (dedicated notification)
        3 = 7+ days (elevated severity alert)
    """

    @staticmethod
    def _age_to_severity(age_hours: float) -> int:
        """Map age in hours to severity level."""
        if age_hours >= 168:  # 7 days
            return 3
        if age_hours >= 72:
            return 2
        return 1

    def check_neglected_items(
        self,
        task_tracker: Any = None,
        decision_queue: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Find tasks and decisions that have been sitting too long.

        Args:
            task_tracker: Optional TaskTracker instance. Uses list_tasks(status_filter="queued").
            decision_queue: Optional list of decision queue item dicts from Harbinger.

        Returns:
            List of neglected item dicts sorted by severity descending.
        """
        items: list[dict[str, Any]] = []
        now_epoch = time.time()
        now_dt = datetime.now()

        # Check tasks from TaskTracker
        if task_tracker is not None:
            try:
                queued = task_tracker.list_tasks(status_filter="queued")
                for task in queued:
                    created = task.get("created_at", now_epoch)
                    age_hours = (now_epoch - created) / 3600
                    if age_hours >= 24:
                        items.append({
                            "item_type": "task",
                            "description": task.get("description", "Unknown task"),
                            "age_hours": round(age_hours, 1),
                            "severity": self._age_to_severity(age_hours),
                        })
            except Exception as e:
                logger.warning("NeglectDetector: failed to check tasks: %s", e)

        # Check decision queue items
        if decision_queue is not None:
            for item in decision_queue:
                if item.get("status") != "pending":
                    continue
                try:
                    ts = datetime.fromisoformat(item["timestamp"])
                    age_hours = (now_dt - ts).total_seconds() / 3600
                    if age_hours >= 24:
                        items.append({
                            "item_type": "decision",
                            "description": item.get("description", "Unknown decision"),
                            "age_hours": round(age_hours, 1),
                            "severity": self._age_to_severity(age_hours),
                        })
                except (ValueError, KeyError) as e:
                    logger.warning("NeglectDetector: bad decision item: %s", e)

        # Sort by severity descending (most urgent first)
        items.sort(key=lambda x: x["severity"], reverse=True)
        return items

    def format_neglect_report(self, items: list[dict[str, Any]]) -> str:
        """Format neglected items into a readable report.

        Args:
            items: List from check_neglected_items().

        Returns:
            Human-readable string summary.
        """
        if not items:
            return "No neglected items found."

        severity_labels = {1: "Low", 2: "Medium", 3: "High"}
        lines = [f"Neglected Items Report ({len(items)} items):"]
        lines.append("-" * 40)

        for item in items:
            sev = severity_labels.get(item["severity"], "Unknown")
            age = item["age_hours"]
            if age >= 168:
                age_str = f"{age / 168:.1f} weeks"
            elif age >= 24:
                age_str = f"{age / 24:.1f} days"
            else:
                age_str = f"{age:.0f} hours"
            lines.append(
                f"[{sev}] {item['item_type'].upper()}: "
                f"{item['description']} (age: {age_str})"
            )

        return "\n".join(lines)


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
        self._temporal_tracker = TemporalTracker(
            self._config.get("temporal_db", "data/wraith_temporal.db")
        )
        self._neglect_detector = NeglectDetector()
        # Timezone for user-facing time displays
        tz_name = self._config.get("timezone", "America/Chicago")
        try:
            self._tz = ZoneInfo(tz_name)
        except (KeyError, Exception):
            logger.warning("Invalid timezone '%s', falling back to America/Chicago", tz_name)
            self._tz = ZoneInfo("America/Chicago")

    def _now(self) -> datetime:
        """Return current time in the configured timezone."""
        return datetime.now(tz=self._tz)

    async def initialize(self) -> None:
        """Start Wraith. Load persisted reminders."""
        self.status = ModuleStatus.STARTING
        try:
            self._load_reminders()
            self._temporal_tracker.initialize()
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
            elif tool_name == "temporal_record":
                result = self._temporal_record(params)
            elif tool_name == "temporal_patterns":
                result = self._temporal_patterns(params)
            elif tool_name == "neglect_check":
                result = self._neglect_check(params)
            elif tool_name == "proactive_suggestions":
                result = self._proactive_suggestions(params)
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
        self._temporal_tracker.close()
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
                "description": "Create a timed reminder. Fires when due_time passes.",
                "parameters": {
                    "content": "str — reminder message",
                    "importance": "int (1-5, default 3)",
                    "delay_minutes": "int | float | None — minutes from now until due",
                    "due_time": "str | None — ISO datetime when reminder is due",
                },
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
            {
                "name": "temporal_record",
                "description": "Record an event for temporal pattern tracking",
                "parameters": {
                    "event_type": "str — category of the event",
                    "metadata": "dict | None — optional additional data",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "temporal_patterns",
                "description": "Get detected temporal patterns from event history",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "neglect_check",
                "description": "Check for neglected tasks and decisions",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "proactive_suggestions",
                "description": "Get proactive suggestions based on patterns and neglect detection",
                "parameters": {},
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
            params: Must contain 'content'. Optional 'importance' (1-5, default 3),
                'delay_minutes' (int/float), 'due_time' (ISO datetime string).
                If neither delay_minutes nor due_time is given, reminder is due immediately.
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

        # Determine due_time from delay_minutes or explicit due_time
        now = self._now()
        delay_minutes = params.get("delay_minutes")
        due_time_str = params.get("due_time")

        if delay_minutes is not None:
            try:
                delay = float(delay_minutes)
                if delay < 0:
                    return ToolResult(
                        success=False,
                        content=None,
                        tool_name="reminder_create",
                        module=self.name,
                        error="delay_minutes cannot be negative",
                    )
                due_time = now + timedelta(minutes=delay)
            except (TypeError, ValueError):
                return ToolResult(
                    success=False,
                    content=None,
                    tool_name="reminder_create",
                    module=self.name,
                    error="delay_minutes must be a number",
                )
        elif due_time_str is not None:
            try:
                due_time = datetime.fromisoformat(due_time_str)
            except (TypeError, ValueError):
                return ToolResult(
                    success=False,
                    content=None,
                    tool_name="reminder_create",
                    module=self.name,
                    error="due_time must be a valid ISO datetime string",
                )
        else:
            # No timing specified — due immediately
            due_time = now

        reminder_id = str(self._next_reminder_id)
        self._next_reminder_id += 1

        reminder = {
            "id": reminder_id,
            "content": content,
            "importance": importance,
            "created_at": now.isoformat(),
            "due_time": due_time.isoformat(),
            "status": "pending",
            "dismiss_count": 0,
            "next_surface": now.isoformat(),
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
        next_surface = self._now() + timedelta(days=days)

        reminder["dismiss_count"] = dismiss_count + 1
        reminder["next_surface"] = next_surface.isoformat()
        reminder["status"] = "dismissed"

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
        reminder["status"] = "killed"
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
            suggestion = {"module": "cerberus", "task_type": "analysis", "confidence": 0.7}
        elif any(kw in lower for kw in ["system", "cpu", "memory", "disk", "health", "status"]):
            # System metrics are recorded by the Void daemon; the router
            # has no module target for this, so fall through to direct
            # with a hint for the caller.
            suggestion = {
                "module": "direct",
                "task_type": "system",
                "confidence": 0.6,
                "note": "system metrics are recorded by the Void daemon; "
                        "read data/void_metrics.db or data/void_latest.json",
            }
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
        now = self._now()
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
            "created_at": self._now().isoformat(),
        }

        return ToolResult(
            success=True,
            content=prompt,
            tool_name="ask_user",
            module=self.name,
        )

    # --- Proactive intelligence tools ---

    def _temporal_record(self, params: dict[str, Any]) -> ToolResult:
        """Record an event for temporal pattern tracking.

        Args:
            params: Must contain 'event_type'. Optional 'metadata' (dict).
        """
        event_type = params.get("event_type", "")
        if not event_type:
            return ToolResult(
                success=False,
                content=None,
                tool_name="temporal_record",
                module=self.name,
                error="event_type is required",
            )

        metadata = params.get("metadata")
        event = self._temporal_tracker.record_event(event_type, metadata)

        return ToolResult(
            success=True,
            content=event,
            tool_name="temporal_record",
            module=self.name,
        )

    def _temporal_patterns(self, params: dict[str, Any]) -> ToolResult:
        """Get detected temporal patterns from event history.

        Args:
            params: No required parameters.
        """
        patterns = self._temporal_tracker.get_patterns()

        return ToolResult(
            success=True,
            content={
                "patterns": patterns,
                "count": len(patterns),
                "checked_at": self._now().isoformat(),
            },
            tool_name="temporal_patterns",
            module=self.name,
        )

    def _neglect_check(self, params: dict[str, Any]) -> ToolResult:
        """Check for neglected tasks and decisions.

        Args:
            params: Optional 'task_tracker' and 'decision_queue'.
        """
        task_tracker = params.get("task_tracker")
        decision_queue = params.get("decision_queue")

        items = self._neglect_detector.check_neglected_items(
            task_tracker=task_tracker,
            decision_queue=decision_queue,
        )
        report = self._neglect_detector.format_neglect_report(items)

        return ToolResult(
            success=True,
            content={
                "neglected_items": items,
                "count": len(items),
                "report": report,
                "checked_at": self._now().isoformat(),
            },
            tool_name="neglect_check",
            module=self.name,
        )

    def _proactive_suggestions(self, params: dict[str, Any]) -> ToolResult:
        """Get proactive suggestions based on patterns and neglect detection.

        Combines temporal pattern matches (current time vs detected patterns)
        with neglect detection results. Phase 1: rule-based only, max 3.

        Args:
            params: Optional 'task_tracker' and 'decision_queue'.
        """
        suggestions: list[dict[str, Any]] = []
        now = self._now()

        # Pattern-based suggestions
        patterns = self._temporal_tracker.get_patterns()
        for pattern in patterns:
            if pattern["pattern"] == "daily_time":
                # Check if current hour matches the pattern's typical hour
                try:
                    pattern_hour = int(pattern["typical_time"].split(":")[0])
                except (ValueError, IndexError):
                    continue
                if now.hour == pattern_hour:
                    suggestions.append({
                        "suggestion": (
                            f"You usually trigger '{pattern['event_type']}' "
                            f"around {pattern['typical_time']}. Want me to handle it?"
                        ),
                        "reason": (
                            f"Detected {pattern['occurrences']} occurrences "
                            f"at this time of day"
                        ),
                        "confidence": pattern["confidence"],
                        "source": "pattern",
                    })
            elif pattern["pattern"] == "weekly":
                # Check if current day of week matches
                day_names = [
                    "Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday",
                ]
                current_day = day_names[now.weekday()]
                if pattern["typical_time"] == current_day:
                    suggestions.append({
                        "suggestion": (
                            f"You usually trigger '{pattern['event_type']}' "
                            f"on {current_day}s. Want me to handle it?"
                        ),
                        "reason": (
                            f"Detected {pattern['occurrences']} occurrences "
                            f"on {current_day}s"
                        ),
                        "confidence": pattern["confidence"],
                        "source": "pattern",
                    })

        # Neglect-based suggestions
        task_tracker = params.get("task_tracker")
        decision_queue = params.get("decision_queue")
        neglected = self._neglect_detector.check_neglected_items(
            task_tracker=task_tracker,
            decision_queue=decision_queue,
        )
        for item in neglected:
            age_days = item["age_hours"] / 24
            suggestions.append({
                "suggestion": (
                    f"Neglected {item['item_type']}: '{item['description']}' "
                    f"has been waiting {age_days:.1f} days"
                ),
                "reason": f"Severity {item['severity']} — sitting for {item['age_hours']:.0f}h",
                "confidence": min(1.0, item["severity"] / 3),
                "source": "neglect",
            })

        # Sort by confidence descending, cap at 3
        suggestions.sort(key=lambda s: s["confidence"], reverse=True)
        suggestions = suggestions[:3]

        return ToolResult(
            success=True,
            content={
                "suggestions": suggestions,
                "count": len(suggestions),
                "checked_at": now.isoformat(),
            },
            tool_name="proactive_suggestions",
            module=self.name,
        )

    # --- Public API for orchestrator integration ---

    def check_reminders(self) -> list[dict[str, Any]]:
        """Check for reminders whose due_time has passed and mark them fired.

        Called by the orchestrator on each user input to surface due reminders.

        Returns:
            List of newly fired reminder dicts.
        """
        now = self._now()
        fired: list[dict[str, Any]] = []

        for reminder in self._reminders:
            if reminder.get("killed", False):
                continue
            if reminder.get("status") == "fired":
                continue

            due_time_str = reminder.get("due_time")
            if due_time_str is None:
                continue

            try:
                due_time = datetime.fromisoformat(due_time_str)
            except (TypeError, ValueError):
                continue

            if due_time <= now:
                reminder["status"] = "fired"
                fired.append(reminder)

        if fired:
            self._save_reminders()
            logger.info("check_reminders: %d reminders fired", len(fired))

        return fired

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
            "saved_at": self._now().isoformat(),
        }
        try:
            with open(self._reminder_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error("Failed to save reminders: %s", e)
