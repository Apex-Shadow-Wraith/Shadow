---
source_file: "tests\test_benchmark_suite.py"
type: "rationale"
community: "Async Task Queue"
location: "L432"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# load_history should not include benchmark_tasks.json.

## Connections
- [[.test_load_history_skips_tasks_file()]] - `rationale_for` [EXTRACTED]
- [[BenchmarkSuite]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue