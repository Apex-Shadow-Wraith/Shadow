---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L412"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# Tests for cleanup_unused method.

## Connections
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[TestCleanupUnused]] - `rationale_for` [EXTRACTED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store