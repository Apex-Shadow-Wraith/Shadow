---
source_file: "tests\test_operational_history.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L72"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Build a minimal Orchestrator mock wired to a Grimoire mock.

## Connections
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[_make_orchestrator_with_grimoire()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API