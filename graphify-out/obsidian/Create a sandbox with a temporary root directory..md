---
source_file: "tests\test_omen_sandbox.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L30"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Create a sandbox with a temporary root directory.

## Connections
- [[CCompiler]] - `uses` [INFERRED]
- [[CodeSandbox]] - `uses` [INFERRED]
- [[CompileResult]] - `uses` [INFERRED]
- [[CppCompiler]] - `uses` [INFERRED]
- [[CudaCompiler]] - `uses` [INFERRED]
- [[ExecuteResult]] - `uses` [INFERRED]
- [[sandbox()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)