---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L400"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# Empty store: stats returns valid zeroes.

## Connections
- [[.test_empty_store_stats()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store