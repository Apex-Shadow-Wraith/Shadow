"""
Tests for Inter-Module Communication System
==============================================
Verifies MessageBus, EventSystem, and HandoffProtocol work correctly.
The communication backbone must be reliable — if modules can't talk
to each other, Shadow can't coordinate.
"""

import asyncio
import sqlite3
import tempfile
import threading
import uuid
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.base import BaseModule, ModuleRegistry, ModuleStatus, ToolResult
from modules.shadow.message_bus import (
    HandoffProtocol,
    MessageBus,
    ModuleMessage,
    TaskHandoff,
)
from modules.shadow.events import (
    SECURITY_ALERT,
    TASK_COMPLETED,
    TASK_FAILED,
    EventSystem,
)


# ── Helpers ────────────────────────────────────────────────────────────


class StubModule(BaseModule):
    """Minimal module for testing. No real functionality."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name, description=f"Stub {name}")
        self.status = ModuleStatus.ONLINE

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        return ToolResult(
            success=True,
            content=f"executed {tool_name}",
            tool_name=tool_name,
            module=self.name,
        )

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [{"name": f"{self.name}_tool", "description": "stub", "parameters": {}, "permission_level": "open"}]


def make_registry(*names: str) -> ModuleRegistry:
    """Create a registry with stub modules."""
    registry = ModuleRegistry()
    for name in names:
        registry.register(StubModule(name))
    return registry


def make_message(
    source: str = "sentinel",
    target: str = "omen",
    msg_type: str = "request",
    priority: int = 3,
    payload: dict | None = None,
    requires_cerberus: bool = False,
    ttl: int | None = None,
    correlation_id: str | None = None,
) -> ModuleMessage:
    """Create a test message with sensible defaults."""
    return ModuleMessage(
        message_id=str(uuid.uuid4()),
        source_module=source,
        target_module=target,
        message_type=msg_type,
        priority=priority,
        payload=payload or {"action": "test"},
        requires_cerberus=requires_cerberus,
        correlation_id=correlation_id,
        timestamp=datetime.now(),
        ttl_seconds=ttl,
    )


@pytest.fixture
def bus(tmp_path):
    """Fresh MessageBus for each test — singleton is reset."""
    # Reset singleton
    MessageBus._instance = None
    MessageBus._init_done = False
    b = MessageBus()
    registry = make_registry("sentinel", "omen", "grimoire", "cerberus", "wraith")
    b.initialize(registry=registry, db_path=tmp_path / "test_bus.db")
    yield b
    b.reset()


@pytest.fixture
def event_system(bus):
    """EventSystem wrapping the test bus."""
    return EventSystem(bus)


# ── Test 1: Send / Receive ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_receive(bus):
    """Message sent to a specific module is delivered to that module's inbox."""
    msg = make_message(source="sentinel", target="omen")
    msg_id = await bus.send(msg)

    assert msg_id == msg.message_id

    # Omen receives it
    inbox = bus.receive("omen")
    assert len(inbox) == 1
    assert inbox[0].source_module == "sentinel"
    assert inbox[0].payload == {"action": "test"}
    assert inbox[0].status == "delivered"

    # Sentinel's inbox is empty
    assert bus.receive("sentinel") == []

    # Other modules don't get it
    assert bus.receive("grimoire") == []


# ── Test 2: Broadcast ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_broadcast(bus):
    """Broadcast delivers to all modules except the sender."""
    msg_id = await bus.broadcast("sentinel", "alert", {"level": "high"})

    # All modules except sentinel should get it
    for name in ["omen", "grimoire", "cerberus", "wraith"]:
        inbox = bus.receive(name)
        assert len(inbox) == 1, f"{name} should have 1 message"
        assert inbox[0].payload["event_name"] == "alert"

    # Sender should NOT get it
    assert bus.receive("sentinel") == []


# ── Test 3: Reply links via correlation_id ─────────────────────────────


@pytest.mark.asyncio
async def test_reply_links_correlation(bus):
    """Reply creates a response linked to the original via correlation_id."""
    original = make_message(source="sentinel", target="omen")
    await bus.send(original)

    # Omen receives and replies
    inbox = bus.receive("omen")
    assert len(inbox) == 1
    reply_id = await bus.reply(original.message_id, {"result": "done"})

    # Sentinel gets the reply
    sentinel_inbox = bus.receive("sentinel")
    assert len(sentinel_inbox) == 1
    reply_msg = sentinel_inbox[0]
    assert reply_msg.message_type == "response"
    assert reply_msg.correlation_id == original.message_id
    assert reply_msg.payload == {"result": "done"}
    assert reply_msg.source_module == "omen"
    assert reply_msg.target_module == "sentinel"


# ── Test 4: Priority ordering ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_priority_ordering(bus):
    """Messages are delivered sorted by priority (1 first), then timestamp."""
    # Send in reverse priority order
    msg_low = make_message(source="sentinel", target="omen", priority=4)
    msg_high = make_message(source="grimoire", target="omen", priority=1)
    msg_normal = make_message(source="wraith", target="omen", priority=3)

    await bus.send(msg_low)
    await bus.send(msg_high)
    await bus.send(msg_normal)

    inbox = bus.receive("omen")
    assert len(inbox) == 3
    assert inbox[0].priority == 1  # Critical first
    assert inbox[1].priority == 3  # Normal second
    assert inbox[2].priority == 4  # Background last


# ── Test 5: Cerberus blocks dangerous message ──────────────────────────


@pytest.mark.asyncio
async def test_cerberus_blocks_dangerous(tmp_path):
    """Message with requires_cerberus=True is denied when Cerberus says no."""
    MessageBus._instance = None
    MessageBus._init_done = False
    bus = MessageBus()
    registry = make_registry("sentinel", "omen")

    # Mock Cerberus callback that denies everything
    class MockVerdict:
        verdict = MagicMock()
        verdict.value = "deny"

    async def deny_all(action_tool, action_params, requesting_module):
        return MockVerdict()

    bus.initialize(registry=registry, cerberus_callback=deny_all, db_path=tmp_path / "test.db")

    msg = make_message(source="sentinel", target="omen", requires_cerberus=True)
    msg_id = await bus.send(msg)

    # Message should be marked failed, not delivered
    assert bus.get_message_status(msg_id) == "failed"
    assert bus.receive("omen") == []

    bus.reset()


# ── Test 6: TTL expiration ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ttl_expiration(bus):
    """Messages past their TTL are cleaned up."""
    # Create a message with 0-second TTL (already expired)
    msg = make_message(source="sentinel", target="omen", ttl=0)
    msg.timestamp = datetime.now() - timedelta(seconds=1)
    await bus.send(msg)

    # Cleanup should find it
    count = bus.cleanup_expired()
    assert count == 1

    # It shouldn't be in the inbox
    assert bus.receive("omen") == []


# ── Test 7: Event subscribe / emit ─────────────────────────────────────


@pytest.mark.asyncio
async def test_event_subscribe_emit(bus, event_system):
    """Only subscribed modules receive emitted events."""
    event_system.subscribe("omen", SECURITY_ALERT)
    event_system.subscribe("grimoire", SECURITY_ALERT)
    # wraith does NOT subscribe

    await event_system.emit("sentinel", SECURITY_ALERT, {"threat": "port_scan"})

    # Omen and Grimoire should get it
    assert len(bus.receive("omen")) == 1
    assert len(bus.receive("grimoire")) == 1

    # Wraith should NOT
    assert bus.receive("wraith") == []


# ── Test 8: Event with no subscribers ──────────────────────────────────


@pytest.mark.asyncio
async def test_event_no_subscribers(event_system):
    """Emitting an event with no subscribers doesn't error."""
    # Should not raise
    msg_id = await event_system.emit("sentinel", TASK_COMPLETED, {"task": "scan"})
    assert msg_id is not None  # Returns a tracking ID even with no subscribers


# ── Test 9: Handoff creates message with Grimoire enrichment ───────────


@pytest.mark.asyncio
async def test_handoff_creates_message(bus):
    """Handoff sends a message via bus and enriches context from Grimoire."""
    # Mock Grimoire search
    async def mock_grimoire(query, n_results=3):
        return [
            {"content": "relevant memory", "relevance": 0.9, "trust_level": 0.8},
        ]

    protocol = HandoffProtocol(bus, grimoire_search=mock_grimoire)
    handoff = await protocol.create_handoff(
        from_module="sentinel",
        to_module="omen",
        task="Review suspicious code",
        input_data={"file": "exploit.py"},
        output_format={"verdict": "safe|dangerous"},
    )

    assert isinstance(handoff, TaskHandoff)
    assert handoff.from_module == "sentinel"
    assert handoff.to_module == "omen"
    assert "grimoire_memories" in handoff.context
    assert handoff.context["grimoire_memories"][0]["content"] == "relevant memory"

    # Omen should have a handoff message in inbox
    inbox = bus.receive("omen")
    assert len(inbox) == 1
    assert inbox[0].message_type == "handoff"
    assert inbox[0].payload["task"] == "Review suspicious code"


# ── Test 10: Handoff completion sends reply ────────────────────────────


@pytest.mark.asyncio
async def test_handoff_completion(bus):
    """Completing a handoff sends result back to the originator."""
    protocol = HandoffProtocol(bus)
    handoff = await protocol.create_handoff(
        from_module="sentinel",
        to_module="omen",
        task="Lint code",
        input_data={"code": "print('hi')"},
    )

    # Clear omen's inbox (the handoff message)
    bus.receive("omen")

    # Complete the handoff
    await protocol.complete_handoff(handoff.handoff_id, {"verdict": "clean"})

    # Sentinel should get the result
    inbox = bus.receive("sentinel")
    assert len(inbox) == 1
    assert inbox[0].payload["status"] == "completed"
    assert inbox[0].payload["result"] == {"verdict": "clean"}

    # Handoff should be removed from active tracking
    assert protocol.get_handoff(handoff.handoff_id) is None


# ── Test 11: Handoff failure notifies originator ───────────────────────


@pytest.mark.asyncio
async def test_handoff_failure(bus):
    """Failing a handoff sends failure notification to the originator."""
    protocol = HandoffProtocol(bus)
    handoff = await protocol.create_handoff(
        from_module="sentinel",
        to_module="omen",
        task="Compile binary",
        input_data={"source": "main.c"},
    )
    bus.receive("omen")  # Clear omen inbox

    await protocol.fail_handoff(handoff.handoff_id, "Compiler not found")

    inbox = bus.receive("sentinel")
    assert len(inbox) == 1
    assert inbox[0].payload["status"] == "failed"
    assert inbox[0].payload["reason"] == "Compiler not found"
    assert inbox[0].priority == 1  # Failures are critical

    assert protocol.get_handoff(handoff.handoff_id) is None


# ── Test 12: get_conversation returns full thread ──────────────────────


@pytest.mark.asyncio
async def test_get_conversation(bus):
    """get_conversation returns all messages linked by correlation_id."""
    correlation = str(uuid.uuid4())

    msg1 = make_message(source="sentinel", target="omen", correlation_id=correlation)
    msg2 = make_message(source="omen", target="sentinel", correlation_id=correlation)
    msg2.message_type = "response"

    await bus.send(msg1)
    await bus.send(msg2)

    thread = bus.get_conversation(correlation)
    assert len(thread) == 2
    assert thread[0].timestamp <= thread[1].timestamp


# ── Test 13: SQLite persistence survives restart ───────────────────────


@pytest.mark.asyncio
async def test_sqlite_persistence(tmp_path):
    """Messages persist in SQLite and can be recovered after bus restart."""
    db_path = tmp_path / "persist_test.db"
    registry = make_registry("sentinel", "omen")

    # First bus instance — send a message
    MessageBus._instance = None
    MessageBus._init_done = False
    bus1 = MessageBus()
    bus1.initialize(registry=registry, db_path=db_path)
    msg = make_message(source="sentinel", target="omen")
    await bus1.send(msg)
    bus1.shutdown()

    # Verify it's in SQLite
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM messages").fetchall()
    assert len(rows) >= 1
    assert rows[0]["source_module"] == "sentinel"
    conn.close()

    # Second bus instance — should recover pending messages
    MessageBus._instance = None
    MessageBus._init_done = False
    bus2 = MessageBus()
    bus2.initialize(registry=registry, db_path=db_path)

    inbox = bus2.receive("omen")
    assert len(inbox) >= 1
    assert inbox[0].source_module == "sentinel"
    bus2.reset()


# ── Test 14: Thread safety ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_thread_safety(bus):
    """Concurrent sends from multiple threads don't corrupt state."""
    errors = []

    async def send_batch(source: str, count: int):
        for i in range(count):
            try:
                msg = make_message(source=source, target="omen", payload={"i": i})
                await bus.send(msg)
            except Exception as e:
                errors.append(e)

    # Run concurrent sends from multiple "modules"
    await asyncio.gather(
        send_batch("sentinel", 50),
        send_batch("grimoire", 50),
        send_batch("wraith", 50),
    )

    assert len(errors) == 0

    # All 150 messages should be in omen's inbox
    inbox = bus.receive("omen")
    assert len(inbox) == 150


# ── Test 15: BaseModule convenience methods ────────────────────────────


@pytest.mark.asyncio
async def test_base_module_convenience(bus, event_system):
    """BaseModule convenience methods (send_message, check_inbox, emit_event) work."""
    sentinel = StubModule("sentinel")
    sentinel._message_bus = bus
    sentinel._event_system = event_system

    omen = StubModule("omen")
    omen._message_bus = bus
    omen._event_system = event_system

    # send_message returns a coroutine — await it
    coro = sentinel.send_message("omen", {"task": "review"})
    assert coro is not None
    await coro

    # check_inbox works
    inbox = omen.check_inbox()
    assert len(inbox) == 1
    assert inbox[0].payload == {"task": "review"}

    # subscribe_event + emit_event
    received_events = []

    def on_alert(event_name, payload):
        received_events.append((event_name, payload))

    omen.subscribe_event(SECURITY_ALERT, callback=on_alert)

    coro = sentinel.emit_event(SECURITY_ALERT, {"threat": "test"})
    assert coro is not None
    await coro

    assert len(received_events) == 1
    assert received_events[0][0] == SECURITY_ALERT

    # No-op when bus is None
    orphan = StubModule("orphan")
    assert orphan.send_message("omen", {}) is None
    assert orphan.check_inbox() == []
    assert orphan.emit_event(SECURITY_ALERT, {}) is None


# ── Test 16: Full flow — Sentinel → Omen via MessageBus ───────────────


@pytest.mark.asyncio
async def test_full_flow_sentinel_to_omen(bus):
    """Full integration: Sentinel sends request, Omen receives, replies, Sentinel gets result."""
    # Sentinel sends a code review request to Omen
    request = make_message(
        source="sentinel",
        target="omen",
        msg_type="request",
        priority=2,
        payload={"tool_name": "code_review", "params": {"file": "main.py"}},
    )
    msg_id = await bus.send(request)

    # Omen receives
    omen_inbox = bus.receive("omen")
    assert len(omen_inbox) == 1
    assert omen_inbox[0].payload["tool_name"] == "code_review"

    # Omen replies with results
    reply_id = await bus.reply(msg_id, {"verdict": "safe", "issues": []})

    # Sentinel gets the reply
    sentinel_inbox = bus.receive("sentinel")
    assert len(sentinel_inbox) == 1
    assert sentinel_inbox[0].payload["verdict"] == "safe"
    assert sentinel_inbox[0].correlation_id == msg_id

    # Original message should be marked completed
    assert bus.get_message_status(msg_id) == "completed"

    # Full conversation thread
    thread = bus.get_conversation(msg_id)
    assert len(thread) == 2
    assert thread[0].message_type == "request"
    assert thread[1].message_type == "response"
