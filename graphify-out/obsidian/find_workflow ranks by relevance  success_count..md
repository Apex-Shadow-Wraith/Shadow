---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L185"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# find_workflow ranks by relevance * success_count.

## Connections
- [[.test_ranks_by_success_count()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store