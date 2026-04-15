---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L19"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# Return a temp DB path.

## Connections
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]
- [[tmp_db()_6]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store