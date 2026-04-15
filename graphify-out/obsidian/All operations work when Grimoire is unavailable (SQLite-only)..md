---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L481"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# All operations work when Grimoire is unavailable (SQLite-only).

## Connections
- [[.test_graceful_without_grimoire()_1]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store