---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L233"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Should defer when queue_depth > 10.

## Connections
- [[.test_defer_on_high_queue()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager