---
source_file: "modules\base.py"
type: "rationale"
community: "Async Task Queue"
location: "L263"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Subscribe to an event.          Safe no-op if EventSystem is not wired.

## Connections
- [[.subscribe_event()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[GrimoireReader]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue