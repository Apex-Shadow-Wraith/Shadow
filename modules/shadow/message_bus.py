"""
Inter-Module Communication — MessageBus & HandoffProtocol
==========================================================
The backbone that lets Shadow's modules talk to each other, emit events,
and hand off work. MessageBus handles point-to-point and broadcast messaging
with Cerberus safety integration. HandoffProtocol manages structured task
passing between modules with automatic Grimoire context enrichment.

Singleton pattern — one bus per Shadow instance, thread-safe.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Valid message types
MESSAGE_TYPES = {"request", "response", "event", "notification", "handoff"}

# Valid statuses
MESSAGE_STATUSES = {
    "pending", "delivered", "processing", "completed", "failed", "expired",
}


@dataclass
class ModuleMessage:
    """A single message between Shadow modules.

    Every inter-module communication — requests, responses, events,
    notifications, handoffs — flows through this structure.
    """

    message_id: str
    source_module: str
    target_module: str  # module name or "broadcast"
    message_type: str  # request, response, event, notification, handoff
    priority: int  # 1=critical, 2=high, 3=normal, 4=background
    payload: dict[str, Any]
    requires_cerberus: bool = True
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    ttl_seconds: int | None = None
    status: str = "pending"

    def is_expired(self) -> bool:
        """Check if this message has exceeded its TTL."""
        if self.ttl_seconds is None:
            return False
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for SQLite persistence."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["payload"] = json.dumps(self.payload)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ModuleMessage:
        """Deserialize from SQLite row."""
        d = dict(d)
        if isinstance(d.get("timestamp"), str):
            d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        if isinstance(d.get("payload"), str):
            d["payload"] = json.loads(d["payload"])
        if isinstance(d.get("requires_cerberus"), int):
            d["requires_cerberus"] = bool(d["requires_cerberus"])
        return cls(**d)


@dataclass
class TaskHandoff:
    """Structured task passing between modules.

    When one module needs another to do work, this captures the full
    context: what to do, what data to use, what format to return,
    and any relevant memories from Grimoire.
    """

    handoff_id: str
    from_module: str
    to_module: str
    task_description: str
    input_data: dict[str, Any]
    output_format: dict[str, Any] | None = None
    context: dict[str, Any] = field(default_factory=dict)
    deadline: datetime | None = None
    chain_id: str | None = None
    chain_position: int | None = None


class MessageBus:
    """Singleton message bus for inter-module communication.

    Thread-safe, Cerberus-integrated, SQLite-backed. Every message
    is validated, optionally safety-checked, routed to the target
    module's inbox, and persisted for audit trail and restart recovery.
    """

    _instance: MessageBus | None = None
    _init_done: bool = False

    def __new__(cls) -> MessageBus:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if MessageBus._init_done:
            return
        self._lock = threading.Lock()
        self._queues: dict[str, deque[ModuleMessage]] = {}
        self._messages: dict[str, ModuleMessage] = {}
        self._registry = None
        self._cerberus_callback: Callable | None = None
        self._db_path: Path = Path("data/message_bus.db")
        self._db: sqlite3.Connection | None = None
        MessageBus._init_done = True

    def initialize(
        self,
        registry: Any,
        cerberus_callback: Callable | None = None,
        db_path: str | Path = "data/message_bus.db",
    ) -> None:
        """Set up registry reference, Cerberus callback, and SQLite persistence.

        Args:
            registry: ModuleRegistry for validating module names.
            cerberus_callback: Async callable(action_tool, action_params, requesting_module)
                               that returns a SafetyCheckResult. None disables safety checks.
            db_path: Path for the SQLite audit database.
        """
        self._registry = registry
        self._cerberus_callback = cerberus_callback
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._create_tables()
        self._load_pending_messages()
        logger.info("MessageBus initialized (db=%s)", self._db_path)

    def _create_tables(self) -> None:
        """Create the messages table if it doesn't exist."""
        if self._db is None:
            return
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                source_module TEXT NOT NULL,
                target_module TEXT NOT NULL,
                message_type TEXT NOT NULL,
                priority INTEGER DEFAULT 3,
                payload TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                requires_cerberus INTEGER DEFAULT 1,
                correlation_id TEXT,
                created_at TEXT NOT NULL,
                delivered_at TEXT,
                completed_at TEXT,
                ttl_seconds INTEGER
            )
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_target
            ON messages (target_module, status)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_correlation
            ON messages (correlation_id)
        """)
        self._db.commit()

    def _load_pending_messages(self) -> None:
        """Recover undelivered messages from SQLite on restart."""
        if self._db is None:
            return
        cursor = self._db.execute(
            "SELECT * FROM messages WHERE status IN ('pending', 'processing')"
        )
        for row in cursor.fetchall():
            msg = ModuleMessage(
                message_id=row["message_id"],
                source_module=row["source_module"],
                target_module=row["target_module"],
                message_type=row["message_type"],
                priority=row["priority"],
                payload=json.loads(row["payload"]),
                requires_cerberus=bool(row["requires_cerberus"]),
                correlation_id=row["correlation_id"],
                timestamp=datetime.fromisoformat(row["created_at"]),
                ttl_seconds=row["ttl_seconds"],
                status=row["status"],
            )
            if msg.is_expired():
                self._update_message_status(msg.message_id, "expired")
                continue
            self._messages[msg.message_id] = msg
            target = msg.target_module
            if target == "broadcast":
                # Re-broadcast to all known queues
                for module_name in list(self._queues.keys()):
                    if module_name != msg.source_module:
                        self._queues[module_name].append(msg)
            else:
                if target not in self._queues:
                    self._queues[target] = deque()
                self._queues[target].append(msg)
        count = len([m for m in self._messages.values() if m.status == "pending"])
        if count:
            logger.info("Recovered %d pending messages from SQLite", count)

    def _persist_message(self, message: ModuleMessage) -> None:
        """Write a message to SQLite for audit trail and recovery."""
        if self._db is None:
            return
        try:
            self._db.execute(
                """INSERT OR REPLACE INTO messages
                   (message_id, source_module, target_module, message_type,
                    priority, payload, status, requires_cerberus,
                    correlation_id, created_at, delivered_at, completed_at, ttl_seconds)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    message.message_id,
                    message.source_module,
                    message.target_module,
                    message.message_type,
                    message.priority,
                    json.dumps(message.payload),
                    message.status,
                    int(message.requires_cerberus),
                    message.correlation_id,
                    message.timestamp.isoformat(),
                    None,
                    None,
                    message.ttl_seconds,
                ),
            )
            self._db.commit()
        except Exception as e:
            logger.error("Failed to persist message %s: %s", message.message_id, e)

    def _update_message_status(
        self,
        message_id: str,
        status: str,
        timestamp_field: str | None = None,
    ) -> None:
        """Update message status in both memory and SQLite."""
        if message_id in self._messages:
            self._messages[message_id].status = status
        if self._db is None:
            return
        try:
            if timestamp_field:
                self._db.execute(
                    f"UPDATE messages SET status = ?, {timestamp_field} = ? WHERE message_id = ?",
                    (status, datetime.now().isoformat(), message_id),
                )
            else:
                self._db.execute(
                    "UPDATE messages SET status = ? WHERE message_id = ?",
                    (status, message_id),
                )
            self._db.commit()
        except Exception as e:
            logger.error("Failed to update message %s status: %s", message_id, e)

    def _validate_module(self, module_name: str) -> bool:
        """Check that a module name is valid (registered or 'broadcast')."""
        if module_name == "broadcast":
            return True
        if self._registry is None:
            return True  # No registry = skip validation
        return module_name in self._registry

    def _get_all_module_names(self) -> list[str]:
        """Get all registered module names."""
        if self._registry is None:
            return list(self._queues.keys())
        return list(self._registry.online_modules)

    async def _check_cerberus(self, message: ModuleMessage) -> str:
        """Run Cerberus safety check on a message. Returns verdict string."""
        if self._cerberus_callback is None:
            return "allow"
        try:
            result = await self._cerberus_callback(
                action_tool=f"message_bus.{message.message_type}",
                action_params=message.payload,
                requesting_module=message.source_module,
            )
            if hasattr(result, "verdict"):
                return result.verdict.value if hasattr(result.verdict, "value") else str(result.verdict)
            return "allow"
        except Exception as e:
            logger.error("Cerberus check failed for message %s: %s", message.message_id, e)
            return "allow"  # Fail open — don't block on Cerberus errors

    async def send(self, message: ModuleMessage) -> str:
        """Send a message to a target module's inbox.

        Validates source/target, runs Cerberus safety check if required,
        routes to target inbox(es), and persists to SQLite.

        Args:
            message: The ModuleMessage to send.

        Returns:
            The message_id.

        Raises:
            ValueError: If source or target module is invalid, or message_type is unknown.
        """
        # Validate
        if message.message_type not in MESSAGE_TYPES:
            raise ValueError(f"Invalid message_type: {message.message_type}")
        if not self._validate_module(message.source_module):
            raise ValueError(f"Unknown source module: {message.source_module}")
        if not self._validate_module(message.target_module):
            raise ValueError(f"Unknown target module: {message.target_module}")

        # Cerberus safety check
        if message.requires_cerberus:
            verdict = await self._check_cerberus(message)
            if verdict == "deny":
                message.status = "failed"
                self._persist_message(message)
                logger.warning(
                    "Cerberus DENIED message %s from %s to %s: %s",
                    message.message_id, message.source_module,
                    message.target_module, message.payload,
                )
                with self._lock:
                    self._messages[message.message_id] = message
                return message.message_id
            if verdict == "approval_required":
                message.status = "pending"
                self._persist_message(message)
                logger.info(
                    "Cerberus APPROVAL_REQUIRED for message %s — queued",
                    message.message_id,
                )
                with self._lock:
                    self._messages[message.message_id] = message
                return message.message_id

        # Route to inbox(es)
        with self._lock:
            self._messages[message.message_id] = message
            if message.target_module == "broadcast":
                for module_name in self._get_all_module_names():
                    if module_name != message.source_module:
                        if module_name not in self._queues:
                            self._queues[module_name] = deque()
                        self._queues[module_name].append(message)
            else:
                target = message.target_module
                if target not in self._queues:
                    self._queues[target] = deque()
                self._queues[target].append(message)

        self._persist_message(message)
        logger.debug(
            "Message %s sent: %s -> %s (%s)",
            message.message_id, message.source_module,
            message.target_module, message.message_type,
        )
        return message.message_id

    def receive(
        self,
        module_name: str,
        filter_type: str | None = None,
        filter_priority: int | None = None,
    ) -> list[ModuleMessage]:
        """Retrieve pending messages for a module.

        Returns messages sorted by priority (1 first), then timestamp (oldest first).
        Marks returned messages as 'delivered'.

        Args:
            module_name: The module whose inbox to check.
            filter_type: Only return messages of this type (e.g. "request").
            filter_priority: Only return messages at this priority level.

        Returns:
            List of ModuleMessage objects, sorted by priority then timestamp.
        """
        with self._lock:
            if module_name not in self._queues:
                return []

            inbox = self._queues[module_name]
            results = []
            remaining = deque()

            for msg in inbox:
                # Skip expired messages
                if msg.is_expired():
                    self._update_message_status(msg.message_id, "expired")
                    continue
                # Apply filters
                if filter_type and msg.message_type != filter_type:
                    remaining.append(msg)
                    continue
                if filter_priority is not None and msg.priority != filter_priority:
                    remaining.append(msg)
                    continue
                results.append(msg)

            self._queues[module_name] = remaining

        # Sort: priority ascending (1 first), then timestamp ascending (oldest first)
        results.sort(key=lambda m: (m.priority, m.timestamp))

        # Mark as delivered
        for msg in results:
            self._update_message_status(msg.message_id, "delivered", "delivered_at")

        return results

    async def reply(self, original_message_id: str, payload: dict[str, Any]) -> str:
        """Create a response message linked to the original via correlation_id.

        Auto-sets source/target as reverse of original message.

        Args:
            original_message_id: The message_id being replied to.
            payload: The response data.

        Returns:
            The new message_id.

        Raises:
            KeyError: If original message not found.
        """
        if original_message_id not in self._messages:
            raise KeyError(f"Original message not found: {original_message_id}")

        original = self._messages[original_message_id]
        correlation = original.correlation_id or original.message_id

        response = ModuleMessage(
            message_id=str(uuid.uuid4()),
            source_module=original.target_module,
            target_module=original.source_module,
            message_type="response",
            priority=original.priority,
            payload=payload,
            requires_cerberus=False,  # Responses don't need re-checking
            correlation_id=correlation,
            timestamp=datetime.now(),
        )

        # Mark original as completed
        self._update_message_status(
            original_message_id, "completed", "completed_at",
        )

        return await self.send(response)

    async def broadcast(
        self,
        source_module: str,
        event_name: str,
        payload: dict[str, Any],
        priority: int = 3,
    ) -> str:
        """Broadcast an event to all modules except the sender.

        Args:
            source_module: The module emitting the event.
            event_name: Name of the event.
            payload: Event data.
            priority: Message priority (default 3=normal).

        Returns:
            The message_id.
        """
        message = ModuleMessage(
            message_id=str(uuid.uuid4()),
            source_module=source_module,
            target_module="broadcast",
            message_type="event",
            priority=priority,
            payload={"event_name": event_name, **payload},
            requires_cerberus=False,  # Events are internal notifications
            timestamp=datetime.now(),
        )
        return await self.send(message)

    def get_message_status(self, message_id: str) -> str | None:
        """Return the current status of a message, or None if not found."""
        msg = self._messages.get(message_id)
        if msg is None:
            return None
        if msg.is_expired() and msg.status not in ("completed", "failed", "expired"):
            self._update_message_status(message_id, "expired")
            return "expired"
        return msg.status

    def get_conversation(self, correlation_id: str) -> list[ModuleMessage]:
        """Return all messages in a conversation thread, ordered by timestamp.

        Args:
            correlation_id: The correlation_id linking the conversation.

        Returns:
            List of ModuleMessage objects sorted by timestamp.
        """
        thread = []
        for msg in self._messages.values():
            if (
                msg.correlation_id == correlation_id
                or msg.message_id == correlation_id
            ):
                thread.append(msg)
        thread.sort(key=lambda m: m.timestamp)
        return thread

    def cleanup_expired(self) -> int:
        """Remove messages that have exceeded their TTL.

        Returns:
            Count of messages removed.
        """
        expired_ids = []
        with self._lock:
            for msg_id, msg in list(self._messages.items()):
                if msg.is_expired() and msg.status not in ("completed", "failed", "expired"):
                    expired_ids.append(msg_id)
                    msg.status = "expired"

            # Remove from queues
            for module_name, queue in self._queues.items():
                self._queues[module_name] = deque(
                    m for m in queue if m.message_id not in expired_ids
                )

        # Update SQLite
        for msg_id in expired_ids:
            self._update_message_status(msg_id, "expired")

        if expired_ids:
            logger.info("Cleaned up %d expired messages", len(expired_ids))
        return len(expired_ids)

    def reset(self) -> None:
        """Reset the singleton for testing. Clears all state."""
        with self._lock:
            self._queues.clear()
            self._messages.clear()
        if self._db:
            try:
                self._db.close()
            except Exception:
                pass
        self._db = None
        self._registry = None
        self._cerberus_callback = None
        MessageBus._init_done = False
        MessageBus._instance = None

    def shutdown(self) -> None:
        """Clean shutdown — close SQLite connection."""
        if self._db:
            try:
                self._db.close()
            except Exception:
                pass
            self._db = None
        logger.info("MessageBus shut down")


