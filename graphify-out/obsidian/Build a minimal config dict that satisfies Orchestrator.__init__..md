---
source_file: "tests\test_async_wiring.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L436"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Build a minimal config dict that satisfies Orchestrator.__init__.

## Connections
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[_minimal_config()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API