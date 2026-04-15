---
source_file: "tests\test_test_gate.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L281"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# If pass count goes up (new tests added), allow it.

## Connections
- [[GateResult]] - `uses` [INFERRED]
- [[TestGate]] - `uses` [INFERRED]
- [[TestResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)