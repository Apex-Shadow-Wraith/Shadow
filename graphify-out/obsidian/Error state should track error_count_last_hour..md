---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L123"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Error state should track error_count_last_hour.

## Connections
- [[.test_error_tracks_error_count()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager