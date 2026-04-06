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
import time
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

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

    async def initialize(self) -> None:
        """Start Harbinger. Load persisted decision queue."""
        self.status = ModuleStatus.STARTING
        try:
            self._load_queue()
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
        """Shut down Harbinger. Persist decision queue."""
        self._save_queue()
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
                "description": "Send notification at assigned severity level",
                "parameters": {"message": "str", "severity": "int", "category": "str"},
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
                "shadow_activity", "overnight_plan",
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

        Phase 1: Logs the notification. Telegram dispatch deferred.

        Args:
            params: 'message', 'severity' (1-4), 'category'.
        """
        message = params.get("message", "")
        severity = params.get("severity", 1)
        category = params.get("category", "general")

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
                delivered = False
                logger.info(
                    "Notification held (sleep hours, severity=3): %s", message[:50]
                )
            # Severity 4 always delivered

        notification = {
            "message": message,
            "severity": severity,
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "delivered": delivered,
            "held_for_morning": is_sleep_hours and not delivered,
            "channel": "log",  # Phase 1: log only
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

    # --- Internal helpers ---

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
