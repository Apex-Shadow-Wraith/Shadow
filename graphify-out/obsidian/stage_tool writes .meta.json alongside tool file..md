---
source_file: "tests\test_tool_creator.py"
type: "rationale"
community: "Module Lifecycle"
location: "L202"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Lifecycle
---

# stage_tool writes .meta.json alongside tool file.

## Connections
- [[.test_stage_writes_metadata()]] - `rationale_for` [EXTRACTED]
- [[ToolCandidate]] - `uses` [INFERRED]
- [[ToolCreator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Lifecycle