class HandoffProtocol:
    """Standardized task handoff between modules.

    Manages the lifecycle of inter-module task delegation: creating handoffs
    with auto-enriched Grimoire context, tracking completion, handling failures,
    and managing multi-step chains.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        grimoire_search: Callable | None = None,
    ) -> None:
        """Initialize the handoff protocol.

        Args:
            message_bus: The MessageBus to send handoff messages through.
            grimoire_search: Optional async callable(query, n_results) that
                             returns a list of memory dicts for context enrichment.
        """
        self._bus = message_bus
        self._grimoire_search = grimoire_search
        self._handoffs: dict[str, TaskHandoff] = {}

    async def create_handoff(
        self,
        from_module: str,
        to_module: str,
        task: str,
        input_data: dict[str, Any],
        output_format: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        deadline: datetime | None = None,
        chain_id: str | None = None,
        chain_position: int | None = None,
    ) -> TaskHandoff:
        """Create a handoff and send it via the MessageBus.

        Automatically enriches context with relevant Grimoire memories
        by searching for keywords from the task description.

        Args:
            from_module: Module delegating the task.
            to_module: Module that should execute the task.
            task: Human-readable task description.
            input_data: Data the receiving module needs.
            output_format: Schema/description of expected result format.
            context: Additional context (conversation history, etc).
            deadline: Optional deadline for task completion.
            chain_id: If part of a multi-module chain, the chain identifier.
            chain_position: Step N in the chain.

        Returns:
            The created TaskHandoff object.
        """
        handoff_id = str(uuid.uuid4())
        enriched_context = dict(context) if context else {}

        # Auto-enrich from Grimoire
        if self._grimoire_search:
            try:
                memories = await self._grimoire_search(task, 3)
                if memories:
                    enriched_context["grimoire_memories"] = [
                        {
                            "content": m.get("content", ""),
                            "relevance": m.get("relevance", 0.0),
                            "trust_level": m.get("trust_level", 0.0),
                        }
                        for m in memories
                    ]
            except Exception as e:
                logger.warning("Grimoire enrichment failed for handoff %s: %s", handoff_id, e)

        handoff = TaskHandoff(
            handoff_id=handoff_id,
            from_module=from_module,
            to_module=to_module,
            task_description=task,
            input_data=input_data,
            output_format=output_format,
            context=enriched_context,
            deadline=deadline,
            chain_id=chain_id,
            chain_position=chain_position,
        )
        self._handoffs[handoff_id] = handoff

        # Send as a message via the bus
        message = ModuleMessage(
            message_id=str(uuid.uuid4()),
            source_module=from_module,
            target_module=to_module,
            message_type="handoff",
            priority=2,  # Handoffs are high priority
            payload={
                "handoff_id": handoff_id,
                "task": task,
                "input_data": input_data,
                "output_format": output_format,
                "context": enriched_context,
                "deadline": deadline.isoformat() if deadline else None,
                "chain_id": chain_id,
                "chain_position": chain_position,
            },
            requires_cerberus=True,
            correlation_id=chain_id,
            timestamp=datetime.now(),
        )
        await self._bus.send(message)

        logger.info(
            "Handoff %s created: %s -> %s (%s)",
            handoff_id, from_module, to_module, task,
        )
        return handoff

    async def complete_handoff(
        self, handoff_id: str, result: dict[str, Any],
    ) -> None:
        """Mark a handoff as completed and send result to the originator.

        Args:
            handoff_id: The handoff to complete.
            result: The result data to send back.

        Raises:
            KeyError: If handoff_id not found.
        """
        if handoff_id not in self._handoffs:
            raise KeyError(f"Handoff not found: {handoff_id}")

        handoff = self._handoffs[handoff_id]

        # Send result back to originator
        message = ModuleMessage(
            message_id=str(uuid.uuid4()),
            source_module=handoff.to_module,
            target_module=handoff.from_module,
            message_type="response",
            priority=2,
            payload={
                "handoff_id": handoff_id,
                "status": "completed",
                "result": result,
            },
            requires_cerberus=False,
            correlation_id=handoff.chain_id or handoff_id,
            timestamp=datetime.now(),
        )
        await self._bus.send(message)

        logger.info("Handoff %s completed: %s -> %s", handoff_id, handoff.to_module, handoff.from_module)

        # If part of a chain, the orchestrator handles triggering the next step
        del self._handoffs[handoff_id]

    async def fail_handoff(self, handoff_id: str, reason: str) -> None:
        """Mark a handoff as failed and notify the originator.

        Args:
            handoff_id: The handoff that failed.
            reason: Human-readable failure reason.

        Raises:
            KeyError: If handoff_id not found.
        """
        if handoff_id not in self._handoffs:
            raise KeyError(f"Handoff not found: {handoff_id}")

        handoff = self._handoffs[handoff_id]

        # Notify originator of failure
        message = ModuleMessage(
            message_id=str(uuid.uuid4()),
            source_module=handoff.to_module,
            target_module=handoff.from_module,
            message_type="response",
            priority=1,  # Failures are critical
            payload={
                "handoff_id": handoff_id,
                "status": "failed",
                "reason": reason,
            },
            requires_cerberus=False,
            correlation_id=handoff.chain_id or handoff_id,
            timestamp=datetime.now(),
        )
        await self._bus.send(message)

        logger.warning(
            "Handoff %s failed: %s -> %s (reason: %s)",
            handoff_id, handoff.to_module, handoff.from_module, reason,
        )

        del self._handoffs[handoff_id]

    def get_handoff(self, handoff_id: str) -> TaskHandoff | None:
        """Get a handoff by ID, or None if not found/completed."""
        return self._handoffs.get(handoff_id)

    @property
    def active_handoffs(self) -> int:
        """Count of currently active (incomplete) handoffs."""
        return len(self._handoffs)
