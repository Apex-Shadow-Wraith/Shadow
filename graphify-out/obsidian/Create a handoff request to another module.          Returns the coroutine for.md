---
source_file: "modules\base.py"
type: "rationale"
community: "Async Task Queue"
location: "L190"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Create a handoff request to another module.          Returns the coroutine for

## Connections
- [[.request_module()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[GrimoireReader]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue