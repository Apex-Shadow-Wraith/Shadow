---
source_file: "tests\test_lora_manager.py"
type: "rationale"
community: "Confidence Calibration"
location: "L140"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Adapters with negative improvement should be skipped.

## Connections
- [[.test_adapter_with_negative_improvement_skipped()]] - `rationale_for` [EXTRACTED]
- [[LoRAAdapter]] - `uses` [INFERRED]
- [[LoRAManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration