---
source_file: "tests\test_watchdog.py"
type: "rationale"
community: "Ethical Topics & Watchdog"
location: "L202"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Ethical_Topics_&_Watchdog
---

# on_cerberus_down must write to the emergency shutdown log.

## Connections
- [[.test_on_cerberus_down_writes_emergency_log()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[CerberusWatchdog]] - `uses` [INFERRED]
- [[HeartbeatWriter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Ethical_Topics_&_Watchdog