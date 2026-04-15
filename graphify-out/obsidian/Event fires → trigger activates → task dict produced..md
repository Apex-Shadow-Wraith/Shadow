---
source_file: "tests\test_proactive_engine.py"
type: "rationale"
community: "Proactive Engine"
location: "L578"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Proactive_Engine
---

# Event fires → trigger activates → task dict produced.

## Connections
- [[.test_full_event_flow()]] - `rationale_for` [EXTRACTED]
- [[ProactiveEngine]] - `uses` [INFERRED]
- [[ProactiveTrigger]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Proactive_Engine