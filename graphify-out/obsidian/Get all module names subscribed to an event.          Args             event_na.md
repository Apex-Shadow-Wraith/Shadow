---
source_file: "modules\shadow\events.py"
type: "rationale"
community: "Async Task Queue"
location: "L211"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Get all module names subscribed to an event.          Args:             event_na

## Connections
- [[.get_subscribers()]] - `rationale_for` [EXTRACTED]
- [[MessageBus]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue