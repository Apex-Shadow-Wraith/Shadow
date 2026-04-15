---
source_file: "tests\test_confidence_scorer.py"
type: "rationale"
community: "Benchmark Generator"
location: "L426"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Benchmark_Generator
---

# Response claims 'ran this through Omen' but no tools ran → low score.

## Connections
- [[.test_confabulation_tool_claim_without_execution()]] - `rationale_for` [EXTRACTED]
- [[ConfidenceScorer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Benchmark_Generator