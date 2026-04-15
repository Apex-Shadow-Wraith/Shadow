---
source_file: "modules\shadow\predictive_escalation.py"
type: "code"
community: "Predictive Escalation"
location: "L16"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Predictive_Escalation
---

# EscalationPrediction

## Connections
- [[.predict()]] - `calls` [EXTRACTED]
- [[.test_high_probability_aggressive_preparation()]] - `calls` [INFERRED]
- [[.test_low_probability_minimal_preparation()]] - `calls` [INFERRED]
- [[.test_medium_probability_moderate_preparation()]] - `calls` [INFERRED]
- [[Batch predictions are sorted by probability descending.]] - `uses` [INFERRED]
- [[CUDA task with no CUDA entries → elevated probability.]] - `uses` [INFERRED]
- [[Can close and reopen without data loss.]] - `uses` [INFERRED]
- [[Create a PredictiveEscalation instance with no Grimoire.]] - `uses` [INFERRED]
- [[Create a PredictiveEscalation with a mock Grimoire.]] - `uses` [INFERRED]
- [[Create a mock Grimoire with recall method.]] - `uses` [INFERRED]
- [[Empty task list returns empty prediction list.]] - `uses` [INFERRED]
- [[Empty task returns valid prediction with defaults.]] - `uses` [INFERRED]
- [[False negative rate is calculated correctly.]] - `uses` [INFERRED]
- [[False positive rate is calculated correctly.]] - `uses` [INFERRED]
- [[Graceful when grimoire is None.]] - `uses` [INFERRED]
- [[Handles Grimoire exceptions gracefully.]] - `uses` [INFERRED]
- [[Helper to seed predictions with outcomes.]] - `uses` [INFERRED]
- [[High complexity + no Grimoire depth → high probability.]] - `uses` [INFERRED]
- [[High probability → aggressive preparation with Apex queue.]] - `uses` [INFERRED]
- [[Longer task descriptions score higher complexity.]] - `uses` [INFERRED]
- [[Low probability → minimal preparation.]] - `uses` [INFERRED]
- [[Medium probability → moderate preparation.]] - `uses` [INFERRED]
- [[Multi-step keywords increase complexity score.]] - `uses` [INFERRED]
- [[None task is handled gracefully.]] - `uses` [INFERRED]
- [[Prediction of whether a task will need Apex escalation.]] - `rationale_for` [EXTRACTED]
- [[Predictions are persisted to SQLite.]] - `uses` [INFERRED]
- [[Probability is always clamped to 0.0-1.0.]] - `uses` [INFERRED]
- [[Return a temporary database path.]] - `uses` [INFERRED]
- [[Returns a valid EscalationPrediction with all fields populated.]] - `uses` [INFERRED]
- [[SQLite DB file is created on initialization.]] - `uses` [INFERRED]
- [[Simple task + deep Grimoire → low probability.]] - `uses` [INFERRED]
- [[TestAccuracyTracking]] - `uses` [INFERRED]
- [[TestBatchPredictions]] - `uses` [INFERRED]
- [[TestEdgeCases_14]] - `uses` [INFERRED]
- [[TestForecasting]] - `uses` [INFERRED]
- [[TestInit_1]] - `uses` [INFERRED]
- [[TestPredict]] - `uses` [INFERRED]
- [[TestPreparationActions]] - `uses` [INFERRED]
- [[Tests for Predictive Escalation module.]] - `uses` [INFERRED]
- [[The predictions table is created.]] - `uses` [INFERRED]
- [[Without Grimoire, predictions rely on task complexity signals only.]] - `uses` [INFERRED]
- [[get_cost_forecast handles empty database gracefully.]] - `uses` [INFERRED]
- [[get_cost_forecast returns valid cost projections.]] - `uses` [INFERRED]
- [[get_escalation_forecast filters by specified task types.]] - `uses` [INFERRED]
- [[get_escalation_forecast identifies domains with high escalation rates.]] - `uses` [INFERRED]
- [[get_escalation_forecast recommends knowledge investments for high-escalation dom]] - `uses` [INFERRED]
- [[get_prediction_accuracy returns correct metrics.]] - `uses` [INFERRED]
- [[get_prediction_accuracy returns zeros with no data.]] - `uses` [INFERRED]
- [[predictive_escalation.py]] - `contains` [EXTRACTED]
- [[record_outcome returns False for nonexistent prediction ID.]] - `uses` [INFERRED]
- [[record_outcome updates the prediction's actual_escalated field.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Predictive_Escalation