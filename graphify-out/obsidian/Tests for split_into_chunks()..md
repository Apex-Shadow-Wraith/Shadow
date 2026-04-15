---
source_file: "tests\test_chunked_processor.py"
type: "rationale"
community: "Async Task Queue"
location: "L105"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Tests for split_into_chunks().

## Connections
- [[ChunkResult]] - `uses` [INFERRED]
- [[ChunkedProcessor]] - `uses` [INFERRED]
- [[ChunkedResult]] - `uses` [INFERRED]
- [[TestSplitIntoChunks]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue