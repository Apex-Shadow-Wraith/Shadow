---
source_file: "tests\test_context_profiler.py"
type: "rationale"
community: "Context Profiler"
location: "L164"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Profiler
---

# Profiler should not crash on a package missing expected attributes.

## Connections
- [[.test_graceful_handling_of_malformed_package()]] - `rationale_for` [EXTRACTED]
- [[ContextProfile]] - `uses` [INFERRED]
- [[ContextProfiler]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Profiler