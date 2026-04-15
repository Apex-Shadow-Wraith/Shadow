---
source_file: "main.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L95"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# Create, wire, and initialize everything in the right order.      Dependency chai

## Connections
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[OllamaSupervisor]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[ShadowModule]] - `uses` [INFERRED]
- [[StandingTaskScheduler]] - `uses` [INFERRED]
- [[startup()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools