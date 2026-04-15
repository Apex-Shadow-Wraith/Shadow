---
source_file: "main.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L341"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# Detect if user is asking about a previous task's results.      Returns the task

## Connections
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[OllamaSupervisor]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[ShadowModule]] - `uses` [INFERRED]
- [[StandingTaskScheduler]] - `uses` [INFERRED]
- [[is_task_result_query()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools