---
source_file: "tests\test_retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L635"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Verify there are exactly 12 strategy categories.

## Connections
- [[Attempt]] - `uses` [INFERRED]
- [[FailureType]] - `uses` [INFERRED]
- [[RetryEngine]] - `uses` [INFERRED]
- [[RetrySession]] - `uses` [INFERRED]
- [[test_strategy_categories_count()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine