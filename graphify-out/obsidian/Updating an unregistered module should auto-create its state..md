---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L143"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Updating an unregistered module should auto-create its state.

## Connections
- [[.test_unregistered_module_auto_creates()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager