---
source_file: "modules\omen\sandbox.py"
type: "code"
community: "Code Analyzer (Omen)"
location: "L120"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# _validate_c_safety()

## Connections
- [[.execute_compiled()]] - `calls` [EXTRACTED]
- [[.test_allows_safe_code()]] - `calls` [INFERRED]
- [[.test_blocks_exec_family()]] - `calls` [INFERRED]
- [[.test_blocks_popen()]] - `calls` [INFERRED]
- [[.test_blocks_system_call()]] - `calls` [INFERRED]
- [[Check CC++CUDA code for dangerous patterns.      Args         code Source co]] - `rationale_for` [EXTRACTED]
- [[sandbox.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Code_Analyzer_(Omen)