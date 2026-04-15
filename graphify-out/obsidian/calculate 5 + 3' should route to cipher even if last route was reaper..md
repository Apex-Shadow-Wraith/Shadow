---
source_file: "tests\test_contextual_routing.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L135"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# calculate 5 + 3' should route to cipher even if last route was reaper.

## Connections
- [[.test_math_keyword_ignores_last_route()]] - `rationale_for` [EXTRACTED]
- [[BrainType]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[TaskClassification]] - `uses` [INFERRED]
- [[TaskType]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API