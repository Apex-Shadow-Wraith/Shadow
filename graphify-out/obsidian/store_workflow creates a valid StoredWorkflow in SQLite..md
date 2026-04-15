---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L78"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# store_workflow creates a valid StoredWorkflow in SQLite.

## Connections
- [[.test_creates_valid_workflow_in_sqlite()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store