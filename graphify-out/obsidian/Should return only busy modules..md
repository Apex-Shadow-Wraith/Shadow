---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L171"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Should return only busy modules.

## Connections
- [[.test_get_busy_modules()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager