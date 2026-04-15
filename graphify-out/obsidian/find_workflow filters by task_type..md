---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L206"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# find_workflow filters by task_type.

## Connections
- [[.test_filters_by_task_type()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store