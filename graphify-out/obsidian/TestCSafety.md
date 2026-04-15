---
source_file: "tests\test_omen_sandbox.py"
type: "code"
community: "Code Analyzer (Omen)"
location: "L413"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Code_Analyzer_(Omen)
---

# TestCSafety

## Connections
- [[.test_allows_safe_code()]] - `method` [EXTRACTED]
- [[.test_blocks_exec_family()]] - `method` [EXTRACTED]
- [[.test_blocks_popen()]] - `method` [EXTRACTED]
- [[.test_blocks_system_call()]] - `method` [EXTRACTED]
- [[.test_execute_compiled_blocks_system()]] - `method` [EXTRACTED]
- [[CCompiler]] - `uses` [INFERRED]
- [[CodeSandbox]] - `uses` [INFERRED]
- [[CompileResult]] - `uses` [INFERRED]
- [[CppCompiler]] - `uses` [INFERRED]
- [[CudaCompiler]] - `uses` [INFERRED]
- [[ExecuteResult]] - `uses` [INFERRED]
- [[Tests for CC++ code safety validation.]] - `rationale_for` [EXTRACTED]
- [[test_omen_sandbox.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Code_Analyzer_(Omen)