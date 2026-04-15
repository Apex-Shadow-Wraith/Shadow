---
source_file: "tests\test_test_gate.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L221"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Change that passes tests should be allowed, not reverted.

## Connections
- [[GateResult]] - `uses` [INFERRED]
- [[TestGate]] - `uses` [INFERRED]
- [[TestResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)