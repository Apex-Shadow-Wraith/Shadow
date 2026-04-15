---
source_file: "tests\test_retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L872"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Tool execution errors should be classified as infrastructure, not model.

## Connections
- [[Attempt]] - `uses` [INFERRED]
- [[FailureType]] - `uses` [INFERRED]
- [[RetryEngine]] - `uses` [INFERRED]
- [[RetrySession]] - `uses` [INFERRED]
- [[test_classify_failure_tool_execution_errors()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine