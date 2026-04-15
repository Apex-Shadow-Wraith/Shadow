---
source_file: "tests\test_tool_creator.py"
type: "rationale"
community: "Module Lifecycle"
location: "L335"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Lifecycle
---

# Reject unknown candidate_id → False.

## Connections
- [[.test_reject_nonexistent_returns_false()]] - `rationale_for` [EXTRACTED]
- [[ToolCandidate]] - `uses` [INFERRED]
- [[ToolCreator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Lifecycle