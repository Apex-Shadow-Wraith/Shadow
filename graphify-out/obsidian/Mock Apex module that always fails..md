---
source_file: "tests\test_fallback_transparency.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L27"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Mock Apex module that always fails.

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[BrainType]] - `uses` [INFERRED]
- [[ExecutionPlan_1]] - `uses` [INFERRED]
- [[MockFailingApex]] - `rationale_for` [EXTRACTED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[TaskClassification]] - `uses` [INFERRED]
- [[TaskType]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API