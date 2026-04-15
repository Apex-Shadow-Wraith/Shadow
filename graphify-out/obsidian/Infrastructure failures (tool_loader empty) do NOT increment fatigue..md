---
source_file: "tests\test_retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L665"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Infrastructure failures (tool_loader empty) do NOT increment fatigue.

## Connections
- [[Attempt]] - `uses` [INFERRED]
- [[FailureType]] - `uses` [INFERRED]
- [[RetryEngine]] - `uses` [INFERRED]
- [[RetrySession]] - `uses` [INFERRED]
- [[test_infrastructure_failure_no_fatigue()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine