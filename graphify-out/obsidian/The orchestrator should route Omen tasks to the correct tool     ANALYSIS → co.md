---
source_file: "tests\test_orchestrator.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L1820"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# The orchestrator should route Omen tasks to the correct tool:     ANALYSIS → co

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[BrainType]] - `uses` [INFERRED]
- [[Cerberus]] - `uses` [INFERRED]
- [[ExecutionPlan_1]] - `uses` [INFERRED]
- [[InjectionResult]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[TaskClassification]] - `uses` [INFERRED]
- [[TaskType]] - `uses` [INFERRED]
- [[TestOmenPlanRouting]] - `rationale_for` [EXTRACTED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API