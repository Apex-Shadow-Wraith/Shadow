---
source_file: "tests\test_emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L718"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Emergency_Shutdown
---

# Verify _is_safe_operation whitelist covers all required tools.

## Connections
- [[EmergencyShutdown]] - `uses` [INFERRED]
- [[TestSafeOperationWhitelist]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Emergency_Shutdown