---
source_file: "tests\test_retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L722"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# When tool_loader returns empty on first attempt, skip ALL remaining retries.

## Connections
- [[Attempt]] - `uses` [INFERRED]
- [[FailureType]] - `uses` [INFERRED]
- [[RetryEngine]] - `uses` [INFERRED]
- [[RetrySession]] - `uses` [INFERRED]
- [[test_early_exit_on_tool_loader_empty()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine