---
source_file: "tests\test_predictive_escalation.py"
type: "rationale"
community: "Predictive Escalation"
location: "L274"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Predictive_Escalation
---

# get_prediction_accuracy returns zeros with no data.

## Connections
- [[.test_empty_accuracy()]] - `rationale_for` [EXTRACTED]
- [[EscalationPrediction]] - `uses` [INFERRED]
- [[PredictiveEscalation]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Predictive_Escalation