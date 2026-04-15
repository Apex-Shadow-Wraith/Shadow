---
source_file: "tests\test_context_orchestrator.py"
type: "rationale"
community: "Context Orchestrator"
location: "L426"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Orchestrator
---

# If compressor raises, pipeline continues with raw history.

## Connections
- [[.test_compressor_exception_handled()]] - `rationale_for` [EXTRACTED]
- [[ContextOrchestrator]] - `uses` [INFERRED]
- [[ContextPackage]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Orchestrator