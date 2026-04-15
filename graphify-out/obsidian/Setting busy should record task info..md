---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L91"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Setting busy should record task info.

## Connections
- [[.test_update_to_busy()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager