---
source_file: "tests\test_chain_of_thought.py"
type: "rationale"
community: "Chain of Thought"
location: "L52"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Chain_of_Thought
---

# Scorer that returns increasing confidence per call.

## Connections
- [[ChainOfThought]] - `uses` [INFERRED]
- [[ChainResult]] - `uses` [INFERRED]
- [[ReasoningStep]] - `uses` [INFERRED]
- [[_SteppedConfidenceScorer]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Chain_of_Thought