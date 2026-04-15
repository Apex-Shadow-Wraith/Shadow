---
source_file: "tests\test_emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L263"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Emergency_Shutdown
---

# CPU 99% AND memory 95% simultaneously must NOT trigger shutdown.

## Connections
- [[.test_cpu_99_and_memory_95_simultaneously_no_shutdown()]] - `rationale_for` [EXTRACTED]
- [[EmergencyShutdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Emergency_Shutdown