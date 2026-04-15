---
source_file: "tests\test_emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L343"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Emergency_Shutdown
---

# Genuinely dangerous situations must return a trigger reason.

## Connections
- [[EmergencyShutdown]] - `uses` [INFERRED]
- [[TestRealThreatsTriggerShutdown]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Emergency_Shutdown