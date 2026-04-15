---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L368"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Queue depth should never go negative.

## Connections
- [[.test_decrement_floor_zero()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager