"""
Event System — Pub/Sub for Shadow Modules
===========================================
Wraps the MessageBus to provide a publish/subscribe pattern. Modules
subscribe to named events and receive them when emitted — unlike raw
broadcast, only subscribers get the message.

Standard event constants define the vocabulary of inter-module signals.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Callable

from modules.shadow.message_bus import MessageBus, ModuleMessage

logger = logging.getLogger(__name__)

# ── Standard Event Names ──────────────────────────────────────────────
# These are the canonical events that Shadow modules emit and subscribe to.
# Add new events here — never use raw strings elsewhere.

SECURITY_ALERT = "security_alert"
SYSTEM_HEALTH_WARNING = "system_health_warning"
SYSTEM_HEALTH_CRITICAL = "system_health_critical"
MEMORY_STORED = "memory_stored"
MEMORY_CONFLICT = "memory_conflict"
TASK_COMPLETED = "task_completed"
TASK_FAILED = "task_failed"
CODE_CHANGE = "code_change"
CODE_TEST_FAILURE = "code_test_failure"
MODEL_AVAILABLE = "model_available"
EXTERNAL_ACTION_BLOCKED = "external_action_blocked"
REMINDER_FIRED = "reminder_fired"
RESEARCH_COMPLETE = "research_complete"
BRIEFING_READY = "briefing_ready"
CONTENT_GENERATED = "content_generated"
GROWTH_GOAL_SET = "growth_goal_set"
SHUTDOWN_WARNING = "shutdown_warning"
CERBERUS_HEARTBEAT_MISSED = "cerberus_heartbeat_missed"
NEW_CAPABILITY_NEEDED = "new_capability_needed"
APPROVAL_NEEDED = "approval_needed"
NUMERICAL_DATA_PRODUCED = "numerical_data_produced"

# All standard events for validation
ALL_EVENTS = {
    SECURITY_ALERT,
    SYSTEM_HEALTH_WARNING,
    SYSTEM_HEALTH_CRITICAL,
    MEMORY_STORED,
    MEMORY_CONFLICT,
    TASK_COMPLETED,
    TASK_FAILED,
    CODE_CHANGE,
    CODE_TEST_FAILURE,
    MODEL_AVAILABLE,
    EXTERNAL_ACTION_BLOCKED,
    REMINDER_FIRED,
    RESEARCH_COMPLETE,
    BRIEFING_READY,
    CONTENT_GENERATED,
    GROWTH_GOAL_SET,
    SHUTDOWN_WARNING,
    CERBERUS_HEARTBEAT_MISSED,
    NEW_CAPABILITY_NEEDED,
    APPROVAL_NEEDED,
    NUMERICAL_DATA_PRODUCED,
}


class EventSystem:
    """Pub/sub event system wrapping the MessageBus.

    Modules subscribe to specific event names. When an event is emitted,
    only subscribed modules receive it. Optionally, a callback is invoked
    immediately on delivery (for modules with active loops). Otherwise,
    events queue in the module's MessageBus inbox for polling.
    """

    def __init__(self, message_bus: MessageBus) -> None:
        """Initialize the event system.

        Args:
            message_bus: The MessageBus to route events through.
        """
        self._bus = message_bus
        self._subscriptions: dict[str, list[dict[str, Any]]] = {}

    def subscribe(
        self,
        module_name: str,
        event_name: str,
        callback: Callable | None = None,
    ) -> None:
        """Register a module as a listener for a specific event.

        Args:
            module_name: The subscribing module's name.
            event_name: The event to listen for.
            callback: Optional callable invoked when the event fires.
                      If None, events queue in the module's inbox for polling.
        """
        if event_name not in self._subscriptions:
            self._subscriptions[event_name] = []

        # Don't double-subscribe
        for sub in self._subscriptions[event_name]:
            if sub["module_name"] == module_name:
                sub["callback"] = callback  # Update callback
                return

        self._subscriptions[event_name].append({
            "module_name": module_name,
            "callback": callback,
        })
        logger.debug("Module '%s' subscribed to event '%s'", module_name, event_name)

    def unsubscribe(self, module_name: str, event_name: str) -> None:
        """Remove a module's subscription to an event.

        Args:
            module_name: The module to unsubscribe.
            event_name: The event to stop listening for.
        """
        if event_name not in self._subscriptions:
            return
        self._subscriptions[event_name] = [
            sub for sub in self._subscriptions[event_name]
            if sub["module_name"] != module_name
        ]
        logger.debug("Module '%s' unsubscribed from event '%s'", module_name, event_name)

    async def emit(
        self,
        source_module: str,
        event_name: str,
        payload: dict[str, Any],
        priority: int = 3,
    ) -> str:
        """Emit an event to all subscribers.

        Unlike MessageBus.broadcast() which goes to everyone, this only
        delivers to modules that have subscribed to this specific event.

        Args:
            source_module: The module emitting the event.
            event_name: The event name (use constants from this module).
            payload: Event data.
            priority: Message priority (default 3=normal).

        Returns:
            The message_id of the broadcast message.
        """
        subscribers = self._subscriptions.get(event_name, [])

        if not subscribers:
            logger.debug("Event '%s' emitted by '%s' — no subscribers", event_name, source_module)
            # Still create a message ID for tracking
            return str(uuid.uuid4())

        message_id = str(uuid.uuid4())
        event_payload = {"event_name": event_name, **payload}

        # Fire callbacks for subscribers that have them
        for sub in subscribers:
            if sub["module_name"] == source_module:
                continue  # Don't deliver to self

            if sub["callback"] is not None:
                try:
                    result = sub["callback"](event_name, payload)
                    # Support async callbacks
                    if hasattr(result, "__await__"):
                        await result
                except Exception as e:
                    logger.error(
                        "Event callback failed for '%s' on '%s': %s",
                        sub["module_name"], event_name, e,
                    )

        # Send via MessageBus to subscribers without callbacks (for inbox polling)
        inbox_subscribers = [
            sub["module_name"] for sub in subscribers
            if sub["callback"] is None and sub["module_name"] != source_module
        ]

        for target_module in inbox_subscribers:
            msg = ModuleMessage(
                message_id=str(uuid.uuid4()),
                source_module=source_module,
                target_module=target_module,
                message_type="event",
                priority=priority,
                payload=event_payload,
                requires_cerberus=False,
                correlation_id=message_id,  # Link all event messages
                timestamp=datetime.now(),
            )
            await self._bus.send(msg)

        logger.debug(
            "Event '%s' emitted by '%s' — %d subscribers notified",
            event_name, source_module, len(subscribers),
        )
        return message_id

    def get_subscribers(self, event_name: str) -> list[str]:
        """Get all module names subscribed to an event.

        Args:
            event_name: The event to check.

        Returns:
            List of module names.
        """
        return [
            sub["module_name"]
            for sub in self._subscriptions.get(event_name, [])
        ]

    @property
    def subscription_count(self) -> int:
        """Total number of active subscriptions across all events."""
        return sum(len(subs) for subs in self._subscriptions.values())

    def clear(self) -> None:
        """Remove all subscriptions. Used in testing."""
        self._subscriptions.clear()
