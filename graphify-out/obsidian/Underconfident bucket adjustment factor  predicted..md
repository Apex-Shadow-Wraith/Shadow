---
source_file: "tests\test_confidence_calibration.py"
type: "rationale"
community: "Confidence Calibration"
location: "L143"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Underconfident bucket: adjustment factor > predicted.

## Connections
- [[.test_underconfident_adjustment_raises()]] - `rationale_for` [EXTRACTED]
- [[CalibrationRecord]] - `uses` [INFERRED]
- [[ConfidenceCalibrator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration