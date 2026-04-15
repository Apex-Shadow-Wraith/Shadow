---
source_file: "tests\test_standing_tasks.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L293"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# After a task runs, schedule info shows the execution time.

## Connections
- [[.test_shows_last_run_after_execution()]] - `rationale_for` [EXTRACTED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[StandingTaskScheduler]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools