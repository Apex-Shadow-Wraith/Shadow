---
source_file: "tests\test_watchdog.py"
type: "rationale"
community: "Ethical Topics & Watchdog"
location: "L151"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Ethical_Topics_&_Watchdog
---

# A heartbeat older than 90s should be detected as down.

## Connections
- [[.test_stale_heartbeat_detected_as_down()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[CerberusWatchdog]] - `uses` [INFERRED]
- [[HeartbeatWriter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Ethical_Topics_&_Watchdog