---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L34"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# WorkflowStore with no Grimoire (SQLite-only mode).

## Connections
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]
- [[store()_1]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store