---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L353"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Increment should increase queue depth.

## Connections
- [[.test_increment_queue()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager