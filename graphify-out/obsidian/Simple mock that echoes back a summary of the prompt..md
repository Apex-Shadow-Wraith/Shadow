---
source_file: "tests\test_chain_of_thought.py"
type: "rationale"
community: "Chain of Thought"
location: "L20"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Chain_of_Thought
---

# Simple mock that echoes back a summary of the prompt.

## Connections
- [[ChainOfThought]] - `uses` [INFERRED]
- [[ChainResult]] - `uses` [INFERRED]
- [[ReasoningStep]] - `uses` [INFERRED]
- [[_mock_generate()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Chain_of_Thought