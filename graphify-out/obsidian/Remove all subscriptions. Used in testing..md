---
source_file: "modules\shadow\events.py"
type: "rationale"
community: "Async Task Queue"
location: "L230"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Remove all subscriptions. Used in testing.

## Connections
- [[.clear()]] - `rationale_for` [EXTRACTED]
- [[MessageBus]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue