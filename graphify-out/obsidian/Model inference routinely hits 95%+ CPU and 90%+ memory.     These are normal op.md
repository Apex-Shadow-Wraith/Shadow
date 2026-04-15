---
source_file: "tests\test_emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L248"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Emergency_Shutdown
---

# Model inference routinely hits 95%+ CPU and 90%+ memory.     These are normal op

## Connections
- [[EmergencyShutdown]] - `uses` [INFERRED]
- [[TestHighResourceUsageNeverTriggersShutdown]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Emergency_Shutdown