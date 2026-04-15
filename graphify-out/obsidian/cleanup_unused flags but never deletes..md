---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L437"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# cleanup_unused flags but never deletes.

## Connections
- [[.test_doesnt_delete_anything()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store