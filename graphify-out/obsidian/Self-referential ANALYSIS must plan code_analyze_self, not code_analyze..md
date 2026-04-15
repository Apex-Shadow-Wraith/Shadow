---
source_file: "tests\test_code_analyze_routing.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L484"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Self-referential ANALYSIS must plan code_analyze_self, not code_analyze.

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[BrainType]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Omen]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[TaskClassification]] - `uses` [INFERRED]
- [[TaskType]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API