---
type: community
cohesion: 0.33
members: 6
---

# Import Speed Tests

**Cohesion:** 0.33 - loosely connected
**Members:** 6 nodes

## Members
- [[Each module should import in under 500ms (cold import).]] - rationale - tests\test_import_speed.py
- [[Import Speed Tests ================== Measures cold-import time for each Shadow]] - rationale - tests\test_import_speed.py
- [[Remove target modules from sys.modules for cold-import measurement.]] - rationale - tests\test_import_speed.py
- [[clean_module_cache()]] - code - tests\test_import_speed.py
- [[test_import_speed()]] - code - tests\test_import_speed.py
- [[test_import_speed.py]] - code - tests\test_import_speed.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Import_Speed_Tests
SORT file.name ASC
```
