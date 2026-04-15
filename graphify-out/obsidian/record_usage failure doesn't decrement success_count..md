---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L329"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# record_usage: failure doesn't decrement success_count.

## Connections
- [[.test_failure_doesnt_decrement()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store