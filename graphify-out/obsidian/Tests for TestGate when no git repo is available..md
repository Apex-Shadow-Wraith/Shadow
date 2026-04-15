---
source_file: "tests\test_test_gate.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L520"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Tests for TestGate when no git repo is available.

## Connections
- [[GateResult]] - `uses` [INFERRED]
- [[TestGate]] - `uses` [INFERRED]
- [[TestNoGitRepo]] - `rationale_for` [EXTRACTED]
- [[TestResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)