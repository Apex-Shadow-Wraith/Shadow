---
source_file: "tests\test_tool_creator.py"
type: "rationale"
community: "Module Lifecycle"
location: "L211"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Lifecycle
---

# stage_tool sends Telegram notification via notifier.

## Connections
- [[.test_stage_sends_notification()]] - `rationale_for` [EXTRACTED]
- [[ToolCandidate]] - `uses` [INFERRED]
- [[ToolCreator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Lifecycle