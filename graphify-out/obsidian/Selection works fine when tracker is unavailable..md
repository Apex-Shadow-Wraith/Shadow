---
source_file: "tests\test_lora_manager.py"
type: "rationale"
community: "Confidence Calibration"
location: "L346"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Selection works fine when tracker is unavailable.

## Connections
- [[.test_graceful_without_tracker()]] - `rationale_for` [EXTRACTED]
- [[LoRAAdapter]] - `uses` [INFERRED]
- [[LoRAManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration