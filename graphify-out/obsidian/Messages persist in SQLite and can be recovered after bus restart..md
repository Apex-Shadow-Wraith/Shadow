---
source_file: "tests\test_message_bus.py"
type: "rationale"
community: "Async Task Queue"
location: "L403"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Messages persist in SQLite and can be recovered after bus restart.

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[EventSystem]] - `uses` [INFERRED]
- [[HandoffProtocol]] - `uses` [INFERRED]
- [[MessageBus]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[TaskHandoff]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[test_sqlite_persistence()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue