---
source_file: "tests\test_chunked_processor.py"
type: "rationale"
community: "Async Task Queue"
location: "L248"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# If generate_fn fails mid-chunk, return partial result.

## Connections
- [[.test_generate_fn_failure_mid_chunk()]] - `rationale_for` [EXTRACTED]
- [[ChunkResult]] - `uses` [INFERRED]
- [[ChunkedProcessor]] - `uses` [INFERRED]
- [[ChunkedResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue