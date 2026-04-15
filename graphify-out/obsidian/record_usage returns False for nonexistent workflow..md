---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L342"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# record_usage returns False for nonexistent workflow.

## Connections
- [[.test_nonexistent_workflow_returns_false()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store