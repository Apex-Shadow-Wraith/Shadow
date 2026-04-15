---
source_file: "tests\test_lora_manager.py"
type: "rationale"
community: "Confidence Calibration"
location: "L303"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Default adapters are NOT registered if paths don't exist.

## Connections
- [[.test_known_adapters_skipped_if_missing()]] - `rationale_for` [EXTRACTED]
- [[LoRAAdapter]] - `uses` [INFERRED]
- [[LoRAManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration