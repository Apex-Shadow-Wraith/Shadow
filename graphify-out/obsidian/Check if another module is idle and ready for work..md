---
source_file: "modules\base.py"
type: "rationale"
community: "Async Task Queue"
location: "L308"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Check if another module is idle and ready for work.

## Connections
- [[.is_module_available()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[GrimoireReader]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue