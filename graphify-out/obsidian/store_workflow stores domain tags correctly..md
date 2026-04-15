---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L141"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# store_workflow stores domain tags correctly.

## Connections
- [[.test_stores_domain_tags()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store