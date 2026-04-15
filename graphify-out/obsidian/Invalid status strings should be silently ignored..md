---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L137"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Invalid status strings should be silently ignored.

## Connections
- [[.test_invalid_status_ignored()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager