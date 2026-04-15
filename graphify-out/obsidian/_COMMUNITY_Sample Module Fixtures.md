---
type: community
cohesion: 0.18
members: 11
---

# Sample Module Fixtures

**Cohesion:** 0.18 - loosely connected
**Members:** 11 nodes

## Members
- [[FIXME this module needs proper error handling]] - rationale - tests\fixtures\sample_module.py
- [[HACK workaround for upstream bug]] - rationale - tests\fixtures\sample_module.py
- [[TODO implement batch processing]] - rationale - tests\fixtures\sample_module.py
- [[.method_without_docs()]] - code - tests\fixtures\sample_module.py
- [[Sample module with deliberate code issues for self-improvement testing.  This fi]] - rationale - tests\fixtures\sample_module.py
- [[Sum all positive values.]] - rationale - tests\fixtures\sample_module.py
- [[UndocumentedClass]] - code - tests\fixtures\sample_module.py
- [[another_undocumented()]] - code - tests\fixtures\sample_module.py
- [[clean_function()]] - code - tests\fixtures\sample_module.py
- [[sample_module.py]] - code - tests\fixtures\sample_module.py
- [[very_long_function()]] - code - tests\fixtures\sample_module.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Sample_Module_Fixtures
SORT file.name ASC
```
