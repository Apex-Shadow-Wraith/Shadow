---
source_file: "tests\test_orchestrator.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L1077"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Verify the orchestrator no longer imports OpenAI SDK.

## Connections
- [[.test_no_openai_sdk_import()]] - `rationale_for` [EXTRACTED]
- [[BaseModule]] - `uses` [INFERRED]
- [[BrainType]] - `uses` [INFERRED]
- [[Cerberus]] - `uses` [INFERRED]
- [[ExecutionPlan_1]] - `uses` [INFERRED]
- [[InjectionResult]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[TaskClassification]] - `uses` [INFERRED]
- [[TaskType]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API