---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L100"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Setting idle should clear task info.

## Connections
- [[.test_update_to_idle_clears_task()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager