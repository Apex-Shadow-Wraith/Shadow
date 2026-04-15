---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L48"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Default state should be offline with zero counters.

## Connections
- [[.test_default_state()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager