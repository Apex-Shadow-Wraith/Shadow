---
source_file: "tests\test_watchdog.py"
type: "code"
community: "Ethical Topics & Watchdog"
location: "L180"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Ethical_Topics_&_Watchdog
---

# TestCerberusWatchdogLockfile

## Connections
- [[.test_clear_lock_removes_lockfile()]] - `method` [EXTRACTED]
- [[.test_clear_lock_safe_when_no_lockfile()]] - `method` [EXTRACTED]
- [[.test_is_locked_returns_false_when_no_lockfile()]] - `method` [EXTRACTED]
- [[.test_is_locked_returns_true_when_lockfile_exists()]] - `method` [EXTRACTED]
- [[.test_on_cerberus_down_creates_lockfile()]] - `method` [EXTRACTED]
- [[.test_on_cerberus_down_lockfile_has_metadata()]] - `method` [EXTRACTED]
- [[.test_on_cerberus_down_sends_telegram()]] - `method` [EXTRACTED]
- [[.test_on_cerberus_down_writes_emergency_log()]] - `method` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[CerberusWatchdog]] - `uses` [INFERRED]
- [[HeartbeatWriter]] - `uses` [INFERRED]
- [[Test lockfile creation, detection, and clearing.]] - `rationale_for` [EXTRACTED]
- [[test_watchdog.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Ethical_Topics_&_Watchdog