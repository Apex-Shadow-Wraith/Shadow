---
source_file: "tests\test_lora_tracker.py"
type: "rationale"
community: "Confidence Calibration"
location: "L117"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Adapter that was good but is getting worse needs retrain.

## Connections
- [[.test_needs_retrain_declining_performance()]] - `rationale_for` [EXTRACTED]
- [[AdapterProfile]] - `uses` [INFERRED]
- [[LoRAPerformanceTracker]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration