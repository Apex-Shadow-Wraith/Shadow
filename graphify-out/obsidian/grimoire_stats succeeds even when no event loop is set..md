---
source_file: "tests\test_standing_tasks.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L308"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# grimoire_stats succeeds even when no event loop is set.

## Connections
- [[.test_works_without_event_loop()]] - `rationale_for` [EXTRACTED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[StandingTaskScheduler]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools