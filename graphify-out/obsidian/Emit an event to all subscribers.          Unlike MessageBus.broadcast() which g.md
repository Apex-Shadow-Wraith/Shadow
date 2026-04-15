---
source_file: "modules\shadow\events.py"
type: "rationale"
community: "Async Task Queue"
location: "L143"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Emit an event to all subscribers.          Unlike MessageBus.broadcast() which g

## Connections
- [[.emit()]] - `rationale_for` [EXTRACTED]
- [[MessageBus]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue