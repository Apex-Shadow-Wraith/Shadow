---
source_file: "modules\cerberus\watchdog.py"
type: "code"
community: "Ethical Topics & Watchdog"
location: "L42"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Ethical_Topics_&_Watchdog
---

# HeartbeatWriter

## Connections
- [[.__init__()_11]] - `method` [EXTRACTED]
- [[._heartbeat_loop()]] - `method` [EXTRACTED]
- [[._write_heartbeat()]] - `method` [EXTRACTED]
- [[.increment_checks()]] - `method` [EXTRACTED]
- [[.start()]] - `method` [EXTRACTED]
- [[.stop()]] - `method` [EXTRACTED]
- [[A corrupted heartbeat file should be treated as failure.]] - `uses` [INFERRED]
- [[A heartbeat at 91s should be detected as stale.]] - `uses` [INFERRED]
- [[A heartbeat at exactly 89s should still be considered fresh.]] - `uses` [INFERRED]
- [[A heartbeat older than 90s should be detected as down.]] - `uses` [INFERRED]
- [[A heartbeat written just now should be detected as healthy.]] - `uses` [INFERRED]
- [[Cerberus — Ethics, Safety, and Accountability.]] - `uses` [INFERRED]
- [[Create a CerberusWatchdog with test paths.]] - `uses` [INFERRED]
- [[Create a HeartbeatWriter with fast interval for testing.]] - `uses` [INFERRED]
- [[Each heartbeat should have a unique check ID.]] - `uses` [INFERRED]
- [[Helper to write a heartbeat file for testing.]] - `uses` [INFERRED]
- [[Lockfile should contain structured data about the failure.]] - `uses` [INFERRED]
- [[No heartbeat file at all means Cerberus never started.]] - `uses` [INFERRED]
- [[Provide isolated paths for watchdog testing.]] - `uses` [INFERRED]
- [[Test heartbeat checking.]] - `uses` [INFERRED]
- [[Test lockfile creation, detection, and clearing.]] - `uses` [INFERRED]
- [[Test orchestrator integration (lockfile blocks requests).]] - `uses` [INFERRED]
- [[Test that Cerberus.send_heartbeat() writes correct data.]] - `uses` [INFERRED]
- [[TestCerberusHeartbeatIntegration]] - `uses` [INFERRED]
- [[TestCerberusWatchdogHeartbeat]] - `uses` [INFERRED]
- [[TestCerberusWatchdogLockfile]] - `uses` [INFERRED]
- [[TestCerberusWatchdogOrchestrator]] - `uses` [INFERRED]
- [[TestHeartbeatWriter]] - `uses` [INFERRED]
- [[Tests for Cerberus Watchdog System ===================================== Tests b]] - `uses` [INFERRED]
- [[The orchestrator should refuse all input when locked.]] - `uses` [INFERRED]
- [[Writes periodic heartbeat files for external monitoring.      The heartbeat is a]] - `rationale_for` [EXTRACTED]
- [[clear_lock must remove the lockfile.]] - `uses` [INFERRED]
- [[clear_lock should not crash if there's nothing to clear.]] - `uses` [INFERRED]
- [[heartbeat()]] - `calls` [INFERRED]
- [[is_locked should return False when there's no lockfile.]] - `uses` [INFERRED]
- [[is_locked should return True when the lockfile exists.]] - `uses` [INFERRED]
- [[on_cerberus_down must create the lockfile.]] - `uses` [INFERRED]
- [[on_cerberus_down must write to the emergency shutdown log.]] - `uses` [INFERRED]
- [[on_cerberus_down should attempt to send a Telegram alert.]] - `uses` [INFERRED]
- [[safety_check should trigger a heartbeat write.]] - `uses` [INFERRED]
- [[send_heartbeat should create a heartbeat file with correct fields.]] - `uses` [INFERRED]
- [[watchdog.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Ethical_Topics_&_Watchdog