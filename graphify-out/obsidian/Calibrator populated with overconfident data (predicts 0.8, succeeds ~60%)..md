---
source_file: "tests\test_confidence_calibration.py"
type: "rationale"
community: "Confidence Calibration"
location: "L28"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Calibrator populated with overconfident data (predicts 0.8, succeeds ~60%).

## Connections
- [[CalibrationRecord]] - `uses` [INFERRED]
- [[ConfidenceCalibrator]] - `uses` [INFERRED]
- [[overconfident_calibrator()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration