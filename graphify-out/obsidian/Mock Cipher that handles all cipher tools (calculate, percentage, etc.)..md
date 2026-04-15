---
source_file: "tests\test_decision_loop.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L57"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Mock Cipher that handles all cipher tools (calculate, percentage, etc.).

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[BrainType]] - `uses` [INFERRED]
- [[ExecutionPlan_1]] - `uses` [INFERRED]
- [[MockCipherModule]] - `rationale_for` [EXTRACTED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[TaskClassification]] - `uses` [INFERRED]
- [[TaskType]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API