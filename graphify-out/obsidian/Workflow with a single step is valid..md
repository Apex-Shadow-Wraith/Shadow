---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L157"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# Workflow with a single step is valid.

## Connections
- [[.test_single_step_workflow_valid()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store