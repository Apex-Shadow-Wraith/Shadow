---
source_file: "tests\test_predictive_escalation.py"
type: "rationale"
community: "Predictive Escalation"
location: "L238"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Predictive_Escalation
---

# record_outcome updates the prediction's actual_escalated field.

## Connections
- [[.test_record_outcome_stores_result()]] - `rationale_for` [EXTRACTED]
- [[EscalationPrediction]] - `uses` [INFERRED]
- [[PredictiveEscalation]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Predictive_Escalation