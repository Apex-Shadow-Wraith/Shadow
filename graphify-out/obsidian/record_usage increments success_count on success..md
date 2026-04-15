---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L301"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# record_usage increments success_count on success.

## Connections
- [[.test_increments_success_count()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store