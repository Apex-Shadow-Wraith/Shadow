---
source_file: "tests\test_omen_sandbox.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L143"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# C++ syntax error returns failure.

## Connections
- [[.test_compile_syntax_error()_1]] - `rationale_for` [EXTRACTED]
- [[CCompiler]] - `uses` [INFERRED]
- [[CodeSandbox]] - `uses` [INFERRED]
- [[CompileResult]] - `uses` [INFERRED]
- [[CppCompiler]] - `uses` [INFERRED]
- [[CudaCompiler]] - `uses` [INFERRED]
- [[ExecuteResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)