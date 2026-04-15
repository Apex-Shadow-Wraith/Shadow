---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L280"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# adapt_workflow returns steps as list of dicts.

## Connections
- [[.test_returns_adapted_steps_as_dicts()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store