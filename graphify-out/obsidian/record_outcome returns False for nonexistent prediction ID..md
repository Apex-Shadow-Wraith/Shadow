---
source_file: "tests\test_predictive_escalation.py"
type: "rationale"
community: "Predictive Escalation"
location: "L251"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Predictive_Escalation
---

# record_outcome returns False for nonexistent prediction ID.

## Connections
- [[.test_record_outcome_nonexistent_id()]] - `rationale_for` [EXTRACTED]
- [[EscalationPrediction]] - `uses` [INFERRED]
- [[PredictiveEscalation]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Predictive_Escalation