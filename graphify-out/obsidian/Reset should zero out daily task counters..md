---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L335"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Reset should zero out daily task counters.

## Connections
- [[.test_reset_clears_counters()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager