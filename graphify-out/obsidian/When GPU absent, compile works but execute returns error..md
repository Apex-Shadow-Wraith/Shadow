---
source_file: "tests\test_omen_sandbox.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L226"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# When GPU absent, compile works but execute returns error.

## Connections
- [[.test_compile_only_mode_no_gpu()]] - `rationale_for` [EXTRACTED]
- [[CCompiler]] - `uses` [INFERRED]
- [[CodeSandbox]] - `uses` [INFERRED]
- [[CompileResult]] - `uses` [INFERRED]
- [[CppCompiler]] - `uses` [INFERRED]
- [[CudaCompiler]] - `uses` [INFERRED]
- [[ExecuteResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)