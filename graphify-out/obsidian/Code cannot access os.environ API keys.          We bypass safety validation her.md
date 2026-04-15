---
source_file: "tests\test_sandbox.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L70"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Code cannot access os.environ API keys.          We bypass safety validation her

## Connections
- [[.test_strips_environment_variables()]] - `rationale_for` [EXTRACTED]
- [[CodeSandbox]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)