---
source_file: "modules\shadow\events.py"
type: "rationale"
community: "Async Task Queue"
location: "L122"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Remove a module's subscription to an event.          Args:             module_na

## Connections
- [[.unsubscribe()]] - `rationale_for` [EXTRACTED]
- [[MessageBus]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue