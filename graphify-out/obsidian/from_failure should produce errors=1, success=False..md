---
source_file: "tests\test_test_gate.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L21"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# from_failure should produce errors=1, success=False.

## Connections
- [[.test_from_failure_creates_failed_result()]] - `rationale_for` [EXTRACTED]
- [[GateResult]] - `uses` [INFERRED]
- [[TestGate]] - `uses` [INFERRED]
- [[TestResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)