---
source_file: "tests\test_retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L103"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# All 12 strategy categories are used before declaring exhaustion.

## Connections
- [[Attempt]] - `uses` [INFERRED]
- [[FailureType]] - `uses` [INFERRED]
- [[RetryEngine]] - `uses` [INFERRED]
- [[RetrySession]] - `uses` [INFERRED]
- [[test_all_12_categories_used()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine