---
source_file: "tests\test_watchdog.py"
type: "rationale"
community: "Ethical Topics & Watchdog"
location: "L161"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Ethical_Topics_&_Watchdog
---

# A corrupted heartbeat file should be treated as failure.

## Connections
- [[.test_corrupted_heartbeat_returns_false()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[CerberusWatchdog]] - `uses` [INFERRED]
- [[HeartbeatWriter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Ethical_Topics_&_Watchdog