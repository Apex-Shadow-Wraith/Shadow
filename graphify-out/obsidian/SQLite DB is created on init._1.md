---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L475"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# SQLite DB is created on init.

## Connections
- [[.test_sqlite_db_created_on_init()_3]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store