---
source_file: "modules\base.py"
type: "rationale"
community: "Async Task Queue"
location: "L366"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Wire Cerberus for auto-registration of tools at startup and runtime.

## Connections
- [[.set_cerberus()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[GrimoireReader]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue