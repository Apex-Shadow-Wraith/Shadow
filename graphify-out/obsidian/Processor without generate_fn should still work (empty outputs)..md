---
source_file: "tests\test_chunked_processor.py"
type: "rationale"
community: "Async Task Queue"
location: "L287"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Processor without generate_fn should still work (empty outputs).

## Connections
- [[.test_no_generate_fn()_1]] - `rationale_for` [EXTRACTED]
- [[ChunkResult]] - `uses` [INFERRED]
- [[ChunkedProcessor]] - `uses` [INFERRED]
- [[ChunkedResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue