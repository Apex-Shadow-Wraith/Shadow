---
source_file: "tests\test_confidence_calibration.py"
type: "rationale"
community: "Confidence Calibration"
location: "L40"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Calibrator populated with underconfident data (predicts 0.3, succeeds ~70%).

## Connections
- [[CalibrationRecord]] - `uses` [INFERRED]
- [[ConfidenceCalibrator]] - `uses` [INFERRED]
- [[underconfident_calibrator()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration