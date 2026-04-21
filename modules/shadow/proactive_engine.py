"""
Proactive Initiative System — Shadow's Autonomous Work Engine
================================================================
Enables modules to self-start work without user prompts based on
events, schedules, conditions, and discovered opportunities.

Components:
- ProactiveTrigger: dataclass defining when and how a module acts
- ProactiveEngine: manages triggers, rate limits, idle work cycles,
  and persistence

Uses the existing EventSystem (modules/shadow/events.py) when available.
Falls back to a lightweight built-in event bus otherwise.

Safety: every proactive task goes through the same Cerberus pipeline
as user requests. The engine never directly executes module actions —
it only produces task descriptors for the orchestrator to process.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("shadow.proactive_engine")


# ---------------------------------------------------------------------------
# Lightweight event bus — fallback when the full EventSystem is unavailable
# ---------------------------------------------------------------------------

class _LightEventBus:
    """Minimal pub/sub used when ``modules.shadow.events.EventSystem`` is
    not wired in yet (e.g. during early startup or in tests).

    Each callback receives ``(event_name: str, payload: dict)``.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[tuple[str, Callable]]] = {}

    def subscribe(
        self,
        module_name: str,
        event_name: str,
        callback: Callable | None = None,
    ) -> None:
        """Match the real EventSystem's subscribe signature."""
        if callback is None:
            return
        self._subs.setdefault(event_name, []).append((module_name, callback))

    def unsubscribe(self, module_name: str, event_name: str) -> None:
        """Match the real EventSystem's unsubscribe signature."""
        if event_name in self._subs:
            self._subs[event_name] = [
                (mn, cb) for mn, cb in self._subs[event_name]
                if mn != module_name
            ]

    def emit_sync(self, event_name: str, payload: dict[str, Any]) -> int:
        """Synchronous emit for the proactive engine's internal use."""
        subs = self._subs.get(event_name, [])
        invoked = 0
        for _mn, callback in subs:
            try:
                callback(event_name, payload)
                invoked += 1
            except Exception as exc:
                logger.warning("LightEventBus: callback error on '%s': %s", event_name, exc)
        return invoked


# ---------------------------------------------------------------------------
# ProactiveTrigger — what causes a module to self-start
# ---------------------------------------------------------------------------

@dataclass
class ProactiveTrigger:
    """A condition that causes a module to initiate work autonomously."""

    trigger_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    module_name: str = ""
    trigger_type: str = "condition"  # event | schedule | condition | discovery
    description: str = ""
    event_name: str | None = None
    schedule: str | None = None          # "every 6 hours", "cron 08:00"
    condition: Callable[[], bool] | None = None
    action: str = ""
    priority: int = 4                    # 1 = highest, 4 = background
    max_frequency: int | None = None     # minimum seconds between firings
    last_fired: datetime | None = None
    enabled: bool = True
    requires_approval: bool = False


# ---------------------------------------------------------------------------
# Schedule parsing helpers
# ---------------------------------------------------------------------------

_INTERVAL_RE = re.compile(r"every\s+(\d+)\s+(hour|minute|second)s?", re.IGNORECASE)
_CRON_RE = re.compile(r"cron\s+(\d{1,2}):(\d{2})", re.IGNORECASE)

_INTERVAL_MULTIPLIERS = {"hour": 3600, "minute": 60, "second": 1}


def _parse_interval_seconds(schedule: str) -> int | None:
    """Parse 'every N hours/minutes/seconds' → total seconds, or None."""
    m = _INTERVAL_RE.search(schedule)
    if m:
        count = int(m.group(1))
        unit = m.group(2).lower()
        return count * _INTERVAL_MULTIPLIERS[unit]
    return None


def _parse_cron_time(schedule: str) -> tuple[int, int] | None:
    """Parse 'cron HH:MM' → (hour, minute), or None."""
    m = _CRON_RE.search(schedule)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


# ---------------------------------------------------------------------------
# ProactiveEngine — the core
# ---------------------------------------------------------------------------

class ProactiveEngine:
    """Manages proactive triggers, rate limits, idle work, and persistence.

    The engine never executes module actions directly.  It produces task
    descriptor dicts that the orchestrator routes through the normal
    pipeline (including Cerberus safety checks).

    Accepts the real ``EventSystem`` (from ``modules.shadow.events``) or
    falls back to a built-in ``_LightEventBus``.  Either way, event
    triggers subscribe via the same interface.
    """

    def __init__(
        self,
        event_system: Any | None = None,
        data_dir: str | Path = "data",
        rate_limit_per_hour: int = 100,
        spam_threshold_per_hour: int = 10,
    ) -> None:
        self._event_system = event_system or _LightEventBus()
        self._triggers: dict[str, ProactiveTrigger] = {}
        self._pending_event_fires: list[str] = []
        self._fire_history: list[tuple[str, float]] = []  # (trigger_id, epoch)
        self._data_file = Path(data_dir) / "proactive_triggers.json"
        self._rate_limit = rate_limit_per_hour
        self._spam_threshold = spam_threshold_per_hour
        self._background_stopped = False
        self._spam_disabled_triggers: list[str] = []  # trigger IDs auto-disabled
        self.load_triggers()

    # ------------------------------------------------------------------
    # Trigger registration
    # ------------------------------------------------------------------

    def register_trigger(self, trigger: ProactiveTrigger) -> str:
        """Register a trigger.  Subscribes event triggers to the EventSystem."""
        self._triggers[trigger.trigger_id] = trigger

        if trigger.trigger_type == "event" and trigger.event_name:
            # Use the existing EventSystem API: subscribe(module_name, event_name, callback)
            self._event_system.subscribe(
                f"proactive_{trigger.trigger_id[:8]}",
                trigger.event_name,
                lambda event_name, payload, tid=trigger.trigger_id: self._on_event_fired(tid, payload),
            )

        logger.info(
            "Registered trigger %s (%s) for %s",
            trigger.trigger_id[:8], trigger.trigger_type, trigger.module_name,
        )
        self.save_triggers()
        return trigger.trigger_id

    def unregister_trigger(self, trigger_id: str) -> None:
        """Remove a trigger and unsubscribe from events if applicable."""
        trigger = self._triggers.pop(trigger_id, None)
        if trigger is None:
            return
        if trigger.trigger_type == "event" and trigger.event_name:
            self._event_system.unsubscribe(
                f"proactive_{trigger.trigger_id[:8]}",
                trigger.event_name,
            )
        self.save_triggers()
        logger.info("Unregistered trigger %s", trigger_id[:8])

    # ------------------------------------------------------------------
    # Event callback (marks trigger as needing to fire)
    # ------------------------------------------------------------------

    def _on_event_fired(self, trigger_id: str, _data: dict[str, Any]) -> None:
        """Called by EventSystem when a subscribed event emits."""
        self._pending_event_fires.append(trigger_id)

    # ------------------------------------------------------------------
    # Core: check all triggers
    # ------------------------------------------------------------------

    def check_triggers(self) -> list[dict[str, Any]]:
        """Check all triggers and return task dicts for those that fire.

        Called by the orchestrator on each loop iteration (Step 1.9).
        Event triggers are collected from ``_pending_event_fires``.
        Schedule and condition triggers are polled directly.
        """
        if self._background_stopped:
            return []

        now = datetime.now()
        now_ts = time.time()
        tasks: list[dict[str, Any]] = []

        # Collect event-fired trigger IDs
        event_fired_ids = list(self._pending_event_fires)
        self._pending_event_fires.clear()

        for trigger in list(self._triggers.values()):
            if not trigger.enabled:
                continue

            should_fire = False

            # Event triggers
            if trigger.trigger_type == "event" and trigger.trigger_id in event_fired_ids:
                should_fire = True

            # Schedule triggers
            elif trigger.trigger_type == "schedule" and trigger.schedule:
                should_fire = self._check_schedule(trigger, now)

            # Condition / discovery triggers
            elif trigger.trigger_type in ("condition", "discovery") and trigger.condition is not None:
                try:
                    should_fire = bool(trigger.condition())
                except Exception as exc:
                    logger.warning("Condition check failed for %s: %s", trigger.trigger_id[:8], exc)

            if not should_fire:
                continue

            # Frequency guard
            if trigger.max_frequency and trigger.last_fired:
                elapsed = (now - trigger.last_fired).total_seconds()
                if elapsed < trigger.max_frequency:
                    continue

            # Global rate limit
            if not self._check_rate_limit(now_ts):
                logger.warning("Global rate limit reached (%d/hour) — skipping triggers", self._rate_limit)
                break

            # Per-trigger spam check
            if self._auto_disable_spam(trigger, now_ts):
                continue

            # Fire!
            trigger.last_fired = now
            self._fire_history.append((trigger.trigger_id, now_ts))

            task = {
                "description": trigger.action,
                "assigned_module": trigger.module_name,
                "priority": trigger.priority,
                "source": "proactive",
                "trigger_id": trigger.trigger_id,
                "requires_approval": trigger.requires_approval,
                "requires_safety_check": True,
            }
            tasks.append(task)
            logger.info(
                "Trigger fired: %s (%s) → %s",
                trigger.trigger_id[:8], trigger.description, trigger.module_name,
            )

        if tasks:
            self.save_triggers()

        return tasks

    # ------------------------------------------------------------------
    # Schedule checking
    # ------------------------------------------------------------------

    def _check_schedule(self, trigger: ProactiveTrigger, now: datetime) -> bool:
        """Return True if a schedule trigger is due to fire."""
        if not trigger.schedule:
            return False

        # Interval-based: "every N hours/minutes/seconds"
        interval = _parse_interval_seconds(trigger.schedule)
        if interval is not None:
            if trigger.last_fired is None:
                return True  # Never fired → fire now
            elapsed = (now - trigger.last_fired).total_seconds()
            return elapsed >= interval

        # Cron-based: "cron HH:MM" — fire once per day at that time
        cron_time = _parse_cron_time(trigger.schedule)
        if cron_time is not None:
            hour, minute = cron_time
            if now.hour == hour and now.minute == minute:
                if trigger.last_fired is None:
                    return True
                # Only fire once per day
                return trigger.last_fired.date() < now.date()

        logger.warning("Unrecognized schedule format: %s", trigger.schedule)
        return False

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _check_rate_limit(self, now_ts: float) -> bool:
        """Return True if under the global rate limit (fires per hour)."""
        cutoff = now_ts - 3600
        self._fire_history = [
            (tid, ts) for tid, ts in self._fire_history if ts > cutoff
        ]
        return len(self._fire_history) < self._rate_limit

    def _auto_disable_spam(self, trigger: ProactiveTrigger, now_ts: float) -> bool:
        """Disable a trigger if it fires > spam_threshold times per hour.

        Returns True if the trigger was just disabled (caller should skip it).
        """
        cutoff = now_ts - 3600
        count = sum(
            1 for tid, ts in self._fire_history
            if tid == trigger.trigger_id and ts > cutoff
        )
        if count >= self._spam_threshold:
            trigger.enabled = False
            self._spam_disabled_triggers.append(trigger.trigger_id)
            logger.warning(
                "Auto-disabled trigger %s (%s) — fired %d times in the last hour",
                trigger.trigger_id[:8], trigger.description, count,
            )
            return True
        return False

    # ------------------------------------------------------------------
    # Idle work cycle
    # ------------------------------------------------------------------

    def idle_work_cycle(self) -> dict[str, Any] | None:
        """Return the highest-priority idle task, or None if nothing to do.

        Called by the orchestrator when the queue is empty and no user
        input is pending.  Waterfall priority order:

        1. Pending module-to-module requests
        2. Growth Engine daily goals
        3. Omen code improvements
        4. Sentinel security scans
        5. Reaper technology watch
        6. Morpheus experiments
        7. Grimoire memory maintenance
        """
        if self._background_stopped:
            return None

        waterfall = [
            ("shadow", "Check for pending module-to-module requests"),
            ("shadow", "Review and work on today's growth goals"),
            ("omen", "Scan codebase for improvement opportunities"),
            ("sentinel", "Run scheduled security scan"),
            ("reaper", "Check technology watch list for updates"),
            ("morpheus", "Run queued creative experiments"),
            ("grimoire", "Compact old memories and merge duplicates"),
        ]

        for module_name, action in waterfall:
            task = {
                "description": action,
                "assigned_module": module_name,
                "priority": 4,
                "source": "idle_cycle",
                "requires_approval": False,
                "requires_safety_check": True,
            }
            return task  # Return the first one — orchestrator processes one at a time

        return None  # pragma: no cover — waterfall always has entries

    # ------------------------------------------------------------------
    # Trigger management
    # ------------------------------------------------------------------

    def get_active_triggers(self, module_name: str | None = None) -> list[ProactiveTrigger]:
        """List all enabled triggers, optionally filtered by module."""
        triggers = [t for t in self._triggers.values() if t.enabled]
        if module_name is not None:
            triggers = [t for t in triggers if t.module_name == module_name]
        return triggers

    def enable_trigger(self, trigger_id: str) -> None:
        """Re-enable a disabled trigger."""
        if trigger_id in self._triggers:
            self._triggers[trigger_id].enabled = True
            self.save_triggers()

    def disable_trigger(self, trigger_id: str) -> None:
        """Disable a trigger without removing it."""
        if trigger_id in self._triggers:
            self._triggers[trigger_id].enabled = False
            self.save_triggers()

    def get_initiative_report(self) -> dict[str, Any]:
        """Summary of proactive system state for Harbinger/creator."""
        now_ts = time.time()
        cutoff_hour = now_ts - 3600
        cutoff_day = now_ts - 86400

        by_module: dict[str, int] = {}
        for t in self._triggers.values():
            by_module[t.module_name] = by_module.get(t.module_name, 0) + 1

        return {
            "total_triggers": len(self._triggers),
            "active_triggers": sum(1 for t in self._triggers.values() if t.enabled),
            "disabled_triggers": sum(1 for t in self._triggers.values() if not t.enabled),
            "fires_last_hour": sum(1 for _, ts in self._fire_history if ts > cutoff_hour),
            "fires_last_24h": sum(1 for _, ts in self._fire_history if ts > cutoff_day),
            "by_module": by_module,
            "background_stopped": self._background_stopped,
            "spam_disabled": list(self._spam_disabled_triggers),
            "triggers": [
                {
                    "id": t.trigger_id[:8],
                    "module": t.module_name,
                    "type": t.trigger_type,
                    "description": t.description,
                    "enabled": t.enabled,
                    "last_fired": t.last_fired.isoformat() if t.last_fired else None,
                }
                for t in self._triggers.values()
            ],
        }

    # ------------------------------------------------------------------
    # Creator controls
    # ------------------------------------------------------------------

    def stop_all_background(self) -> None:
        """Stop all proactive work.  Creator command: 'stop all background work'."""
        self._background_stopped = True
        logger.info("All proactive background work stopped by creator")

    def resume_all_background(self) -> None:
        """Resume proactive work.  Creator command: 'resume background work'."""
        self._background_stopped = False
        logger.info("Proactive background work resumed")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_triggers(self) -> None:
        """Persist triggers and fire history to JSON."""
        triggers_data = []
        for t in self._triggers.values():
            triggers_data.append({
                "trigger_id": t.trigger_id,
                "module_name": t.module_name,
                "trigger_type": t.trigger_type,
                "description": t.description,
                "event_name": t.event_name,
                "schedule": t.schedule,
                # condition (Callable) is NOT serialized
                "action": t.action,
                "priority": t.priority,
                "max_frequency": t.max_frequency,
                "last_fired": t.last_fired.isoformat() if t.last_fired else None,
                "enabled": t.enabled,
                "requires_approval": t.requires_approval,
            })

        # Prune fire history to last 24 hours
        cutoff = time.time() - 86400
        recent_history = [
            [tid, ts] for tid, ts in self._fire_history if ts > cutoff
        ]

        payload = {
            "triggers": triggers_data,
            "fire_history": recent_history,
            "saved_at": datetime.now().isoformat(),
        }

        try:
            self._data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._data_file, "w") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            logger.warning("Failed to save proactive triggers: %s", exc)

    def load_triggers(self) -> None:
        """Load triggers and fire history from JSON."""
        if not self._data_file.exists():
            return

        try:
            with open(self._data_file, "r") as f:
                payload = json.load(f)

            for td in payload.get("triggers", []):
                trigger = ProactiveTrigger(
                    trigger_id=td["trigger_id"],
                    module_name=td["module_name"],
                    trigger_type=td["trigger_type"],
                    description=td.get("description", ""),
                    event_name=td.get("event_name"),
                    schedule=td.get("schedule"),
                    condition=None,  # Callables not serialized
                    action=td.get("action", ""),
                    priority=td.get("priority", 4),
                    max_frequency=td.get("max_frequency"),
                    last_fired=(
                        datetime.fromisoformat(td["last_fired"])
                        if td.get("last_fired") else None
                    ),
                    enabled=td.get("enabled", True),
                    requires_approval=td.get("requires_approval", False),
                )
                self._triggers[trigger.trigger_id] = trigger

                # Re-subscribe event triggers
                if trigger.trigger_type == "event" and trigger.event_name:
                    self._event_system.subscribe(
                        f"proactive_{trigger.trigger_id[:8]}",
                        trigger.event_name,
                        lambda event_name, payload, tid=trigger.trigger_id: self._on_event_fired(tid, payload),
                    )

            self._fire_history = [
                (entry[0], entry[1])
                for entry in payload.get("fire_history", [])
            ]

            logger.info("Loaded %d proactive triggers", len(self._triggers))

        except Exception as exc:
            logger.warning("Failed to load proactive triggers: %s", exc)

    # ------------------------------------------------------------------
    # Default trigger registration
    # ------------------------------------------------------------------

    def register_default_triggers(self) -> None:
        """Register the standard set of triggers for all modules.

        Idempotent: triggers whose IDs are already registered are skipped.
        Condition-based triggers attach their Callable here (since
        Callables are not serialized to JSON).
        """
        existing_descriptions = {t.description for t in self._triggers.values()}

        defaults = self._build_default_triggers()
        registered = 0
        for trigger in defaults:
            if trigger.description in existing_descriptions:
                continue
            self.register_trigger(trigger)
            registered += 1

        if registered:
            logger.info("Registered %d default proactive triggers", registered)

    def _build_default_triggers(self) -> list[ProactiveTrigger]:
        """Build the full set of default triggers for all 13 modules."""
        triggers: list[ProactiveTrigger] = []

        # --- Sentinel ---
        triggers.extend([
            ProactiveTrigger(
                module_name="sentinel",
                trigger_type="event",
                description="Sentinel investigates when security alert fires",
                event_name="SECURITY_ALERT",
                action="Investigate threat, build defense profile, notify creator",
                priority=2,
                max_frequency=60,
            ),
            ProactiveTrigger(
                module_name="sentinel",
                trigger_type="schedule",
                description="Sentinel scans log files for suspicious patterns",
                schedule="every 6 hours",
                action="Scan Shadow's log files for suspicious patterns",
                priority=4,
                max_frequency=21600,
            ),
            ProactiveTrigger(
                module_name="sentinel",
                trigger_type="schedule",
                description="Sentinel reviews firewall rules daily",
                schedule="cron 09:00",
                action="Review firewall rules and recommend updates",
                priority=4,
                max_frequency=86400,
            ),
            ProactiveTrigger(
                module_name="sentinel",
                trigger_type="event",
                description="Sentinel emergency audit on heartbeat miss",
                event_name="CERBERUS_HEARTBEAT_MISSED",
                action="Emergency security audit — Cerberus heartbeat missed",
                priority=1,
                max_frequency=300,
            ),
        ])

        # --- Omen ---
        triggers.extend([
            ProactiveTrigger(
                module_name="omen",
                trigger_type="event",
                description="Omen analyzes test failure and attempts fix",
                event_name="CODE_TEST_FAILURE",
                action="Analyze test failure, attempt fix, re-run tests",
                priority=3,
                max_frequency=120,
            ),
            ProactiveTrigger(
                module_name="omen",
                trigger_type="event",
                description="Omen reviews changed code for quality issues",
                event_name="CODE_CHANGE",
                action="Review changed code for quality issues",
                priority=4,
                max_frequency=300,
            ),
            ProactiveTrigger(
                module_name="omen",
                trigger_type="schedule",
                description="Omen scans codebase daily for improvements",
                schedule="cron 02:00",
                action="Scan Shadow codebase for improvement opportunities",
                priority=4,
                max_frequency=86400,
            ),
            ProactiveTrigger(
                module_name="omen",
                trigger_type="event",
                description="Omen researches and prototypes new capability",
                event_name="NEW_CAPABILITY_NEEDED",
                action="Research and prototype the needed capability",
                priority=3,
                max_frequency=600,
            ),
            ProactiveTrigger(
                module_name="omen",
                trigger_type="discovery",
                description="Omen proposes implementation of discovered patterns",
                action="Propose implementation of code pattern Shadow doesn't use yet",
                priority=4,
                max_frequency=86400,
                condition=lambda: False,  # Placeholder — real logic added when Omen's pattern DB is queried
            ),
        ])

        # --- Reaper ---
        triggers.extend([
            ProactiveTrigger(
                module_name="reaper",
                trigger_type="event",
                description="Reaper researches new capability topic",
                event_name="NEW_CAPABILITY_NEEDED",
                action="Research the needed capability topic",
                priority=3,
                max_frequency=600,
            ),
            ProactiveTrigger(
                module_name="reaper",
                trigger_type="schedule",
                description="Reaper checks technology watch list",
                schedule="every 12 hours",
                action="Check technology watch list for updates",
                priority=4,
                max_frequency=43200,
            ),
            ProactiveTrigger(
                module_name="reaper",
                trigger_type="event",
                description="Reaper retries poor research results",
                event_name="RESEARCH_COMPLETE",
                action="If results were poor, reformulate and retry research",
                priority=4,
                max_frequency=600,
            ),
        ])

        # --- Wraith ---
        triggers.extend([
            ProactiveTrigger(
                module_name="wraith",
                trigger_type="event",
                description="Wraith delivers fired reminder with follow-up",
                event_name="REMINDER_FIRED",
                action="Deliver reminder and ask for follow-up",
                priority=2,
                max_frequency=30,
            ),
            ProactiveTrigger(
                module_name="wraith",
                trigger_type="schedule",
                description="Wraith prepares morning task summary",
                schedule="cron 07:00",
                action="Prepare daily task summary for creator",
                priority=3,
                max_frequency=86400,
            ),
            ProactiveTrigger(
                module_name="wraith",
                trigger_type="schedule",
                description="Wraith prepares end-of-day report",
                schedule="cron 20:00",
                action="Prepare end-of-day report for creator",
                priority=3,
                max_frequency=86400,
            ),
        ])

        # --- Harbinger ---
        triggers.extend([
            ProactiveTrigger(
                module_name="harbinger",
                trigger_type="schedule",
                description="Harbinger compiles morning briefing",
                schedule="cron 07:00",
                action="Compile and deliver morning briefing",
                priority=3,
                max_frequency=86400,
            ),
            ProactiveTrigger(
                module_name="harbinger",
                trigger_type="schedule",
                description="Harbinger compiles daily summary",
                schedule="cron 20:00",
                action="Compile daily summary for creator",
                priority=3,
                max_frequency=86400,
            ),
            ProactiveTrigger(
                module_name="harbinger",
                trigger_type="event",
                description="Harbinger batches task completions into report",
                event_name="TASK_COMPLETED",
                action="Batch completed tasks into progress report",
                priority=4,
                max_frequency=1800,
            ),
            ProactiveTrigger(
                module_name="harbinger",
                trigger_type="event",
                description="Harbinger notifies creator of needed approval",
                event_name="APPROVAL_NEEDED",
                action="Notify creator via appropriate channel that approval is needed",
                priority=2,
                max_frequency=60,
                requires_approval=False,
            ),
        ])

        # --- Grimoire ---
        triggers.extend([
            ProactiveTrigger(
                module_name="grimoire",
                trigger_type="schedule",
                description="Grimoire compacts old memories daily",
                schedule="cron 03:00",
                action="Compact old memories, merge duplicates",
                priority=4,
                max_frequency=86400,
            ),
            ProactiveTrigger(
                module_name="grimoire",
                trigger_type="condition",
                description="Grimoire triggers cleanup when database is large",
                action="Trigger memory cleanup and archiving",
                priority=4,
                max_frequency=86400,
                condition=lambda: False,  # Replaced at runtime with real size check
            ),
            ProactiveTrigger(
                module_name="grimoire",
                trigger_type="event",
                description="Grimoire flags memory conflicts for resolution",
                event_name="MEMORY_CONFLICT",
                action="Flag conflicting memories for resolution",
                priority=3,
                max_frequency=300,
            ),
        ])

        # --- Cerberus ---
        triggers.extend([
            ProactiveTrigger(
                module_name="cerberus",
                trigger_type="schedule",
                description="Cerberus generates daily safety report",
                schedule="cron 21:00",
                action="Generate daily safety report",
                priority=3,
                max_frequency=86400,
            ),
            ProactiveTrigger(
                module_name="cerberus",
                trigger_type="event",
                description="Cerberus logs blocked action patterns",
                event_name="EXTERNAL_ACTION_BLOCKED",
                action="Log blocked action pattern and check for escalation",
                priority=3,
                max_frequency=120,
            ),
            ProactiveTrigger(
                module_name="cerberus",
                trigger_type="condition",
                description="Cerberus flags calibration when false positives high",
                action="Flag that safety calibration is needed — false positive rate too high",
                priority=3,
                max_frequency=86400,
                condition=lambda: False,  # Replaced at runtime with real rate check
            ),
        ])

        # --- Apex ---
        triggers.extend([
            ProactiveTrigger(
                module_name="apex",
                trigger_type="event",
                description="Apex offers API escalation after max retries",
                event_name="TASK_FAILED",
                action="Offer API escalation for failed task",
                priority=3,
                max_frequency=300,
            ),
            ProactiveTrigger(
                module_name="apex",
                trigger_type="schedule",
                description="Apex reviews escalation log weekly",
                schedule="every 168 hours",
                action="Review escalation-learning log, identify local model gaps",
                priority=4,
                max_frequency=604800,
            ),
        ])

        # --- Nova ---
        triggers.extend([
            ProactiveTrigger(
                module_name="nova",
                trigger_type="event",
                description="Nova formats and delivers ready briefing",
                event_name="BRIEFING_READY",
                action="Format briefing and deliver via appropriate channel",
                priority=3,
                max_frequency=600,
            ),
            ProactiveTrigger(
                module_name="nova",
                trigger_type="event",
                description="Nova stores generated content as template",
                event_name="CONTENT_GENERATED",
                action="Store generated content as reusable template",
                priority=4,
                max_frequency=300,
            ),
        ])

        # --- Morpheus ---
        triggers.extend([
            ProactiveTrigger(
                module_name="morpheus",
                trigger_type="schedule",
                description="Morpheus runs overnight code experiments",
                schedule="cron 01:00",
                action="Run overnight code experiments with Omen",
                priority=4,
                max_frequency=86400,
            ),
            ProactiveTrigger(
                module_name="morpheus",
                trigger_type="event",
                description="Morpheus generates experimental approaches for goals",
                event_name="GROWTH_GOAL_SET",
                action="Generate experimental approaches for growth goal",
                priority=4,
                max_frequency=600,
            ),
        ])

        # --- Cipher ---
        triggers.extend([
            ProactiveTrigger(
                module_name="cipher",
                trigger_type="event",
                description="Cipher validates numerical data from modules",
                event_name="NUMERICAL_DATA_PRODUCED",
                action="Validate calculations in produced numerical data",
                priority=4,
                max_frequency=120,
            ),
            ProactiveTrigger(
                module_name="cipher",
                trigger_type="discovery",
                description="Cipher cross-checks financial data",
                action="Cross-check math when financial data is processed",
                priority=3,
                max_frequency=300,
                condition=lambda: False,  # Replaced at runtime with real financial data check
            ),
        ])

        return triggers
