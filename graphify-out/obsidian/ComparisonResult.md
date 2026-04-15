---
source_file: "modules\shadow\behavioral_benchmark.py"
type: "code"
community: "Behavioral Benchmark"
location: "L56"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Behavioral_Benchmark
---

# ComparisonResult

## Connections
- [[.compare_to_previous()]] - `calls` [EXTRACTED]
- [[.test_alert_sends_telegram()]] - `calls` [INFERRED]
- [[.test_alert_sets_frozen_flag()]] - `calls` [INFERRED]
- [[.test_no_regression_no_freeze()]] - `calls` [INFERRED]
- [[.test_should_freeze_true_after_regression()]] - `calls` [INFERRED]
- [[Bare benchmark with no Grimoire or Telegram.]] - `uses` [INFERRED]
- [[Benchmark with mocked Grimoire and Telegram.]] - `uses` [INFERRED]
- [[Comparison between current and previous benchmark runs.]] - `rationale_for` [EXTRACTED]
- [[Returns a plausible response with lots of keywords.]] - `uses` [INFERRED]
- [[Simulates a slow response by manipulating time (we test via duration param).]] - `uses` [INFERRED]
- [[TestAlerting]] - `uses` [INFERRED]
- [[TestBenchmarkSuite]] - `uses` [INFERRED]
- [[TestComparison]] - `uses` [INFERRED]
- [[TestEvaluateResult]] - `uses` [INFERRED]
- [[TestRunFullBenchmark]] - `uses` [INFERRED]
- [[TestScheduledRun]] - `uses` [INFERRED]
- [[TestStorage]] - `uses` [INFERRED]
- [[TestTrends]] - `uses` [INFERRED]
- [[Tests for the Nightly Behavioral Benchmark.]] - `uses` [INFERRED]
- [[behavioral_benchmark.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Behavioral_Benchmark