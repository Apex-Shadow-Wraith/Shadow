---
source_file: "tests\test_test_gate.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L250"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Even 1 fewer passing test should trigger revert.

## Connections
- [[GateResult]] - `uses` [INFERRED]
- [[TestGate]] - `uses` [INFERRED]
- [[TestResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)