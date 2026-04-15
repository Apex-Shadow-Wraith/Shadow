---
source_file: "tests\test_decision_loop.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L215"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Standard test config with all paths in tmp_path.

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[BrainType]] - `uses` [INFERRED]
- [[ExecutionPlan_1]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[TaskClassification]] - `uses` [INFERRED]
- [[TaskType]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[_test_config()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API