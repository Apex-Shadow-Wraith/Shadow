---
source_file: "tests\test_tool_creator.py"
type: "rationale"
community: "Module Lifecycle"
location: "L297"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Lifecycle
---

# No notifier → tool staged, no crash.

## Connections
- [[.test_no_notifier_stages_without_notification()]] - `rationale_for` [EXTRACTED]
- [[ToolCandidate]] - `uses` [INFERRED]
- [[ToolCreator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Lifecycle