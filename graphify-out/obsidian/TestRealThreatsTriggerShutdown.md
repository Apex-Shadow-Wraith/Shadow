---
source_file: "tests\test_emergency_shutdown.py"
type: "code"
community: "Emergency Shutdown"
location: "L342"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Emergency_Shutdown
---

# TestRealThreatsTriggerShutdown

## Connections
- [[.test_49_retries_below_threshold_safe()]] - `method` [EXTRACTED]
- [[.test_cerberus_config_modification()]] - `method` [EXTRACTED]
- [[.test_cerberus_self_modification_any_cerberus_file()]] - `method` [EXTRACTED]
- [[.test_cerberus_self_modification_cerberus_py()]] - `method` [EXTRACTED]
- [[.test_cerberus_self_modification_windows_paths()]] - `method` [EXTRACTED]
- [[.test_disk_above_500mb_safe()]] - `method` [EXTRACTED]
- [[.test_disk_below_500mb()]] - `method` [EXTRACTED]
- [[.test_external_actions_outside_window_safe()]] - `method` [EXTRACTED]
- [[.test_fewer_external_actions_safe()]] - `method` [EXTRACTED]
- [[.test_infinite_loop_50_retries_in_60s()]] - `method` [EXTRACTED]
- [[.test_injection_below_threshold_is_safe()]] - `method` [EXTRACTED]
- [[.test_injection_detected_but_blocked_is_safe()]] - `method` [EXTRACTED]
- [[.test_injection_executed_triggers_shutdown()]] - `method` [EXTRACTED]
- [[.test_normal_12_retry_cycle_is_safe()]] - `method` [EXTRACTED]
- [[.test_omen_editing_non_cerberus_is_safe()]] - `method` [EXTRACTED]
- [[.test_unauthorized_external_burst()]] - `method` [EXTRACTED]
- [[EmergencyShutdown]] - `uses` [INFERRED]
- [[Genuinely dangerous situations must return a trigger reason.]] - `rationale_for` [EXTRACTED]
- [[test_emergency_shutdown.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Emergency_Shutdown