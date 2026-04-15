---
source_file: "tests\test_omen_sandbox.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L212"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Compiles with nvcc when GPU present.

## Connections
- [[.test_compile_with_nvcc()]] - `rationale_for` [EXTRACTED]
- [[CCompiler]] - `uses` [INFERRED]
- [[CodeSandbox]] - `uses` [INFERRED]
- [[CompileResult]] - `uses` [INFERRED]
- [[CppCompiler]] - `uses` [INFERRED]
- [[CudaCompiler]] - `uses` [INFERRED]
- [[ExecuteResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)