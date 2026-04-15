---
source_file: "tests\test_standing_tasks.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L78"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# Provide a running event loop for marshaling.

## Connections
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[StandingTaskScheduler]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[event_loop_for_tasks()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools