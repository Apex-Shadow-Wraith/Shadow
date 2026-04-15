---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L216"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# When all capable modules busy, pick shortest queue.

## Connections
- [[.test_busy_fallback_shortest_queue()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager