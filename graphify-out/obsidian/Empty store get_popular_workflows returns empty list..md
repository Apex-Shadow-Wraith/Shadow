---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L372"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# Empty store: get_popular_workflows returns empty list.

## Connections
- [[.test_empty_store_returns_empty()_1]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store