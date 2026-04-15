---
source_file: "tests\test_context_orchestrator.py"
type: "rationale"
community: "Context Orchestrator"
location: "L725"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Orchestrator
---

# Task without module key loads tools with module_name=None.

## Connections
- [[.test_task_with_no_module()]] - `rationale_for` [EXTRACTED]
- [[ContextOrchestrator]] - `uses` [INFERRED]
- [[ContextPackage]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Orchestrator