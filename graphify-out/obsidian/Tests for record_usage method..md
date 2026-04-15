---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L298"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# Tests for record_usage method.

## Connections
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[TestRecordUsage]] - `rationale_for` [EXTRACTED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store