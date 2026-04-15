---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L95"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# store_workflow also stores in Grimoire for semantic search.

## Connections
- [[.test_stores_in_grimoire()_2]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store