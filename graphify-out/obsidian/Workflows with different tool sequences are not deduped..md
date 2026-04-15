---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L127"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# Workflows with different tool sequences are not deduped.

## Connections
- [[.test_different_tools_not_deduped()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store