---
source_file: "tests\test_chunked_processor.py"
type: "rationale"
community: "Async Task Queue"
location: "L24"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Generate function that always raises.

## Connections
- [[ChunkResult]] - `uses` [INFERRED]
- [[ChunkedProcessor]] - `uses` [INFERRED]
- [[ChunkedResult]] - `uses` [INFERRED]
- [[_failing_generate()_1]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue