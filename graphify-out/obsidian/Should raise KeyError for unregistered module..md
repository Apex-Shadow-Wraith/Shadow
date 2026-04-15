---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L187"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Should raise KeyError for unregistered module.

## Connections
- [[.test_get_state_raises_for_unknown()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager