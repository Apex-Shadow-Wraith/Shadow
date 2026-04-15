---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L180"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Should return states for all registered modules.

## Connections
- [[.test_get_all_states()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager