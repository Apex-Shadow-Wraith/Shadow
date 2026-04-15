---
source_file: "tests\test_omen_sandbox.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L202"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# nvidia-smi failure means no GPU.

## Connections
- [[.test_detects_gpu_absent()]] - `rationale_for` [EXTRACTED]
- [[CCompiler]] - `uses` [INFERRED]
- [[CodeSandbox]] - `uses` [INFERRED]
- [[CompileResult]] - `uses` [INFERRED]
- [[CppCompiler]] - `uses` [INFERRED]
- [[CudaCompiler]] - `uses` [INFERRED]
- [[ExecuteResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)