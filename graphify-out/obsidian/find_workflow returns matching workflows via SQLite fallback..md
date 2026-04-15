---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L174"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# find_workflow returns matching workflows via SQLite fallback.

## Connections
- [[.test_returns_matching_workflows()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store