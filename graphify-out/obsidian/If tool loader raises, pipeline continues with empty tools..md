---
source_file: "tests\test_context_orchestrator.py"
type: "rationale"
community: "Context Orchestrator"
location: "L407"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Orchestrator
---

# If tool loader raises, pipeline continues with empty tools.

## Connections
- [[.test_tool_loader_exception_handled()]] - `rationale_for` [EXTRACTED]
- [[ContextOrchestrator]] - `uses` [INFERRED]
- [[ContextPackage]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Orchestrator