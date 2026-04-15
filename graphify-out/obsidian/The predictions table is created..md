---
source_file: "tests\test_predictive_escalation.py"
type: "rationale"
community: "Predictive Escalation"
location: "L56"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Predictive_Escalation
---

# The predictions table is created.

## Connections
- [[.test_predictions_table_exists()]] - `rationale_for` [EXTRACTED]
- [[EscalationPrediction]] - `uses` [INFERRED]
- [[PredictiveEscalation]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Predictive_Escalation