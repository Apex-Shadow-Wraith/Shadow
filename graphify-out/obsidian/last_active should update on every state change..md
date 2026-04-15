---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L130"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# last_active should update on every state change.

## Connections
- [[.test_last_active_updates()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager