---
source_file: "tests\test_tool_creator.py"
type: "rationale"
community: "Module Lifecycle"
location: "L194"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Lifecycle
---

# stage_tool writes .py file to staging directory.

## Connections
- [[.test_stage_writes_to_directory()]] - `rationale_for` [EXTRACTED]
- [[ToolCandidate]] - `uses` [INFERRED]
- [[ToolCreator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Lifecycle