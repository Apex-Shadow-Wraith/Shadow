---
source_file: "modules\shadow\confidence_calibration.py"
type: "code"
community: "Confidence Calibration"
location: "L24"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# CalibrationRecord

## Connections
- [[A single prediction-outcome pair.]] - `rationale_for` [EXTRACTED]
- [[All failures calibration reflects that.]] - `uses` [INFERRED]
- [[All successes calibration reflects that.]] - `uses` [INFERRED]
- [[Calibrator populated with overconfident data (predicts 0.8, succeeds ~60%).]] - `uses` [INFERRED]
- [[Calibrator populated with underconfident data (predicts 0.3, succeeds ~70%).]] - `uses` [INFERRED]
- [[Calibrator populated with well-calibrated data.]] - `uses` [INFERRED]
- [[Create a calibrator with a temp database.]] - `uses` [INFERRED]
- [[Different modules can have different calibration.]] - `uses` [INFERRED]
- [[Empty DB returns a valid empty curve.]] - `uses` [INFERRED]
- [[Empty database returns meaningful report.]] - `uses` [INFERRED]
- [[Insufficient data returns predicted_confidence unchanged.]] - `uses` [INFERRED]
- [[Multiple records accumulate correctly.]] - `uses` [INFERRED]
- [[Overconfident bucket adjustment factor  predicted.]] - `uses` [INFERRED]
- [[Overconfident pattern detected.]] - `uses` [INFERRED]
- [[Record stores a prediction-outcome pair in SQLite.]] - `uses` [INFERRED]
- [[SQLite DB created on init.]] - `uses` [INFERRED]
- [[Single record valid but insufficient data for adjustment.]] - `uses` [INFERRED]
- [[TestAdjustment]] - `uses` [INFERRED]
- [[TestCalibrationCurve]] - `uses` [INFERRED]
- [[TestEdgeCases_2]] - `uses` [INFERRED]
- [[TestFiltering]] - `uses` [INFERRED]
- [[TestRecording]] - `uses` [INFERRED]
- [[TestReporting]] - `uses` [INFERRED]
- [[Tests for the Confidence Calibration Curve module.]] - `uses` [INFERRED]
- [[Underconfident bucket adjustment factor  predicted.]] - `uses` [INFERRED]
- [[Underconfident pattern detected.]] - `uses` [INFERRED]
- [[Well-calibrated pattern detected.]] - `uses` [INFERRED]
- [[Well-calibrated calibrate returns value close to input.]] - `uses` [INFERRED]
- [[calibrate applies adjustment and clamps to 0.0-1.0.]] - `uses` [INFERRED]
- [[confidence_calibration.py]] - `contains` [EXTRACTED]
- [[get_calibration_by_type filters by module.]] - `uses` [INFERRED]
- [[get_calibration_by_type filters by task_type.]] - `uses` [INFERRED]
- [[get_calibration_curve buckets records correctly.]] - `uses` [INFERRED]
- [[get_calibration_report returns a readable string.]] - `uses` [INFERRED]
- [[get_monthly_trend returns monthly data.]] - `uses` [INFERRED]
- [[overall_calibration_error calculated correctly.]] - `uses` [INFERRED]
- [[should_recalibrate True when error  0.15.]] - `uses` [INFERRED]
- [[should_recalibrate True when many new records since last check.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Confidence_Calibration