---
source_file: "tests\test_message_bus.py"
type: "rationale"
community: "Async Task Queue"
location: "L165"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Reply creates a response linked to the original via correlation_id.

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
- [[test_reply_links_correlation()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue