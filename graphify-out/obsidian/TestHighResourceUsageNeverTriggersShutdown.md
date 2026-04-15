---
source_file: "tests\test_emergency_shutdown.py"
type: "code"
community: "Emergency Shutdown"
location: "L247"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Emergency_Shutdown
---

# TestHighResourceUsageNeverTriggersShutdown

## Connections
- [[.test_cpu_100_percent_no_shutdown()]] - `method` [EXTRACTED]
- [[.test_cpu_99_and_memory_95_simultaneously_no_shutdown()]] - `method` [EXTRACTED]
- [[.test_cpu_99_percent_no_shutdown()]] - `method` [EXTRACTED]
- [[.test_cpu_and_memory_maxed_with_model_inference_no_shutdown()]] - `method` [EXTRACTED]
- [[.test_high_resources_with_safe_grimoire_tools()]] - `method` [EXTRACTED]
- [[.test_high_resources_with_safe_omen_tools()]] - `method` [EXTRACTED]
- [[.test_high_resources_with_safe_reaper_tools()]] - `method` [EXTRACTED]
- [[.test_memory_95_percent_no_shutdown()]] - `method` [EXTRACTED]
- [[.test_memory_99_percent_no_shutdown()]] - `method` [EXTRACTED]
- [[.test_no_runaway_process_trigger_exists()]] - `method` [EXTRACTED]
- [[EmergencyShutdown]] - `uses` [INFERRED]
- [[Model inference routinely hits 95%+ CPU and 90%+ memory.     These are normal op]] - `rationale_for` [EXTRACTED]
- [[test_emergency_shutdown.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Emergency_Shutdown