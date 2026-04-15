---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L384"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# get_workflow_stats returns accurate aggregate stats.

## Connections
- [[.test_returns_accurate_counts()_1]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store