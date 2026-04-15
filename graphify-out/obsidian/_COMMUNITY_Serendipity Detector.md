---
type: community
cohesion: 0.05
members: 93
---

# Serendipity Detector

**Cohesion:** 0.05 - loosely connected
**Members:** 93 nodes

## Members
- [[.__init__()_34]] - code - modules\morpheus\serendipity_detector.py
- [[._heuristic_score()]] - code - modules\morpheus\serendipity_detector.py
- [[._make_finding()]] - code - tests\test_serendipity_detector.py
- [[.capture_baseline_metrics()]] - code - modules\morpheus\serendipity_detector.py
- [[.check_for_serendipity()]] - code - modules\morpheus\serendipity_detector.py
- [[.compare_metrics()]] - code - modules\morpheus\serendipity_detector.py
- [[.confirm_finding()]] - code - modules\morpheus\serendipity_detector.py
- [[.dismiss_finding()]] - code - modules\morpheus\serendipity_detector.py
- [[.get_findings()]] - code - modules\morpheus\serendipity_detector.py
- [[.get_serendipity_stats()]] - code - modules\morpheus\serendipity_detector.py
- [[.queue_for_investigation()]] - code - modules\morpheus\serendipity_detector.py
- [[.test_capture_baseline_no_benchmark_uses_heuristic()]] - code - tests\test_serendipity_detector.py
- [[.test_capture_baseline_returns_valid_snapshot()]] - code - tests\test_serendipity_detector.py
- [[.test_compare_metrics_identifies_improvements()]] - code - tests\test_serendipity_detector.py
- [[.test_compare_metrics_regression_not_reported()]] - code - tests\test_serendipity_detector.py
- [[.test_confirm_finding_stores_in_grimoire()]] - code - tests\test_serendipity_detector.py
- [[.test_confirm_nonexistent_finding()]] - code - tests\test_serendipity_detector.py
- [[.test_dismiss_finding_marks_false_positive()]] - code - tests\test_serendipity_detector.py
- [[.test_dismiss_nonexistent_finding()]] - code - tests\test_serendipity_detector.py
- [[.test_empty_metrics_no_findings()]] - code - tests\test_serendipity_detector.py
- [[.test_get_findings_filters_by_status()]] - code - tests\test_serendipity_detector.py
- [[.test_graceful_when_experiment_store_unavailable()]] - code - tests\test_serendipity_detector.py
- [[.test_graceful_when_grimoire_unavailable()_1]] - code - tests\test_serendipity_detector.py
- [[.test_improvement_in_non_target_domain_detected()]] - code - tests\test_serendipity_detector.py
- [[.test_improvement_in_target_domain_not_serendipitous()]] - code - tests\test_serendipity_detector.py
- [[.test_multiple_domains_improved()]] - code - tests\test_serendipity_detector.py
- [[.test_no_benchmark_fn_uses_heuristic()]] - code - tests\test_serendipity_detector.py
- [[.test_no_improvements_empty_list()]] - code - tests\test_serendipity_detector.py
- [[.test_queue_for_investigation_creates_experiment()]] - code - tests\test_serendipity_detector.py
- [[.test_same_metrics_no_findings()]] - code - tests\test_serendipity_detector.py
- [[.test_stats_returns_accurate_counts()]] - code - tests\test_serendipity_detector.py
- [[.test_threshold_above_detected()]] - code - tests\test_serendipity_detector.py
- [[.test_threshold_below_not_detected()]] - code - tests\test_serendipity_detector.py
- [[4% improvement (below 5% threshold) → not detected.]] - rationale - tests\test_serendipity_detector.py
- [[6% improvement (above 5% threshold) → detected.]] - rationale - tests\test_serendipity_detector.py
- [[A serendipitous discovery from a failed experiment.]] - rationale - modules\morpheus\serendipity_detector.py
- [[Add a finding to the investigation queue.          If experiment_store is availa]] - rationale - modules\morpheus\serendipity_detector.py
- [[Basic detector with no dependencies.]] - rationale - tests\test_serendipity_detector.py
- [[Capture current performance metrics before an experiment runs.          Args]] - rationale - modules\morpheus\serendipity_detector.py
- [[Compare prepost metrics across all domains after a failed experiment.]] - rationale - modules\morpheus\serendipity_detector.py
- [[Compare two metric snapshots and return significant improvements.          Args]] - rationale - modules\morpheus\serendipity_detector.py
- [[Confirming a finding that doesn't exist returns False.]] - rationale - tests\test_serendipity_detector.py
- [[Detects unexpected improvements from failed Morpheus experiments.      After a f]] - rationale - modules\morpheus\serendipity_detector.py
- [[Dismissing a finding that doesn't exist returns False.]] - rationale - tests\test_serendipity_detector.py
- [[Empty metrics → no findings.]] - rationale - tests\test_serendipity_detector.py
- [[Generate a heuristic score for a domain without a benchmark function.          U]] - rationale - modules\morpheus\serendipity_detector.py
- [[Improvement in non-target domain → finding detected.]] - rationale - tests\test_serendipity_detector.py
- [[Improvement in target domain → NOT serendipitous.]] - rationale - tests\test_serendipity_detector.py
- [[Mark a finding as confirmed after investigation validates it.          Stores co]] - rationale - modules\morpheus\serendipity_detector.py
- [[Mark a finding as false_positive with an optional reason.          The finding i]] - rationale - modules\morpheus\serendipity_detector.py
- [[Mock Grimoire module._1]] - rationale - tests\test_serendipity_detector.py
- [[Mock benchmark function.]] - rationale - tests\test_serendipity_detector.py
- [[Multiple non-target domains improved → multiple findings.]] - rationale - tests\test_serendipity_detector.py
- [[No benchmark_fn → uses heuristic comparison.]] - rationale - tests\test_serendipity_detector.py
- [[No improvements → empty list.]] - rationale - tests\test_serendipity_detector.py
- [[Post-experiment metrics with unexpected research improvement.]] - rationale - tests\test_serendipity_detector.py
- [[Pre-experiment baseline metrics.]] - rationale - tests\test_serendipity_detector.py
- [[Regression (worse score) not reported as improvement.]] - rationale - tests\test_serendipity_detector.py
- [[Return aggregate statistics about serendipity findings.          Returns]] - rationale - modules\morpheus\serendipity_detector.py
- [[Return serendipity findings, optionally filtered by status.          Args]] - rationale - modules\morpheus\serendipity_detector.py
- [[Same metrics prepost → no findings.]] - rationale - tests\test_serendipity_detector.py
- [[Sample failed experiment dict.]] - rationale - tests\test_serendipity_detector.py
- [[SerendipityDetector]] - code - modules\morpheus\serendipity_detector.py
- [[SerendipityDetector — Unexpected Discovery Detection for Failed Experiments ====]] - rationale - modules\morpheus\serendipity_detector.py
- [[SerendipityFinding]] - code - modules\morpheus\serendipity_detector.py
- [[TestCheckForSerendipity]] - code - tests\test_serendipity_detector.py
- [[TestEdgeCases_20]] - code - tests\test_serendipity_detector.py
- [[TestInvestigation]] - code - tests\test_serendipity_detector.py
- [[TestMetrics]] - code - tests\test_serendipity_detector.py
- [[TestStats_2]] - code - tests\test_serendipity_detector.py
- [[Tests for SerendipityDetector — Unexpected Discovery Detection =================]] - rationale - tests\test_serendipity_detector.py
- [[Tests for capture_baseline_metrics and compare_metrics.]] - rationale - tests\test_serendipity_detector.py
- [[Tests for check_for_serendipity method.]] - rationale - tests\test_serendipity_detector.py
- [[Tests for get_serendipity_stats.]] - rationale - tests\test_serendipity_detector.py
- [[Tests for queue_for_investigation, confirm, dismiss.]] - rationale - tests\test_serendipity_detector.py
- [[Without benchmark_fn, uses heuristic scoring.]] - rationale - tests\test_serendipity_detector.py
- [[capture_baseline_metrics returns valid snapshot with scores.]] - rationale - tests\test_serendipity_detector.py
- [[compare_metrics correctly identifies improvements above threshold.]] - rationale - tests\test_serendipity_detector.py
- [[confirm_finding stores in Grimoire.]] - rationale - tests\test_serendipity_detector.py
- [[confirm_finding works without Grimoire.]] - rationale - tests\test_serendipity_detector.py
- [[detector()_2]] - code - tests\test_serendipity_detector.py
- [[dismiss_finding marks as false_positive.]] - rationale - tests\test_serendipity_detector.py
- [[get_findings filters by status correctly.]] - rationale - tests\test_serendipity_detector.py
- [[get_serendipity_stats returns accurate counts.]] - rationale - tests\test_serendipity_detector.py
- [[mock_benchmark()]] - code - tests\test_serendipity_detector.py
- [[mock_grimoire()_14]] - code - tests\test_serendipity_detector.py
- [[post_metrics_with_serendipity()]] - code - tests\test_serendipity_detector.py
- [[pre_metrics()]] - code - tests\test_serendipity_detector.py
- [[queue_for_investigation creates experiment in store.]] - rationale - tests\test_serendipity_detector.py
- [[queue_for_investigation works without experiment_store.]] - rationale - tests\test_serendipity_detector.py
- [[sample_experiment()]] - code - tests\test_serendipity_detector.py
- [[serendipity_detector.py]] - code - modules\morpheus\serendipity_detector.py
- [[test_serendipity_detector.py]] - code - tests\test_serendipity_detector.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Serendipity_Detector
SORT file.name ASC
```

## Connections to other communities
- 1 edge to [[_COMMUNITY_Experiment Store]]
- 1 edge to [[_COMMUNITY_Workflow Store]]

## Top bridge nodes
- [[.confirm_finding()]] - degree 6, connects to 1 community
- [[.queue_for_investigation()]] - degree 5, connects to 1 community