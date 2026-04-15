---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L314"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# record_usage updates average_duration.

## Connections
- [[.test_updates_average_duration()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store