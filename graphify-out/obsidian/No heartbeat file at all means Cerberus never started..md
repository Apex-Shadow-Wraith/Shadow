---
source_file: "tests\test_watchdog.py"
type: "rationale"
community: "Ethical Topics & Watchdog"
location: "L157"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Ethical_Topics_&_Watchdog
---

# No heartbeat file at all means Cerberus never started.

## Connections
- [[.test_missing_heartbeat_file_returns_false()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[CerberusWatchdog]] - `uses` [INFERRED]
- [[HeartbeatWriter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Ethical_Topics_&_Watchdog