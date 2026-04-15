---
source_file: "tests\test_retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L645"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Grimoire search failure is handled gracefully.

## Connections
- [[Attempt]] - `uses` [INFERRED]
- [[FailureType]] - `uses` [INFERRED]
- [[RetryEngine]] - `uses` [INFERRED]
- [[RetrySession]] - `uses` [INFERRED]
- [[test_grimoire_search_failure_graceful()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine