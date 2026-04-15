---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L415"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# cleanup_unused flags workflows not used in N days.

## Connections
- [[.test_flags_old_workflows()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store