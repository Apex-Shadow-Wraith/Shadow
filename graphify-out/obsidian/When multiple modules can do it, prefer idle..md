---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L206"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# When multiple modules can do it, prefer idle.

## Connections
- [[.test_prefers_idle_over_busy()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager