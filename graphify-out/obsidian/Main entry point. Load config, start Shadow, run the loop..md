---
source_file: "main.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L522"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# Main entry point. Load config, start Shadow, run the loop.

## Connections
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[OllamaSupervisor]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[ShadowModule]] - `uses` [INFERRED]
- [[StandingTaskScheduler]] - `uses` [INFERRED]
- [[main()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools