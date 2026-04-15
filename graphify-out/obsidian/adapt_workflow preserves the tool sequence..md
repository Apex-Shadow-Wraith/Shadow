---
source_file: "tests\test_workflow_store.py"
type: "rationale"
community: "Workflow Store"
location: "L267"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Workflow_Store
---

# adapt_workflow preserves the tool sequence.

## Connections
- [[.test_preserves_tool_sequence()]] - `rationale_for` [EXTRACTED]
- [[StoredWorkflow]] - `uses` [INFERRED]
- [[WorkflowStep]] - `uses` [INFERRED]
- [[WorkflowStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Workflow_Store