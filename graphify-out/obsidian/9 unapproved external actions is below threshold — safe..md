---
source_file: "tests\test_emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L483"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Emergency_Shutdown
---

# 9 unapproved external actions is below threshold — safe.

## Connections
- [[.test_fewer_external_actions_safe()]] - `rationale_for` [EXTRACTED]
- [[EmergencyShutdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Emergency_Shutdown