---
source_file: "tests\test_emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L785"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Emergency_Shutdown
---

# Default thresholds do not include cpu or memory.

## Connections
- [[.test_no_cpu_or_memory_threshold_in_defaults()]] - `rationale_for` [EXTRACTED]
- [[EmergencyShutdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Emergency_Shutdown