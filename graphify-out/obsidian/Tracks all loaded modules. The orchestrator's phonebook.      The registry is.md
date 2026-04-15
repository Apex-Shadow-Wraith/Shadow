---
source_file: "modules\base.py"
type: "rationale"
community: "Async Task Queue"
location: "L350"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Tracks all loaded modules. The orchestrator's phonebook.      The registry is

## Connections
- [[Cerberus]] - `uses` [INFERRED]
- [[GrimoireReader]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `rationale_for` [EXTRACTED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue