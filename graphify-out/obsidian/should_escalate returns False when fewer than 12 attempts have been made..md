---
source_file: "tests\test_retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L392"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# should_escalate returns False when fewer than 12 attempts have been made.

## Connections
- [[Attempt]] - `uses` [INFERRED]
- [[FailureType]] - `uses` [INFERRED]
- [[RetryEngine]] - `uses` [INFERRED]
- [[RetrySession]] - `uses` [INFERRED]
- [[test_should_escalate_false_before_12()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine