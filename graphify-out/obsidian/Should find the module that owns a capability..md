---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L196"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Should find the module that owns a capability.

## Connections
- [[.test_finds_correct_module()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager