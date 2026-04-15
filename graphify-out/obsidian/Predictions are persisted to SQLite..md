---
source_file: "tests\test_predictive_escalation.py"
type: "rationale"
community: "Predictive Escalation"
location: "L135"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Predictive_Escalation
---

# Predictions are persisted to SQLite.

## Connections
- [[.test_prediction_stored_in_db()]] - `rationale_for` [EXTRACTED]
- [[EscalationPrediction]] - `uses` [INFERRED]
- [[PredictiveEscalation]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Predictive_Escalation