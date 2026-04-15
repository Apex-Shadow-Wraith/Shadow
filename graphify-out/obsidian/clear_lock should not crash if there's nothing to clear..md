---
source_file: "tests\test_watchdog.py"
type: "rationale"
community: "Ethical Topics & Watchdog"
location: "L242"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Ethical_Topics_&_Watchdog
---

# clear_lock should not crash if there's nothing to clear.

## Connections
- [[.test_clear_lock_safe_when_no_lockfile()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[CerberusWatchdog]] - `uses` [INFERRED]
- [[HeartbeatWriter]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Ethical_Topics_&_Watchdog