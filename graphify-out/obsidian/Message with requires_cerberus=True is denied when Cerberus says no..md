---
source_file: "tests\test_message_bus.py"
type: "rationale"
community: "Async Task Queue"
location: "L212"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Message with requires_cerberus=True is denied when Cerberus says no.

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
- [[test_cerberus_blocks_dangerous()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue