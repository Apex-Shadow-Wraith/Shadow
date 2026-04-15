---
source_file: "tests\test_confidence_calibration.py"
type: "rationale"
community: "Confidence Calibration"
location: "L69"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Record stores a prediction-outcome pair in SQLite.

## Connections
- [[.test_record_stores_pair()]] - `rationale_for` [EXTRACTED]
- [[CalibrationRecord]] - `uses` [INFERRED]
- [[ConfidenceCalibrator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration