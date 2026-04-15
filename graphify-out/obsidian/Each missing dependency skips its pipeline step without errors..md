---
source_file: "tests\test_context_orchestrator.py"
type: "rationale"
community: "Context Orchestrator"
location: "L372"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Orchestrator
---

# Each missing dependency skips its pipeline step without errors.

## Connections
- [[.test_missing_dependency_skips_gracefully()]] - `rationale_for` [EXTRACTED]
- [[ContextOrchestrator]] - `uses` [INFERRED]
- [[ContextPackage]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Orchestrator