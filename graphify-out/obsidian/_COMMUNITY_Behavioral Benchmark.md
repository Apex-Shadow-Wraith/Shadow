---
type: community
cohesion: 0.05
members: 100
---

# Behavioral Benchmark

**Cohesion:** 0.05 - loosely connected
**Members:** 100 nodes

## Members
- [[.__init__()_53]] - code - modules\shadow\behavioral_benchmark.py
- [[._build_report()]] - code - modules\shadow\behavioral_benchmark.py
- [[._evaluate_business()]] - code - modules\shadow\behavioral_benchmark.py
- [[._evaluate_code()]] - code - modules\shadow\behavioral_benchmark.py
- [[._evaluate_ethics()]] - code - modules\shadow\behavioral_benchmark.py
- [[._evaluate_generic()]] - code - modules\shadow\behavioral_benchmark.py
- [[._evaluate_math()]] - code - modules\shadow\behavioral_benchmark.py
- [[._evaluate_research()]] - code - modules\shadow\behavioral_benchmark.py
- [[._evaluate_routing()]] - code - modules\shadow\behavioral_benchmark.py
- [[._evaluate_security()]] - code - modules\shadow\behavioral_benchmark.py
- [[._keyword_score()]] - code - modules\shadow\behavioral_benchmark.py
- [[._load_previous_report()]] - code - modules\shadow\behavioral_benchmark.py
- [[._store_report()]] - code - modules\shadow\behavioral_benchmark.py
- [[.alert_on_regression()]] - code - modules\shadow\behavioral_benchmark.py
- [[.compare_to_previous()]] - code - modules\shadow\behavioral_benchmark.py
- [[.evaluate_result()]] - code - modules\shadow\behavioral_benchmark.py
- [[.get_trend()]] - code - modules\shadow\behavioral_benchmark.py
- [[.run_full_benchmark()]] - code - modules\shadow\behavioral_benchmark.py
- [[.run_scheduled()]] - code - modules\shadow\behavioral_benchmark.py
- [[.should_freeze_changes()]] - code - modules\shadow\behavioral_benchmark.py
- [[.test_alert_none_comparison()]] - code - tests\test_behavioral_benchmark.py
- [[.test_alert_sends_telegram()]] - code - tests\test_behavioral_benchmark.py
- [[.test_alert_sets_frozen_flag()]] - code - tests\test_behavioral_benchmark.py
- [[.test_all_categories_have_3_plus_tasks()]] - code - tests\test_behavioral_benchmark.py
- [[.test_all_tasks_have_valid_schema()]] - code - tests\test_behavioral_benchmark.py
- [[.test_business_task_structured()]] - code - tests\test_behavioral_benchmark.py
- [[.test_calls_executor_for_each_task()]] - code - tests\test_behavioral_benchmark.py
- [[.test_categories_cover_all_expected()]] - code - tests\test_behavioral_benchmark.py
- [[.test_code_task_invalid_syntax()]] - code - tests\test_behavioral_benchmark.py
- [[.test_code_task_valid_syntax()]] - code - tests\test_behavioral_benchmark.py
- [[.test_detects_improvement()]] - code - tests\test_behavioral_benchmark.py
- [[.test_detects_regression()]] - code - tests\test_behavioral_benchmark.py
- [[.test_empty_executor_all_zeros()]] - code - tests\test_behavioral_benchmark.py
- [[.test_empty_response_scores_zero()]] - code - tests\test_behavioral_benchmark.py
- [[.test_ethics_task_no_nuance()]] - code - tests\test_behavioral_benchmark.py
- [[.test_ethics_task_nuance()]] - code - tests\test_behavioral_benchmark.py
- [[.test_executor_exception_handled()]] - code - tests\test_behavioral_benchmark.py
- [[.test_get_trend_no_grimoire()]] - code - tests\test_behavioral_benchmark.py
- [[.test_get_trend_with_data()]] - code - tests\test_behavioral_benchmark.py
- [[.test_math_task_has_numbers()]] - code - tests\test_behavioral_benchmark.py
- [[.test_no_previous_returns_none()]] - code - tests\test_behavioral_benchmark.py
- [[.test_no_regression_no_freeze()]] - code - tests\test_behavioral_benchmark.py
- [[.test_overall_score_is_category_average()]] - code - tests\test_behavioral_benchmark.py
- [[.test_report_has_all_fields()]] - code - tests\test_behavioral_benchmark.py
- [[.test_research_task_multiple_approaches()]] - code - tests\test_behavioral_benchmark.py
- [[.test_routing_accuracy_check()]] - code - tests\test_behavioral_benchmark.py
- [[.test_routing_fn_called()]] - code - tests\test_behavioral_benchmark.py
- [[.test_run_scheduled_full_pipeline()]] - code - tests\test_behavioral_benchmark.py
- [[.test_security_task_identifies_threats()]] - code - tests\test_behavioral_benchmark.py
- [[.test_should_freeze_default_false()]] - code - tests\test_behavioral_benchmark.py
- [[.test_should_freeze_true_after_regression()]] - code - tests\test_behavioral_benchmark.py
- [[.test_store_no_grimoire_no_error()]] - code - tests\test_behavioral_benchmark.py
- [[.test_store_report_calls_grimoire()]] - code - tests\test_behavioral_benchmark.py
- [[.test_suite_has_20_plus_tasks()]] - code - tests\test_behavioral_benchmark.py
- [[.test_task_ids_unique()]] - code - tests\test_behavioral_benchmark.py
- [[.test_timeout_scores_zero()]] - code - tests\test_behavioral_benchmark.py
- [[Bare benchmark with no Grimoire or Telegram.]] - rationale - tests\test_behavioral_benchmark.py
- [[BehavioralBenchmark]] - code - modules\shadow\behavioral_benchmark.py
- [[Benchmark with mocked Grimoire and Telegram.]] - rationale - tests\test_behavioral_benchmark.py
- [[BenchmarkReport]] - code - modules\shadow\behavioral_benchmark.py
- [[BenchmarkTask]] - code - modules\shadow\behavioral_benchmark.py
- [[Check keyword presence, return (fraction_found, matched_keywords).]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Compare current report to the last stored one.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Comparison between current and previous benchmark runs.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[ComparisonResult]] - code - modules\shadow\behavioral_benchmark.py
- [[Compile TaskResults into a BenchmarkReport.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Evaluation result for a single task.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Fixed benchmark suite measuring Shadow's behavioral quality over time.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Full benchmark run report.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Load the most recent benchmark report from Grimoire.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Nightly Behavioral Benchmark — fixed tasks measuring Shadow's actual quality.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Nightly entry point run, compare, alert, store.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[One fixed benchmark task.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Return score trends over time for Growth Engine  Harbinger briefing.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Returns True if last benchmark showed regression.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Returns a plausible response with lots of keywords.]] - rationale - tests\test_behavioral_benchmark.py
- [[Rule-based evaluation of a single task response.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Run all benchmark tasks and produce a report.          Args             executo]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Send Telegram alert and freeze changes if regression detected.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[Simulates a slow response by manipulating time (we test via duration param).]] - rationale - tests\test_behavioral_benchmark.py
- [[Store a benchmark report in Grimoire.]] - rationale - modules\shadow\behavioral_benchmark.py
- [[TaskResult]] - code - modules\shadow\behavioral_benchmark.py
- [[TestAlerting]] - code - tests\test_behavioral_benchmark.py
- [[TestBenchmarkSuite]] - code - tests\test_behavioral_benchmark.py
- [[TestComparison]] - code - tests\test_behavioral_benchmark.py
- [[TestEvaluateResult]] - code - tests\test_behavioral_benchmark.py
- [[TestRunFullBenchmark]] - code - tests\test_behavioral_benchmark.py
- [[TestScheduledRun]] - code - tests\test_behavioral_benchmark.py
- [[TestStorage]] - code - tests\test_behavioral_benchmark.py
- [[TestTrends]] - code - tests\test_behavioral_benchmark.py
- [[Tests for the Nightly Behavioral Benchmark.]] - rationale - tests\test_behavioral_benchmark.py
- [[_empty_executor()]] - code - tests\test_behavioral_benchmark.py
- [[_good_executor()]] - code - tests\test_behavioral_benchmark.py
- [[_slow_executor()]] - code - tests\test_behavioral_benchmark.py
- [[behavioral_benchmark.py]] - code - modules\shadow\behavioral_benchmark.py
- [[benchmark()]] - code - tests\test_behavioral_benchmark.py
- [[mock_grimoire()_1]] - code - tests\test_behavioral_benchmark.py
- [[mock_telegram()]] - code - tests\test_behavioral_benchmark.py
- [[test_behavioral_benchmark.py]] - code - tests\test_behavioral_benchmark.py
- [[wired_benchmark()]] - code - tests\test_behavioral_benchmark.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Behavioral_Benchmark
SORT file.name ASC
```

## Connections to other communities
- 3 edges to [[_COMMUNITY_Cross-Reference & Security]]
- 1 edge to [[_COMMUNITY_Data Pipeline & Embeddings]]
- 1 edge to [[_COMMUNITY_Tool Evaluator]]

## Top bridge nodes
- [[.evaluate_result()]] - degree 16, connects to 1 community
- [[.alert_on_regression()]] - degree 9, connects to 1 community
- [[._store_report()]] - degree 6, connects to 1 community
- [[.get_trend()]] - degree 5, connects to 1 community
- [[._load_previous_report()]] - degree 5, connects to 1 community