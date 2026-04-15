---
source_file: "tests\test_chunked_processor.py"
type: "rationale"
community: "Async Task Queue"
location: "L38"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Create a long text with sentences but no paragraph breaks.

## Connections
- [[ChunkResult]] - `uses` [INFERRED]
- [[ChunkedProcessor]] - `uses` [INFERRED]
- [[ChunkedResult]] - `uses` [INFERRED]
- [[_make_long_text_no_paragraphs()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue