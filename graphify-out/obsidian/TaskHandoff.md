---
source_file: "modules\shadow\message_bus.py"
type: "code"
community: "Async Task Queue"
location: "L83"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# TaskHandoff

## Connections
- [[.create_handoff()]] - `calls` [EXTRACTED]
- [[BaseModule convenience methods (send_message, check_inbox, emit_event) work.]] - `uses` [INFERRED]
- [[Broadcast delivers to all modules except the sender.]] - `uses` [INFERRED]
- [[Completing a handoff sends result back to the originator.]] - `uses` [INFERRED]
- [[Concurrent sends from multiple threads don't corrupt state.]] - `uses` [INFERRED]
- [[Create a registry with stub modules.]] - `uses` [INFERRED]
- [[Create a test message with sensible defaults.]] - `uses` [INFERRED]
- [[Emitting an event with no subscribers doesn't error.]] - `uses` [INFERRED]
- [[EventSystem wrapping the test bus.]] - `uses` [INFERRED]
- [[Failing a handoff sends failure notification to the originator.]] - `uses` [INFERRED]
- [[Fresh MessageBus for each test — singleton is reset.]] - `uses` [INFERRED]
- [[Full integration Sentinel sends request, Omen receives, replies, Sentinel gets]] - `uses` [INFERRED]
- [[Handoff sends a message via bus and enriches context from Grimoire.]] - `uses` [INFERRED]
- [[Message sent to a specific module is delivered to that module's inbox.]] - `uses` [INFERRED]
- [[Message with requires_cerberus=True is denied when Cerberus says no.]] - `uses` [INFERRED]
- [[Messages are delivered sorted by priority (1 first), then timestamp.]] - `uses` [INFERRED]
- [[Messages past their TTL are cleaned up.]] - `uses` [INFERRED]
- [[Messages persist in SQLite and can be recovered after bus restart.]] - `uses` [INFERRED]
- [[Minimal module for testing. No real functionality.]] - `uses` [INFERRED]
- [[Only subscribed modules receive emitted events.]] - `uses` [INFERRED]
- [[Reply creates a response linked to the original via correlation_id.]] - `uses` [INFERRED]
- [[Structured task passing between modules.      When one module needs another to d]] - `rationale_for` [EXTRACTED]
- [[StubModule]] - `uses` [INFERRED]
- [[Tests for Inter-Module Communication System ====================================]] - `uses` [INFERRED]
- [[get_conversation returns all messages linked by correlation_id.]] - `uses` [INFERRED]
- [[message_bus.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Async_Task_Queue