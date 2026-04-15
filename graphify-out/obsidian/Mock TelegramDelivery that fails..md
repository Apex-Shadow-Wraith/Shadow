---
source_file: "tests\test_emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L66"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Emergency_Shutdown
---

# Mock TelegramDelivery that fails.

## Connections
- [[EmergencyShutdown]] - `uses` [INFERRED]
- [[mock_telegram_fail()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Emergency_Shutdown