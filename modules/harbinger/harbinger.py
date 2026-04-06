"""
Harbinger — Shadow's Communications Director
==============================================
Briefings, alerts, reports, and the decision queue.

Design Principle: Harbinger optimizes for density and actionability.
No filler, no pleasantries, just information you can act on. A morning
briefing should be scannable in 3-5 minutes. A notification should be
understood in two lines.

Phase 1: Decision queue, notification severity, briefing structure,
report compilation. Telegram dispatch logged but not sent.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.harbinger.telegram import TelegramDelivery

logger = logging.getLogger("shadow.harbinger")


class Harbinger(BaseModule):
    """Shadow's communications director.

    Manages briefings, notifications, the decision queue, and report
    generation. Everything converges into one coherent communication stream.
    """

    # Notification severity levels
    SEVERITY_SILENT = 1   # Waits for next briefing
    SEVERITY_QUIET = 2    # Notification sent, no sound
    SEVERITY_AUDIBLE = 3  # Notification with sound
    SEVERITY_URGENT = 4   # Repeated alert, wake-up worthy

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Harbinger.

        Args:
            config: Module configuration from shadow_config.yaml.
        """
        super().__init__(
            name="harbinger",
            description="Communications director — briefings, alerts, decision queue",
        )
        self._config = config or {}
        self._queue: list[dict[str, Any]] = []
        self._notification_log: list[dict[str, Any]] = []
        self._queue_file = Path(
            self._config.get("queue_file", "data/harbinger_queue.json")
        )
        self._next_queue_id = 1
        # Sleep window (default 10 PM - 6 AM)
        self._sleep_start = dtime(
            self._config.get("sleep_start_hour", 22), 0
        )
        self._sleep_end = dtime(
            self._config.get("sleep_end_hour", 6), 0
        )

        # Personalization DB
        self._personalization_db_path = Path(
            self._config.get(
                "personalization_db", "data/harbinger_personalization.db"
            )
        )
        self._personalization_conn: sqlite3.Connection | None = None

        # Telegram delivery
        bot_token = self._config.get(
            "telegram_bot_token",
            os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        )
        chat_id = self._config.get(
            "telegram_chat_id",
            os.environ.get("TELEGRAM_CHAT_ID", ""),
        )
        self._telegram = TelegramDelivery(
            bot_token=str(bot_token).strip(),
            chat_id=str(chat_id).strip(),
        )

    async def initialize(self) -> None:
        """Start Harbinger. Load persisted decision queue and personalization DB."""
        self.status = ModuleStatus.STARTING
        try:
            self._load_queue()
            self._init_personalization_db()
            self.status = ModuleStatus.ONLINE
            logger.info(
                "Harbinger online. %d pending decisions in queue.",
                len(self._pending_items),
            )
        except Exception as e:
            self.status = ModuleStatus.ERROR
            logger.error("Harbinger failed to initialize: %s", e)
            raise

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a Harbinger tool.

        Args:
            tool_name: Which tool to invoke.
            params: Tool-specific parameters.

        Returns:
            ToolResult with success/failure and content.
        """
        start = time.time()
        try:
            handlers = {
                "briefing_compile": self._briefing_compile,
                "notification_send": self._notification_send,
                "notification_severity_assign": self._notification_severity_assign,
                "decision_queue_add": self._decision_queue_add,
                "decision_queue_read": self._decision_queue_read,
                "decision_queue_resolve": self._decision_queue_resolve,
                "report_compile": self._report_compile,
                "channel_fallback": self._channel_fallback,
                "preemptive_approval_scan": self._preemptive_approval_scan,
                "briefing_deliver": self._briefing_deliver,
                "personalization_update": self._personalization_update,
                "personalization_weights": self._personalization_weights,
            }

            handler = handlers.get(tool_name)
            if handler is None:
                result = ToolResult(
                    success=False,
                    content=None,
                    tool_name=tool_name,
                    module=self.name,
                    error=f"Unknown tool: {tool_name}",
                )
            else:
                result = handler(params)

            result.execution_time_ms = (time.time() - start) * 1000
            self._record_call(result.success)
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._record_call(False)
            logger.error("Harbinger tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False,
                content=None,
                tool_name=tool_name,
                module=self.name,
                error=str(e),
                execution_time_ms=elapsed,
            )

    async def shutdown(self) -> None:
        """Shut down Harbinger. Persist decision queue and close personalization DB."""
        self._save_queue()
        if self._personalization_conn is not None:
            try:
                self._personalization_conn.close()
            except Exception:
                pass
            self._personalization_conn = None
        self.status = ModuleStatus.OFFLINE
        logger.info("Harbinger offline. Decision queue saved.")

    def get_tools(self) -> list[dict[str, Any]]:
        """Return Harbinger's tool definitions."""
        return [
            {
                "name": "briefing_compile",
                "description": "Compile morning/evening briefing from module data",
                "parameters": {"briefing_type": "str", "sections": "list"},
                "permission_level": "autonomous",
            },
            {
                "name": "notification_send",
                "description": "Send notification at assigned severity level via Telegram (or log fallback)",
                "parameters": {"message": "str", "severity": "int", "category": "str", "importance": "int"},
                "permission_level": "autonomous",
            },
            {
                "name": "notification_severity_assign",
                "description": "Determine severity level (1-4) for an event",
                "parameters": {"event": "str", "category": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "decision_queue_add",
                "description": "Add a deferred decision to the queue",
                "parameters": {
                    "description": "str",
                    "context": "str",
                    "recommendation": "str",
                    "importance": "int",
                    "source_module": "str",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "decision_queue_read",
                "description": "Get pending decisions for user review",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "decision_queue_resolve",
                "description": "Mark a decision as resolved after user input",
                "parameters": {"decision_id": "str", "resolution": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "report_compile",
                "description": "Structure data into report format with sections",
                "parameters": {"title": "str", "sections": "list"},
                "permission_level": "autonomous",
            },
            {
                "name": "channel_fallback",
                "description": "Switch to next delivery channel if primary fails",
                "parameters": {"failed_channel": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "preemptive_approval_scan",
                "description": "Scan upcoming tasks for actions needing user approval",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "briefing_deliver",
                "description": "Deliver a compiled briefing through the active channel",
                "parameters": {"briefing": "dict", "channel": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "personalization_update",
                "description": "Record user interaction with a briefing section",
                "parameters": {"section_name": "str", "action": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "personalization_weights",
                "description": "Get current section engagement weights",
                "parameters": {},
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _briefing_compile(self, params: dict[str, Any]) -> ToolResult:
        """Compile a morning or evening briefing.

        Architecture: 'Wraith compiles raw data at 5:30 AM. Harbinger
        formats it into a structured, scannable report.'

        Args:
            params: 'briefing_type' (morning/evening), 'sections' (list of dicts).
        """
        briefing_type = params.get("briefing_type", "morning")
        sections = params.get("sections", [])

        if briefing_type not in ("morning", "evening"):
            return ToolResult(
                success=False,
                content=None,
                tool_name="briefing_compile",
                module=self.name,
                error="briefing_type must be 'morning' or 'evening'",
            )

        # Build structured briefing
        now = datetime.now()
        briefing = {
            "type": briefing_type,
            "compiled_at": now.isoformat(),
            "date": now.strftime("%A, %B %d, %Y"),
            "sections": [],
        }

        # If modules are provided for evening, use assemble_evening_summary
        modules = params.get("modules")
        if briefing_type == "evening" and modules is not None:
            summary = self.assemble_evening_summary(modules)
            # Convert assembled sections into briefing_compile format
            for section in summary["sections"]:
                briefing["sections"].append({
                    "name": section["title"].lower().replace(" ", "_"),
                    "title": section["title"],
                    "content": section["content"],
                    "source": section.get("source", "harbinger"),
                })
            return ToolResult(
                success=True,
                content=briefing,
                tool_name="briefing_compile",
                module=self.name,
            )

        if briefing_type == "morning":
            # Morning briefing has 10 sections per architecture
            section_order = [
                "critical_alerts", "decision_queue", "schedule",
                "weather", "email_summary", "business_snapshot",
                "research_intel", "morpheus_report", "shadow_growth",
                "pending_reminders",
            ]
        else:
            section_order = [
                "completed_today", "pending_items", "tomorrow_preview",
                "shadow_activity", "learning_report", "overnight_plan",
            ]

        # Merge provided sections into the template
        section_map = {s.get("name", ""): s for s in sections if isinstance(s, dict)}
        for section_name in section_order:
            section_data = section_map.get(section_name, {})
            briefing["sections"].append({
                "name": section_name,
                "title": section_name.replace("_", " ").title(),
                "content": section_data.get("content", "No data available."),
                "source": section_data.get("source", "pending"),
            })

        # Include pending decision queue items in morning briefing
        if briefing_type == "morning":
            pending = self._pending_items
            if pending:
                for section in briefing["sections"]:
                    if section["name"] == "decision_queue":
                        section["content"] = {
                            "count": len(pending),
                            "items": pending,
                        }
                        break

        return ToolResult(
            success=True,
            content=briefing,
            tool_name="briefing_compile",
            module=self.name,
        )

    def _notification_send(self, params: dict[str, Any]) -> ToolResult:
        """Send a notification at the assigned severity level.

        Delivers via Telegram when configured and severity/nighttime rules allow.
        Falls back to log-only when Telegram is not configured.

        Args:
            params: 'message', 'severity' (1-4), 'category',
                    'importance' (1-5, optional, used for nighttime severity-3 gating).
        """
        message = params.get("message", "")
        severity = params.get("severity", 1)
        category = params.get("category", "general")
        importance = params.get("importance", 3)

        if not message:
            return ToolResult(
                success=False,
                content=None,
                tool_name="notification_send",
                module=self.name,
                error="Message is required",
            )

        if not isinstance(severity, int) or severity < 1 or severity > 4:
            return ToolResult(
                success=False,
                content=None,
                tool_name="notification_send",
                module=self.name,
                error="Severity must be 1 (Silent), 2 (Quiet), 3 (Audible), or 4 (Urgent)",
            )

        if not isinstance(importance, int):
            importance = 3
        importance = max(1, min(5, importance))

        # Nighttime rules
        now = datetime.now().time()
        is_sleep_hours = self._is_sleep_time(now)
        delivered = True

        if is_sleep_hours:
            if severity <= 2:
                delivered = False
                logger.info(
                    "Notification held (sleep hours, severity=%d): %s",
                    severity, message[:50],
                )
            elif severity == 3:
                if importance < 5:
                    delivered = False
                    logger.info(
                        "Notification held (sleep hours, severity=3, importance=%d): %s",
                        importance, message[:50],
                    )
                else:
                    logger.info(
                        "Severity-3 delivered during sleep (importance=%d): %s",
                        importance, message[:50],
                    )
            # Severity 4 always delivered

        # Determine delivery channel
        telegram_sent = False
        channel = "log"

        if delivered and self._telegram and self._telegram.is_configured():
            if severity >= 2:
                telegram_sent = self._telegram.send_alert(
                    message, severity, category,
                )
                if telegram_sent:
                    channel = "telegram"
                    logger.info("Notification delivered via Telegram.")
                else:
                    channel = "log"
                    logger.warning(
                        "Telegram delivery failed — queuing fallback."
                    )
                    self._decision_queue_add({
                        "description": f"Notification delivery failed: {message[:80]}",
                        "context": f"Telegram send failed for severity-{severity} {category} notification.",
                        "recommendation": "Check Telegram bot token and chat ID. Retry or use alternate channel.",
                        "importance": min(severity, 4),
                        "source_module": "harbinger",
                    })
        elif delivered and (not self._telegram or not self._telegram.is_configured()):
            logger.info("Telegram not configured — notification logged only.")

        notification = {
            "message": message,
            "severity": severity,
            "category": category,
            "importance": importance,
            "timestamp": datetime.now().isoformat(),
            "delivered": delivered,
            "held_for_morning": is_sleep_hours and not delivered,
            "channel": channel,
            "telegram_sent": telegram_sent,
        }
        self._notification_log.append(notification)

        severity_names = {1: "Silent", 2: "Quiet", 3: "Audible", 4: "Urgent"}
        logger.info(
            "[%s] %s: %s",
            severity_names.get(severity, "Unknown"),
            category,
            message[:100],
        )

        return ToolResult(
            success=True,
            content=notification,
            tool_name="notification_send",
            module=self.name,
        )

    def _notification_severity_assign(self, params: dict[str, Any]) -> ToolResult:
        """Determine the severity level for an event.

        Rule-based assignment in Phase 1.

        Args:
            params: 'event' description, 'category'.
        """
        event = params.get("event", "")
        category = params.get("category", "general")

        if not event:
            return ToolResult(
                success=False,
                content=None,
                tool_name="notification_severity_assign",
                module=self.name,
                error="Event description is required",
            )

        lower = event.lower()

        # Rule-based severity assignment
        if any(kw in lower for kw in ["breach", "attack", "critical", "emergency", "down"]):
            severity = self.SEVERITY_URGENT
        elif any(kw in lower for kw in ["warning", "failed", "error", "deadline", "overdue"]):
            severity = self.SEVERITY_AUDIBLE
        elif any(kw in lower for kw in ["update", "reminder", "approval", "pending"]):
            severity = self.SEVERITY_QUIET
        else:
            severity = self.SEVERITY_SILENT

        severity_names = {1: "Silent", 2: "Quiet", 3: "Audible", 4: "Urgent"}

        return ToolResult(
            success=True,
            content={
                "event": event,
                "category": category,
                "severity": severity,
                "severity_name": severity_names[severity],
            },
            tool_name="notification_severity_assign",
            module=self.name,
        )

    def _decision_queue_add(self, params: dict[str, Any]) -> ToolResult:
        """Add a deferred decision to the queue.

        Architecture: 'The decision queue is the pipeline of items waiting
        for user input. It bridges Shadow's autonomous operation and the
        user's authority.'

        Args:
            params: 'description', 'context', 'recommendation', 'importance', 'source_module'.
        """
        description = params.get("description", "")
        if not description:
            return ToolResult(
                success=False,
                content=None,
                tool_name="decision_queue_add",
                module=self.name,
                error="Decision description is required",
            )

        importance = params.get("importance", 3)
        if not isinstance(importance, int) or importance < 1 or importance > 5:
            return ToolResult(
                success=False,
                content=None,
                tool_name="decision_queue_add",
                module=self.name,
                error="Importance must be between 1 and 5",
            )

        decision_id = str(self._next_queue_id)
        self._next_queue_id += 1

        item = {
            "id": decision_id,
            "description": description,
            "context": params.get("context", ""),
            "recommendation": params.get("recommendation", ""),
            "importance": importance,
            "timestamp": datetime.now().isoformat(),
            "source_module": params.get("source_module", "unknown"),
            "status": "pending",
            "resolution": None,
            "resolved_at": None,
        }
        self._queue.append(item)
        self._save_queue()

        logger.info("Decision queued: id=%s, importance=%d", decision_id, importance)

        return ToolResult(
            success=True,
            content=item,
            tool_name="decision_queue_add",
            module=self.name,
        )

    def _decision_queue_read(self, params: dict[str, Any]) -> ToolResult:
        """Read pending decisions from the queue.

        Args:
            params: Optional 'include_resolved' (bool).
        """
        include_resolved = params.get("include_resolved", False)

        if include_resolved:
            items = sorted(self._queue, key=lambda x: x["importance"], reverse=True)
        else:
            items = sorted(self._pending_items, key=lambda x: x["importance"], reverse=True)

        return ToolResult(
            success=True,
            content={
                "items": items,
                "pending_count": len(self._pending_items),
                "total_count": len(self._queue),
            },
            tool_name="decision_queue_read",
            module=self.name,
        )

    def _decision_queue_resolve(self, params: dict[str, Any]) -> ToolResult:
        """Mark a decision as resolved.

        Args:
            params: 'decision_id', 'resolution' (what was decided).
        """
        decision_id = str(params.get("decision_id", ""))
        resolution = params.get("resolution", "")

        if not decision_id:
            return ToolResult(
                success=False,
                content=None,
                tool_name="decision_queue_resolve",
                module=self.name,
                error="decision_id is required",
            )

        if not resolution:
            return ToolResult(
                success=False,
                content=None,
                tool_name="decision_queue_resolve",
                module=self.name,
                error="resolution is required",
            )

        item = self._find_queue_item(decision_id)
        if item is None:
            return ToolResult(
                success=False,
                content=None,
                tool_name="decision_queue_resolve",
                module=self.name,
                error=f"Decision {decision_id} not found",
            )

        item["status"] = "resolved"
        item["resolution"] = resolution
        item["resolved_at"] = datetime.now().isoformat()
        self._save_queue()

        logger.info("Decision %s resolved: %s", decision_id, resolution[:50])

        return ToolResult(
            success=True,
            content=item,
            tool_name="decision_queue_resolve",
            module=self.name,
        )

    def _report_compile(self, params: dict[str, Any]) -> ToolResult:
        """Compile structured data into a report.

        Args:
            params: 'title', 'sections' (list of dicts with 'heading' and 'content').
        """
        title = params.get("title", "Report")
        sections = params.get("sections", [])

        report = {
            "title": title,
            "compiled_at": datetime.now().isoformat(),
            "sections": [],
        }

        for section in sections:
            if isinstance(section, dict):
                report["sections"].append({
                    "heading": section.get("heading", "Untitled"),
                    "content": section.get("content", ""),
                })

        return ToolResult(
            success=True,
            content=report,
            tool_name="report_compile",
            module=self.name,
        )

    def _channel_fallback(self, params: dict[str, Any]) -> ToolResult:
        """Switch to next delivery channel when primary fails.

        Architecture fallback chain: Telegram → Signal → Email → Decision Queue.

        Args:
            params: 'failed_channel' — which channel failed.
        """
        failed = params.get("failed_channel", "")
        fallback_chain = ["telegram", "signal", "email", "decision_queue"]

        if failed not in fallback_chain:
            next_channel = fallback_chain[0]
        else:
            idx = fallback_chain.index(failed)
            if idx + 1 < len(fallback_chain):
                next_channel = fallback_chain[idx + 1]
            else:
                next_channel = "decision_queue"  # Last resort: nothing is ever lost

        logger.info("Channel fallback: %s → %s", failed, next_channel)

        return ToolResult(
            success=True,
            content={
                "failed_channel": failed,
                "next_channel": next_channel,
                "fallback_chain": fallback_chain,
            },
            tool_name="channel_fallback",
            module=self.name,
        )

    def _preemptive_approval_scan(self, params: dict[str, Any]) -> ToolResult:
        """Scan upcoming tasks and scheduled items for actions needing user approval.

        Presents them in a batch so the user can pre-authorize over dinner
        instead of getting interrupted throughout the next day.

        Args:
            params: Optional 'modules' dict of available module instances.
        """
        approval_items: list[dict[str, Any]] = []

        # 1. Check decision queue for pending items
        for item in self._pending_items:
            importance = item.get("importance", 3)
            if importance >= 4:
                risk = "high"
            elif importance >= 2:
                risk = "medium"
            else:
                risk = "low"
            approval_items.append({
                "item_id": item["id"],
                "description": item.get("description", ""),
                "source": f"decision_queue ({item.get('source_module', 'unknown')})",
                "action_needed": item.get("recommendation", "Review and decide"),
                "risk_level": risk,
            })

        # 2. Check task tracker if available
        modules = params.get("modules") or {}
        task_tracker = modules.get("task_tracker")
        if task_tracker is not None:
            try:
                queued = task_tracker.list_tasks(status_filter="queued")
                for task in queued:
                    perm = task.get("permission_level", "autonomous")
                    if perm != "autonomous":
                        priority = task.get("priority", 5)
                        if priority <= 2:
                            risk = "high"
                        elif priority <= 4:
                            risk = "medium"
                        else:
                            risk = "low"
                        approval_items.append({
                            "item_id": task.get("id", "unknown"),
                            "description": task.get("description", ""),
                            "source": "task_tracker",
                            "action_needed": f"Approve task: {task.get('description', '')[:60]}",
                            "risk_level": risk,
                        })
            except Exception as e:
                logger.warning("Failed to scan task tracker: %s", e)

        # Sort by risk_level: high > medium > low
        risk_order = {"high": 0, "medium": 1, "low": 2}
        approval_items.sort(key=lambda x: risk_order.get(x["risk_level"], 3))

        if not approval_items:
            return ToolResult(
                success=True,
                content={
                    "items": [],
                    "message": "No upcoming actions require approval",
                },
                tool_name="preemptive_approval_scan",
                module=self.name,
            )

        return ToolResult(
            success=True,
            content={
                "items": approval_items,
                "count": len(approval_items),
            },
            tool_name="preemptive_approval_scan",
            module=self.name,
        )

    def _briefing_deliver(self, params: dict[str, Any]) -> ToolResult:
        """Deliver a compiled briefing through the active channel.

        Falls through channels on failure: telegram -> console -> log.

        Args:
            params: 'briefing' (dict), 'channel' (str, default 'telegram').
        """
        briefing = params.get("briefing")
        if not briefing or not isinstance(briefing, dict):
            return ToolResult(
                success=False,
                content=None,
                tool_name="briefing_deliver",
                module=self.name,
                error="briefing (dict) is required",
            )

        channel = params.get("channel", "telegram")
        fallback_used = False

        # Format the briefing text
        briefing_type = briefing.get("type", "")
        if "evening" in briefing_type:
            text = self.format_evening_summary(briefing)
        else:
            text = self.format_briefing_text(briefing)

        # Attempt delivery through channel cascade
        if channel == "telegram":
            delivered = False
            try:
                if self._telegram and self._telegram.is_configured():
                    delivered = self._telegram.send_message(text)
            except Exception as e:
                logger.warning("Telegram delivery failed: %s", e)

            if delivered:
                return ToolResult(
                    success=True,
                    content={
                        "delivered": True,
                        "channel_used": "telegram",
                        "fallback_used": False,
                    },
                    tool_name="briefing_deliver",
                    module=self.name,
                )
            # Fall through to console
            channel = "console"
            fallback_used = True

        if channel == "console":
            try:
                print(text)
                return ToolResult(
                    success=True,
                    content={
                        "delivered": True,
                        "channel_used": "console",
                        "fallback_used": fallback_used,
                    },
                    tool_name="briefing_deliver",
                    module=self.name,
                )
            except Exception as e:
                logger.warning("Console delivery failed: %s", e)
                channel = "log"
                fallback_used = True

        # Log channel — always available
        logger.info("Briefing delivered via log:\n%s", text)
        return ToolResult(
            success=True,
            content={
                "delivered": True,
                "channel_used": "log",
                "fallback_used": fallback_used,
            },
            tool_name="briefing_deliver",
            module=self.name,
        )

    def _personalization_update(self, params: dict[str, Any]) -> ToolResult:
        """Record user interaction with a briefing section.

        Args:
            params: 'section_name' (str), 'action' (str: engaged|skipped|expanded|dismissed).
        """
        section_name = params.get("section_name", "")
        action = params.get("action", "")

        if not section_name:
            return ToolResult(
                success=False,
                content=None,
                tool_name="personalization_update",
                module=self.name,
                error="section_name is required",
            )

        valid_actions = ("engaged", "skipped", "expanded", "dismissed")
        if action not in valid_actions:
            return ToolResult(
                success=False,
                content=None,
                tool_name="personalization_update",
                module=self.name,
                error=f"action must be one of: {', '.join(valid_actions)}",
            )

        try:
            self._ensure_personalization_db()
            now = datetime.now().isoformat()
            self._personalization_conn.execute(
                "INSERT INTO harbinger_personalization (timestamp, section_name, action) "
                "VALUES (?, ?, ?)",
                (now, section_name, action),
            )
            self._personalization_conn.commit()

            return ToolResult(
                success=True,
                content={
                    "section_name": section_name,
                    "action": action,
                    "recorded_at": now,
                },
                tool_name="personalization_update",
                module=self.name,
            )
        except Exception as e:
            logger.error("Failed to record personalization: %s", e)
            return ToolResult(
                success=False,
                content=None,
                tool_name="personalization_update",
                module=self.name,
                error=str(e),
            )

    def _personalization_weights(self, params: dict[str, Any]) -> ToolResult:
        """Get current section engagement weights.

        Args:
            params: Unused.
        """
        try:
            weights = self.get_personalization_weights()
            return ToolResult(
                success=True,
                content=weights,
                tool_name="personalization_weights",
                module=self.name,
            )
        except Exception as e:
            logger.error("Failed to get personalization weights: %s", e)
            return ToolResult(
                success=False,
                content=None,
                tool_name="personalization_weights",
                module=self.name,
                error=str(e),
            )

    def get_personalization_weights(self) -> dict[str, Any]:
        """Compute engagement scores per section from the last 30 days.

        Returns:
            Dict of section_name -> {score, total_interactions, trend}.
            Sections with < 20% engagement flagged for demotion.
            Sections with > 80% engagement flagged for promotion.
        """
        self._ensure_personalization_db()
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()

        rows = self._personalization_conn.execute(
            "SELECT section_name, action, COUNT(*) as cnt "
            "FROM harbinger_personalization "
            "WHERE timestamp >= ? "
            "GROUP BY section_name, action",
            (cutoff,),
        ).fetchall()

        if not rows:
            return {}

        # Aggregate by section
        sections: dict[str, dict[str, int]] = {}
        for section_name, action, cnt in rows:
            if section_name not in sections:
                sections[section_name] = {}
            sections[section_name][action] = cnt

        weights: dict[str, Any] = {}
        for section_name, actions in sections.items():
            engaged = actions.get("engaged", 0) + actions.get("expanded", 0)
            total = sum(actions.values())
            score = engaged / total if total > 0 else 0.0

            if score >= 0.8:
                trend = "promote"
            elif score <= 0.2:
                trend = "demote"
            else:
                trend = "stable"

            weights[section_name] = {
                "score": round(score, 3),
                "total_interactions": total,
                "trend": trend,
            }

        return weights

    # --- Internal helpers ---

    def _init_personalization_db(self) -> None:
        """Initialize the personalization SQLite database."""
        self._personalization_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._personalization_conn = sqlite3.connect(
            str(self._personalization_db_path)
        )
        self._personalization_conn.execute(
            "CREATE TABLE IF NOT EXISTS harbinger_personalization ("
            "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "    timestamp TEXT NOT NULL,"
            "    section_name TEXT NOT NULL,"
            "    action TEXT NOT NULL,"
            "    metadata TEXT"
            ")"
        )
        self._personalization_conn.commit()

    def _ensure_personalization_db(self) -> None:
        """Ensure the personalization DB connection is open."""
        if self._personalization_conn is None:
            self._init_personalization_db()

    @property
    def _pending_items(self) -> list[dict[str, Any]]:
        """Return only pending (unresolved) queue items."""
        return [q for q in self._queue if q.get("status") == "pending"]

    def _find_queue_item(self, decision_id: str) -> dict[str, Any] | None:
        """Find a queue item by ID."""
        for item in self._queue:
            if item["id"] == str(decision_id):
                return item
        return None

    def _is_sleep_time(self, current_time: dtime) -> bool:
        """Check if the current time is within the sleep window.

        Handles windows that cross midnight (e.g., 22:00 - 06:00).
        """
        if self._sleep_start > self._sleep_end:
            # Crosses midnight: 22:00 to 06:00
            return current_time >= self._sleep_start or current_time < self._sleep_end
        else:
            return self._sleep_start <= current_time < self._sleep_end

    def _load_queue(self) -> None:
        """Load decision queue from disk."""
        if self._queue_file.exists():
            try:
                with open(self._queue_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._queue = data.get("queue", [])
                self._next_queue_id = data.get("next_id", 1)
                logger.info("Loaded %d queue items from disk.", len(self._queue))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load queue: %s. Starting fresh.", e)
                self._queue = []
                self._next_queue_id = 1
        else:
            self._queue = []
            self._next_queue_id = 1

    def _save_queue(self) -> None:
        """Persist decision queue to disk."""
        self._queue_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "queue": self._queue,
            "next_id": self._next_queue_id,
            "saved_at": datetime.now().isoformat(),
        }
        try:
            with open(self._queue_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error("Failed to save queue: %s", e)

    # --- Morning briefing assembly ---

    def assemble_morning_briefing(self, modules: dict[str, Any]) -> dict[str, Any]:
        """Pull data from all available modules and assemble a structured morning briefing.

        Each module is queried gracefully — if a module is missing or its call
        fails, that section is marked as unavailable rather than crashing.

        Args:
            modules: Dict of module_name -> module_instance.

        Returns:
            Structured dict with sorted sections, each containing title,
            content, and priority.
        """
        now = datetime.now()
        sections: list[dict[str, Any]] = []

        # 1. Grimoire — memory stats
        sections.append(self._pull_grimoire(modules.get("grimoire")))

        # 2. Cerberus — safety stats
        sections.append(self._pull_cerberus(modules.get("cerberus")))

        # 3. Wraith — due reminders
        sections.append(self._pull_wraith(modules.get("wraith")))

        # 4. Void — system health
        sections.append(self._pull_void(modules.get("void")))

        # 5. Reaper — standing research
        sections.append(self._pull_reaper(modules.get("reaper")))

        # 6. Harbinger — pending decision queue
        sections.append(self._pull_decision_queue())

        # 7. Task Tracker — active/recent tasks
        sections.append(self._pull_task_tracker(modules.get("task_tracker")))

        # 8. Daily Safety Report — Cerberus audit summary
        sections.append(self._pull_safety_report())

        # 9. Wraith — neglected items report
        sections.append(self._pull_neglect_report(modules.get("wraith")))

        # 10. Apex — escalation stats
        sections.append(self._pull_apex_stats(modules.get("apex")))

        # 11. Shadow Growth — learning goals and metrics
        sections.append(self._pull_growth_summary(modules.get("growth_engine")))

        # Sort by priority (1 = highest)
        sections.sort(key=lambda s: s["priority"])

        return {
            "type": "morning_briefing",
            "compiled_at": now.isoformat(),
            "date": now.strftime("%A, %B %d, %Y"),
            "section_count": len(sections),
            "sections": sections,
        }

    def format_briefing_text(self, briefing: dict[str, Any]) -> str:
        """Render a structured briefing into readable, scannable text.

        Args:
            briefing: Output from assemble_morning_briefing().

        Returns:
            Formatted string scannable in 3-5 minutes.
        """
        lines: list[str] = []
        lines.append(f"=== SHADOW MORNING BRIEFING ===")
        lines.append(f"Date: {briefing.get('date', 'Unknown')}")
        lines.append(f"Compiled: {briefing.get('compiled_at', 'Unknown')}")
        lines.append("")

        for i, section in enumerate(briefing.get("sections", []), 1):
            priority_label = {1: "HIGH", 2: "MEDIUM", 3: "LOW"}.get(
                section["priority"], "INFO"
            )
            lines.append(f"--- {i}. {section['title']} [{priority_label}] ---")

            content = section.get("content")
            if content is None or content == "Module not available":
                lines.append("  [Not available]")
            elif isinstance(content, dict):
                for key, value in content.items():
                    if isinstance(value, list):
                        lines.append(f"  {key}: {len(value)} item(s)")
                        for item in value[:5]:
                            if isinstance(item, dict):
                                summary = item.get("description", item.get("content", str(item)))
                                lines.append(f"    - {str(summary)[:80]}")
                            else:
                                lines.append(f"    - {str(item)[:80]}")
                    else:
                        lines.append(f"  {key}: {value}")
            elif isinstance(content, str):
                lines.append(f"  {content}")
            else:
                lines.append(f"  {content}")

            lines.append("")

        lines.append(f"=== END BRIEFING ({briefing.get('section_count', 0)} sections) ===")
        return "\n".join(lines)

    # --- Evening summary assembly ---

    def assemble_evening_summary(self, modules: dict[str, Any]) -> dict[str, Any]:
        """Pull data from available modules and assemble a structured evening summary.

        Mirrors assemble_morning_briefing() but focuses on what happened today,
        what's still pending, and what's coming tomorrow.

        Args:
            modules: Dict of module_name -> module_instance.

        Returns:
            Structured dict with 5 sections: completed_today, pending_items,
            tomorrow_preview, shadow_activity, overnight_plan.
        """
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        sections: list[dict[str, Any]] = []

        # 1. Completed Today
        sections.append(self._pull_completed_today(modules.get("task_tracker"), today_str))

        # 2. Pending Items
        sections.append(self._pull_pending_items(modules.get("task_tracker")))

        # 3. Tomorrow Preview
        sections.append(self._pull_tomorrow_preview(modules.get("task_tracker")))

        # 4. Shadow Activity
        sections.append(self._pull_shadow_activity(
            modules.get("void"), modules.get("reaper"),
            apex=modules.get("apex"), wraith=modules.get("wraith"),
        ))

        # 5. Learning Report — growth engine evening summary
        sections.append(self._pull_growth_evening(modules.get("growth_engine")))

        # 6. Overnight Plan
        sections.append(self._pull_overnight_plan())

        # Sort by priority (1 = highest)
        sections.sort(key=lambda s: s["priority"])

        return {
            "type": "evening_summary",
            "compiled_at": now.isoformat(),
            "date": now.strftime("%A, %B %d, %Y"),
            "section_count": len(sections),
            "sections": sections,
        }

    def format_evening_summary(self, summary: dict[str, Any]) -> str:
        """Render a structured evening summary into readable, scannable text.

        Args:
            summary: Output from assemble_evening_summary().

        Returns:
            Formatted string for end-of-day review.
        """
        lines: list[str] = []
        lines.append("=== SHADOW EVENING SUMMARY ===")
        lines.append(f"Date: {summary.get('date', 'Unknown')}")
        lines.append(f"Compiled: {summary.get('compiled_at', 'Unknown')}")
        lines.append("")

        for i, section in enumerate(summary.get("sections", []), 1):
            priority_label = {1: "HIGH", 2: "MEDIUM", 3: "LOW"}.get(
                section["priority"], "INFO"
            )
            lines.append(f"--- {i}. {section['title']} [{priority_label}] ---")

            content = section.get("content")
            if content is None or content == "Module not available":
                lines.append("  [Not available]")
            elif isinstance(content, dict):
                for key, value in content.items():
                    if isinstance(value, list):
                        lines.append(f"  {key}: {len(value)} item(s)")
                        for item in value[:5]:
                            if isinstance(item, dict):
                                desc = item.get("description", item.get("content", str(item)))
                                lines.append(f"    - {str(desc)[:80]}")
                            else:
                                lines.append(f"    - {str(item)[:80]}")
                    else:
                        lines.append(f"  {key}: {value}")
            elif isinstance(content, str):
                lines.append(f"  {content}")
            else:
                lines.append(f"  {content}")

            lines.append("")

        lines.append(f"=== END SUMMARY ({summary.get('section_count', 0)} sections) ===")
        return "\n".join(lines)

    # --- Evening summary data pullers (private) ---

    def _pull_completed_today(self, task_tracker: Any, today_str: str) -> dict[str, Any]:
        """Pull tasks completed today from TaskTracker."""
        if task_tracker is None:
            return self._empty_section("Completed Today", 2)
        try:
            completed = task_tracker.list_tasks(status_filter="completed")
            today_completed = [
                t for t in completed
                if t.get("completed_at", "")[:10] == today_str
            ]
            return {
                "title": "Completed Today",
                "priority": 2,
                "source": "task_tracker",
                "content": {
                    "count": len(today_completed),
                    "tasks": today_completed,
                },
            }
        except Exception as e:
            logger.warning("Failed to pull completed tasks: %s", e)
            return self._error_section("Completed Today", 2, str(e))

    def _pull_pending_items(self, task_tracker: Any) -> dict[str, Any]:
        """Pull pending tasks and decision queue items."""
        pending_tasks: list[dict[str, Any]] = []
        task_error = None

        if task_tracker is not None:
            try:
                for status in ("queued", "running"):
                    pending_tasks.extend(task_tracker.list_tasks(status_filter=status))
            except Exception as e:
                task_error = str(e)
                logger.warning("Failed to pull pending tasks: %s", e)

        decision_count = len(self._pending_items)

        if task_tracker is None and decision_count == 0:
            return self._empty_section("Pending Items", 2)

        priority = 1 if pending_tasks or decision_count > 0 else 2

        content: dict[str, Any] = {
            "task_count": len(pending_tasks),
            "tasks": pending_tasks,
            "decision_queue_count": decision_count,
        }
        if task_error:
            content["task_error"] = task_error

        return {
            "title": "Pending Items",
            "priority": priority,
            "source": "task_tracker",
            "content": content,
        }

    def _pull_tomorrow_preview(self, task_tracker: Any) -> dict[str, Any]:
        """Preview tomorrow's workload. Phase 1: show queued task count and high-priority items."""
        if task_tracker is None:
            return self._empty_section("Tomorrow Preview", 3)
        try:
            queued = task_tracker.list_tasks(status_filter="queued")
            high_priority = [t for t in queued if t.get("priority", 5) <= 3]
            return {
                "title": "Tomorrow Preview",
                "priority": 3,
                "source": "task_tracker",
                "content": {
                    "queued_count": len(queued),
                    "high_priority_count": len(high_priority),
                    "high_priority_tasks": high_priority,
                },
            }
        except Exception as e:
            logger.warning("Failed to pull tomorrow preview: %s", e)
            return self._error_section("Tomorrow Preview", 3, str(e))

    def _pull_shadow_activity(
        self, void: Any, reaper: Any,
        apex: Any = None, wraith: Any = None,
    ) -> dict[str, Any]:
        """Pull background activity summary from Void, Reaper, Apex, and Wraith."""
        activity: dict[str, Any] = {}

        if void is not None:
            try:
                result = void._system_health({})
                content = result.content if hasattr(result, "content") else result
                if isinstance(content, dict):
                    activity["system_health"] = {
                        "cpu_percent": content.get("cpu_percent"),
                        "ram_percent": content.get("ram_percent"),
                        "disk_percent": content.get("disk_percent"),
                    }
            except Exception as e:
                activity["system_health_error"] = str(e)
                logger.warning("Failed to pull Void data for evening summary: %s", e)

        if reaper is not None:
            try:
                data = reaper.get_briefing_data()
                if isinstance(data, dict):
                    research = data.get("research", [])
                    activity["research_completed"] = len(research)
                    activity["research_items"] = research[:5]
            except Exception as e:
                activity["research_error"] = str(e)
                logger.warning("Failed to pull Reaper data for evening summary: %s", e)

        if apex is not None:
            try:
                result = apex._escalation_stats({"days": 1})
                content = result.content if hasattr(result, "content") else result
                if isinstance(content, dict):
                    activity["escalation_stats"] = {
                        "total_escalations": content.get("total_escalations", 0),
                        "total_cost": content.get("total_cost_usd", 0.0),
                        "top_types": content.get("by_type", {}),
                    }
            except Exception as e:
                activity["escalation_error"] = str(e)
                logger.warning("Failed to pull Apex data for evening summary: %s", e)

        if wraith is not None:
            try:
                result = wraith._proactive_suggestions({})
                content = result.content if hasattr(result, "content") else result
                if isinstance(content, dict) and content.get("suggestions"):
                    activity["proactive_suggestions"] = content["suggestions"]
            except Exception as e:
                activity["proactive_error"] = str(e)
                logger.warning("Failed to pull Wraith suggestions for evening summary: %s", e)

        if not activity:
            return self._empty_section("Shadow Activity", 3)

        return {
            "title": "Shadow Activity",
            "priority": 3,
            "source": "void/reaper",
            "content": activity,
        }

    def _pull_overnight_plan(self) -> dict[str, Any]:
        """Return overnight plan. Phase 1: static message."""
        return {
            "title": "Overnight Plan",
            "priority": 3,
            "source": "harbinger",
            "content": "No overnight autonomy in Phase 1. Background monitoring only.",
        }

    # --- Module data pullers (private) ---

    def _pull_grimoire(self, grimoire: Any) -> dict[str, Any]:
        """Pull memory stats from Grimoire."""
        if grimoire is None:
            return self._empty_section("Memory Status", 2)
        try:
            stats = grimoire.stats()
            return {
                "title": "Memory Status",
                "priority": 2,
                "source": "grimoire",
                "content": {
                    "active_memories": stats.get("active_memories", 0),
                    "total_stored": stats.get("total_stored", 0),
                    "vector_count": stats.get("vector_count", 0),
                    "by_category": stats.get("by_category", {}),
                },
            }
        except Exception as e:
            logger.warning("Failed to pull Grimoire data: %s", e)
            return self._error_section("Memory Status", 2, str(e))

    def _pull_cerberus(self, cerberus: Any) -> dict[str, Any]:
        """Pull safety stats from Cerberus."""
        if cerberus is None:
            return self._empty_section("Safety Status", 1)
        try:
            stats = cerberus.stats
            return {
                "title": "Safety Status",
                "priority": 1,
                "source": "cerberus",
                "content": {
                    "checks": stats.get("checks", 0),
                    "denials": stats.get("denials", 0),
                    "false_positives": stats.get("false_positives", 0),
                    "denial_rate": stats.get("denial_rate", 0.0),
                    "config_integrity": "verified" if not stats.get("tampered", False) else "TAMPERED",
                },
            }
        except Exception as e:
            logger.warning("Failed to pull Cerberus data: %s", e)
            return self._error_section("Safety Status", 1, str(e))

    def _pull_wraith(self, wraith: Any) -> dict[str, Any]:
        """Pull due reminders from Wraith."""
        if wraith is None:
            return self._empty_section("Reminders & Tasks", 1)
        try:
            result = wraith._proactive_check({})
            content = result.content if hasattr(result, "content") else result
            suggestions = []
            if isinstance(content, dict):
                suggestions = content.get("suggestions", [])
            return {
                "title": "Reminders & Tasks",
                "priority": 1,
                "source": "wraith",
                "content": {
                    "due_items": suggestions,
                    "count": len(suggestions),
                },
            }
        except Exception as e:
            logger.warning("Failed to pull Wraith data: %s", e)
            return self._error_section("Reminders & Tasks", 1, str(e))

    def _pull_void(self, void: Any) -> dict[str, Any]:
        """Pull system health snapshot from Void."""
        if void is None:
            return self._empty_section("System Health", 3)
        try:
            result = void._system_health({})
            content = result.content if hasattr(result, "content") else result
            if isinstance(content, dict):
                return {
                    "title": "System Health",
                    "priority": 3,
                    "source": "void",
                    "content": {
                        "cpu_percent": content.get("cpu_percent"),
                        "ram_percent": content.get("ram_percent"),
                        "disk_percent": content.get("disk_percent"),
                        "alerts": content.get("alerts", []),
                    },
                }
            return {
                "title": "System Health",
                "priority": 3,
                "source": "void",
                "content": content,
            }
        except Exception as e:
            logger.warning("Failed to pull Void data: %s", e)
            return self._error_section("System Health", 3, str(e))

    def _pull_reaper(self, reaper: Any) -> dict[str, Any]:
        """Pull recent research results from Reaper."""
        if reaper is None:
            return self._empty_section("Research Intel", 2)
        try:
            data = reaper.get_briefing_data()
            if isinstance(data, dict):
                return {
                    "title": "Research Intel",
                    "priority": 2,
                    "source": "reaper",
                    "content": {
                        "research": data.get("research", []),
                        "reddit": data.get("reddit", []),
                        "generated_at": data.get("generated_at"),
                    },
                }
            return {
                "title": "Research Intel",
                "priority": 2,
                "source": "reaper",
                "content": data,
            }
        except Exception as e:
            logger.warning("Failed to pull Reaper data: %s", e)
            return self._error_section("Research Intel", 2, str(e))

    def _pull_decision_queue(self) -> dict[str, Any]:
        """Pull pending decision queue items from Harbinger itself."""
        pending = self._pending_items
        if not pending:
            return {
                "title": "Decision Queue",
                "priority": 2,
                "source": "harbinger",
                "content": {
                    "pending_count": 0,
                    "items": [],
                },
            }
        return {
            "title": "Decision Queue",
            "priority": 1,
            "source": "harbinger",
            "content": {
                "pending_count": len(pending),
                "items": sorted(pending, key=lambda x: x.get("importance", 0), reverse=True),
            },
        }

    def _pull_task_tracker(self, task_tracker: Any) -> dict[str, Any]:
        """Pull active and recent task data from the TaskTracker."""
        if task_tracker is None:
            return self._empty_section("Tasks & Queue", 2)
        try:
            active = []
            for status in ("queued", "running"):
                active.extend(task_tracker.list_tasks(status_filter=status))

            # Recently completed/failed (last 24h)
            cutoff = time.time() - 86400
            recent = []
            for status in ("completed", "failed"):
                for t in task_tracker.list_tasks(status_filter=status):
                    if t.get("updated_at", 0) >= cutoff:
                        recent.append(t)

            failed = [t for t in recent if t.get("status") == "failed"]
            overdue = [
                t for t in active
                if t.get("status") == "running"
                and t.get("created_at", time.time()) < cutoff
            ]

            return {
                "title": "Tasks & Queue",
                "priority": 2 if not failed and not overdue else 1,
                "source": "task_tracker",
                "content": {
                    "active_count": len(active),
                    "active_tasks": active,
                    "recent_completed": [t for t in recent if t.get("status") == "completed"],
                    "failed_tasks": failed,
                    "overdue_tasks": overdue,
                },
            }
        except Exception as e:
            logger.warning("Failed to pull TaskTracker data: %s", e)
            return self._error_section("Tasks & Queue", 2, str(e))

    def _pull_safety_report(self) -> dict[str, Any]:
        """Pull daily safety report from Cerberus audit logs."""
        try:
            from modules.harbinger.safety_report import DailySafetyReport

            db_path = Path(
                self._config.get("cerberus_audit_db", "data/cerberus_audit.db")
            )
            if not db_path.exists():
                return self._empty_section("Safety Report", 2)

            report = DailySafetyReport().generate(
                date=datetime.now().date(), db_path=db_path
            )
            formatted = DailySafetyReport.format_for_harbinger(report)

            summary = report.get("summary", {})
            return {
                "title": "Safety Report",
                "priority": 1 if report.get("anomalies") else 2,
                "source": "safety_report",
                "content": {
                    "summary": summary,
                    "anomaly_count": len(report.get("anomalies", [])),
                    "anomalies": report.get("anomalies", []),
                    "calibration_alerts": report.get("calibration_alerts", []),
                    "formatted_text": formatted,
                },
            }
        except Exception as e:
            logger.warning("Failed to pull safety report: %s", e)
            return self._error_section("Safety Report", 2, str(e))

    def _pull_neglect_report(self, wraith: Any) -> dict[str, Any]:
        """Pull neglected items report from Wraith's NeglectDetector."""
        if wraith is None:
            return self._empty_section("Neglected Items", 4)
        try:
            result = wraith._neglect_check({})
            content = result.content if hasattr(result, "content") else result
            if not isinstance(content, dict) or not content.get("neglected_items"):
                return self._empty_section("Neglected Items", 4)

            items = content["neglected_items"]
            max_severity = max((i.get("severity", 1) for i in items), default=1)
            if max_severity >= 3:
                priority = 2
            elif max_severity >= 2:
                priority = 3
            else:
                priority = 4

            return {
                "title": "Neglected Items",
                "priority": priority,
                "source": "wraith",
                "content": content,
            }
        except Exception as e:
            logger.warning("Failed to pull neglect report: %s", e)
            return self._error_section("Neglected Items", 4, str(e))

    def _pull_apex_stats(self, apex: Any) -> dict[str, Any]:
        """Pull escalation statistics from Apex for the last day."""
        if apex is None:
            return self._empty_section("API Escalation Summary", 4)
        try:
            result = apex._escalation_stats({"days": 1})
            content = result.content if hasattr(result, "content") else result
            if not isinstance(content, dict):
                return self._empty_section("API Escalation Summary", 4)

            return {
                "title": "API Escalation Summary",
                "priority": 4,
                "source": "apex",
                "content": {
                    "total_escalations": content.get("total_escalations", 0),
                    "total_cost": content.get("total_cost_usd", 0.0),
                    "top_types": content.get("by_type", {}),
                },
            }
        except Exception as e:
            logger.warning("Failed to pull Apex stats: %s", e)
            return self._error_section("API Escalation Summary", 4, str(e))

    def _pull_growth_summary(self, growth_engine: Any) -> dict[str, Any]:
        """Pull growth goals and metric trends for the morning briefing."""
        if growth_engine is None:
            return self._empty_section("Shadow Growth", 2)
        try:
            summary = growth_engine.get_growth_summary()
            # Ensure today's goals exist — generate if needed
            if not summary.get("today_goals"):
                try:
                    growth_engine.generate_daily_goals()
                    summary = growth_engine.get_growth_summary()
                except Exception as e:
                    logger.warning("Failed to generate daily goals: %s", e)
            content: dict[str, Any] = {}
            yc = summary.get("yesterday_completion", {})
            content["yesterday_completion_rate"] = f"{yc.get('rate', 0) * 100:.0f}%"
            content["yesterday_completed"] = f"{yc.get('completed', 0)}/{yc.get('total', 0)}"
            goals = summary.get("today_goals", [])
            content["today_goals"] = [
                {"description": g.get("goal", ""), "category": g.get("category", "")}
                for g in goals
            ]
            flags = summary.get("flags", [])
            if flags:
                content["metric_alerts"] = flags
            # Check for declining trends
            trends = summary.get("metric_trends", {})
            declining = [
                name for name, data in trends.items()
                if isinstance(data, dict) and data.get("trend") == "declining"
            ]
            if declining:
                content["declining_metrics"] = declining
            return {
                "title": "Shadow Growth",
                "priority": 2,
                "source": "growth_engine",
                "content": content,
            }
        except Exception as e:
            logger.warning("Failed to pull growth summary: %s", e)
            return self._error_section("Shadow Growth", 2, str(e))

    def _pull_growth_evening(self, growth_engine: Any) -> dict[str, Any]:
        """Pull learning report for the evening summary."""
        if growth_engine is None:
            return self._empty_section("Learning Report", 2)
        try:
            report = growth_engine.compile_evening_learning_report()
            content: dict[str, Any] = {}
            content["hit_rate"] = f"{report.get('hit_rate', 0) * 100:.0f}%"
            goals_hit = report.get("goals_hit", [])
            goals_missed = report.get("goals_missed", [])
            content["goals_completed"] = [
                {"description": g.get("goal", ""), "category": g.get("category", "")}
                for g in goals_hit
            ]
            content["goals_missed"] = [
                {"description": g.get("goal", ""), "category": g.get("category", "")}
                for g in goals_missed
            ]
            content["date"] = report.get("date", "")
            return {
                "title": "Learning Report",
                "priority": 2,
                "source": "growth_engine",
                "content": content,
            }
        except Exception as e:
            logger.warning("Failed to pull growth evening report: %s", e)
            return self._error_section("Learning Report", 2, str(e))

    def _empty_section(self, title: str, priority: int) -> dict[str, Any]:
        """Return a section placeholder when a module is not available."""
        return {
            "title": title,
            "priority": priority,
            "source": None,
            "content": "Module not available",
        }

    def _error_section(self, title: str, priority: int, error: str) -> dict[str, Any]:
        """Return a section placeholder when a module call fails."""
        return {
            "title": title,
            "priority": priority,
            "source": "error",
            "content": f"Error: {error}",
        }
