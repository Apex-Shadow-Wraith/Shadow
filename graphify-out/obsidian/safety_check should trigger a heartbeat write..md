---
source_file: "tests\test_watchdog.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L295"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# safety_check should trigger a heartbeat write.

## Connections
- [[.test_heartbeat_updates_on_safety_check()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[CerberusWatchdog]] - `uses` [INFERRED]
- [[HeartbeatWriter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API