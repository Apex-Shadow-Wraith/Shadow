---
source_file: "tests\test_context_orchestrator.py"
type: "rationale"
community: "Context Orchestrator"
location: "L217"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Orchestrator
---

# Result total_tokens should not exceed token_budget.

## Connections
- [[.test_respects_token_budget()]] - `rationale_for` [EXTRACTED]
- [[ContextOrchestrator]] - `uses` [INFERRED]
- [[ContextPackage]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Orchestrator