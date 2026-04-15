---
source_file: "tests\test_standing_tasks.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L144"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# Helper: create a loop, set it on the scheduler, run a task synchronously.

## Connections
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[StandingTaskScheduler]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[_run_task_with_loop()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools