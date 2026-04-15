---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L106"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# store_workflow deduplicates workflows with same tool sequence.

## Connections
- [[.test_deduplicates_same_tool_sequence()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store