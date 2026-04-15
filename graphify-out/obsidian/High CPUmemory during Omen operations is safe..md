---
source_file: "tests\test_emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L298"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Emergency_Shutdown
---

# High CPU/memory during Omen operations is safe.

## Connections
- [[.test_high_resources_with_safe_omen_tools()]] - `rationale_for` [EXTRACTED]
- [[EmergencyShutdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Emergency_Shutdown