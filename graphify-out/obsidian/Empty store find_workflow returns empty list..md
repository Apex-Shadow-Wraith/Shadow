---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L254"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# Empty store: find_workflow returns empty list.

## Connections
- [[.test_empty_store_returns_empty()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store