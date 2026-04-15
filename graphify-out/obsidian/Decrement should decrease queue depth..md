---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L360"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Decrement should decrease queue depth.

## Connections
- [[.test_decrement_queue()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager