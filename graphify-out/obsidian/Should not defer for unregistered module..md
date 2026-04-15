---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L249"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Should not defer for unregistered module.

## Connections
- [[.test_no_defer_unknown_module()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager