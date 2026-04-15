---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L238"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# find_workflow uses Grimoire semantic search when available.

## Connections
- [[.test_find_with_grimoire()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store