---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L239"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Should defer when error_count_last_hour > 5.

## Connections
- [[.test_defer_on_high_errors()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager