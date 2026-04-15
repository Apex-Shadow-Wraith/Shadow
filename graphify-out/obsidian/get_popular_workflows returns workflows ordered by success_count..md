---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L355"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# get_popular_workflows returns workflows ordered by success_count.

## Connections
- [[.test_returns_most_used()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store