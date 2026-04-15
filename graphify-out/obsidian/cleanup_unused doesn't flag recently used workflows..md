---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L458"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# cleanup_unused doesn't flag recently used workflows.

## Connections
- [[.test_recent_workflows_not_flagged()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store