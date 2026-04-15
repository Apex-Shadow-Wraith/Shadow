---
source_file: "modules\morpheus\serendipity_detector.py"
type: "code"
community: "Serendipity Detector"
location: "L40"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Serendipity_Detector
---

# SerendipityDetector

## Connections
- [[.__init__()_34]] - `method` [EXTRACTED]
- [[._heuristic_score()]] - `method` [EXTRACTED]
- [[.capture_baseline_metrics()]] - `method` [EXTRACTED]
- [[.check_for_serendipity()]] - `method` [EXTRACTED]
- [[.compare_metrics()]] - `method` [EXTRACTED]
- [[.confirm_finding()]] - `method` [EXTRACTED]
- [[.dismiss_finding()]] - `method` [EXTRACTED]
- [[.get_findings()]] - `method` [EXTRACTED]
- [[.get_serendipity_stats()]] - `method` [EXTRACTED]
- [[.queue_for_investigation()]] - `method` [EXTRACTED]
- [[.test_capture_baseline_no_benchmark_uses_heuristic()]] - `calls` [INFERRED]
- [[.test_capture_baseline_returns_valid_snapshot()]] - `calls` [INFERRED]
- [[.test_confirm_finding_stores_in_grimoire()]] - `calls` [INFERRED]
- [[.test_dismiss_finding_marks_false_positive()]] - `calls` [INFERRED]
- [[.test_get_findings_filters_by_status()]] - `calls` [INFERRED]
- [[.test_graceful_when_experiment_store_unavailable()]] - `calls` [INFERRED]
- [[.test_graceful_when_grimoire_unavailable()_1]] - `calls` [INFERRED]
- [[.test_no_benchmark_fn_uses_heuristic()]] - `calls` [INFERRED]
- [[.test_queue_for_investigation_creates_experiment()]] - `calls` [INFERRED]
- [[.test_stats_returns_accurate_counts()]] - `calls` [INFERRED]
- [[4% improvement (below 5% threshold) → not detected.]] - `uses` [INFERRED]
- [[6% improvement (above 5% threshold) → detected.]] - `uses` [INFERRED]
- [[Basic detector with no dependencies.]] - `uses` [INFERRED]
- [[Confirming a finding that doesn't exist returns False.]] - `uses` [INFERRED]
- [[Detects unexpected improvements from failed Morpheus experiments.      After a f]] - `rationale_for` [EXTRACTED]
- [[Dismissing a finding that doesn't exist returns False.]] - `uses` [INFERRED]
- [[Empty metrics → no findings.]] - `uses` [INFERRED]
- [[Improvement in non-target domain → finding detected.]] - `uses` [INFERRED]
- [[Improvement in target domain → NOT serendipitous.]] - `uses` [INFERRED]
- [[Mock Grimoire module._1]] - `uses` [INFERRED]
- [[Mock benchmark function.]] - `uses` [INFERRED]
- [[Multiple non-target domains improved → multiple findings.]] - `uses` [INFERRED]
- [[No benchmark_fn → uses heuristic comparison.]] - `uses` [INFERRED]
- [[No improvements → empty list.]] - `uses` [INFERRED]
- [[Post-experiment metrics with unexpected research improvement.]] - `uses` [INFERRED]
- [[Pre-experiment baseline metrics.]] - `uses` [INFERRED]
- [[Regression (worse score) not reported as improvement.]] - `uses` [INFERRED]
- [[Same metrics prepost → no findings.]] - `uses` [INFERRED]
- [[Sample failed experiment dict.]] - `uses` [INFERRED]
- [[TestCheckForSerendipity]] - `uses` [INFERRED]
- [[TestEdgeCases_20]] - `uses` [INFERRED]
- [[TestInvestigation]] - `uses` [INFERRED]
- [[TestMetrics]] - `uses` [INFERRED]
- [[TestStats_2]] - `uses` [INFERRED]
- [[Tests for SerendipityDetector — Unexpected Discovery Detection =================]] - `uses` [INFERRED]
- [[Tests for capture_baseline_metrics and compare_metrics.]] - `uses` [INFERRED]
- [[Tests for check_for_serendipity method.]] - `uses` [INFERRED]
- [[Tests for get_serendipity_stats.]] - `uses` [INFERRED]
- [[Tests for queue_for_investigation, confirm, dismiss.]] - `uses` [INFERRED]
- [[Without benchmark_fn, uses heuristic scoring.]] - `uses` [INFERRED]
- [[capture_baseline_metrics returns valid snapshot with scores.]] - `uses` [INFERRED]
- [[compare_metrics correctly identifies improvements above threshold.]] - `uses` [INFERRED]
- [[confirm_finding stores in Grimoire.]] - `uses` [INFERRED]
- [[confirm_finding works without Grimoire.]] - `uses` [INFERRED]
- [[detector()_2]] - `calls` [INFERRED]
- [[dismiss_finding marks as false_positive.]] - `uses` [INFERRED]
- [[get_findings filters by status correctly.]] - `uses` [INFERRED]
- [[get_serendipity_stats returns accurate counts.]] - `uses` [INFERRED]
- [[queue_for_investigation creates experiment in store.]] - `uses` [INFERRED]
- [[queue_for_investigation works without experiment_store.]] - `uses` [INFERRED]
- [[serendipity_detector.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Serendipity_Detector