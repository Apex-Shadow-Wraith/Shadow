---
source_file: "tests\test_behavioral_benchmark.py"
type: "rationale"
community: "Behavioral Benchmark"
location: "L77"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Behavioral_Benchmark
---

# Simulates a slow response by manipulating time (we test via duration param).

## Connections
- [[BehavioralBenchmark]] - `uses` [INFERRED]
- [[BenchmarkReport]] - `uses` [INFERRED]
- [[BenchmarkTask]] - `uses` [INFERRED]
- [[ComparisonResult]] - `uses` [INFERRED]
- [[TaskResult]] - `uses` [INFERRED]
- [[_slow_executor()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Behavioral_Benchmark