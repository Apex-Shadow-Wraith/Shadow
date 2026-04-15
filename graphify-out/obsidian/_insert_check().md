---
source_file: "tests\test_false_positive.py"
type: "code"
community: "Module Lifecycle"
location: "L27"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Module_Lifecycle
---

# _insert_check()

## Connections
- [[.close()_19]] - `calls` [INFERRED]
- [[.execute()_36]] - `calls` [INFERRED]
- [[.test_calculates_fp_rate()]] - `calls` [EXTRACTED]
- [[.test_category_breakdown_accurate()]] - `calls` [EXTRACTED]
- [[.test_date_filtering()]] - `calls` [EXTRACTED]
- [[.test_high_fp_rate_triggers_calibration()]] - `calls` [EXTRACTED]
- [[.test_low_fp_rate_no_calibration()]] - `calls` [EXTRACTED]
- [[Helper to insert a check row into the audit log.]] - `rationale_for` [EXTRACTED]
- [[test_false_positive.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Module_Lifecycle