---
source_file: "tests\test_emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L90"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Emergency_Shutdown
---

# Normal Shadow operations must return None (no shutdown).

## Connections
- [[EmergencyShutdown]] - `uses` [INFERRED]
- [[TestSafeOperationsNoShutdown]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Emergency_Shutdown