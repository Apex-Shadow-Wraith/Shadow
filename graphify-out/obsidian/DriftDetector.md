---
source_file: "modules\shadow\drift_detector.py"
type: "code"
community: "Drift Detector"
location: "L58"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Drift_Detector
---

# DriftDetector

## Connections
- [[.__init__()_65]] - `method` [EXTRACTED]
- [[._init_db()_5]] - `method` [EXTRACTED]
- [[.analyze_drift()]] - `method` [EXTRACTED]
- [[.detect_violations()]] - `method` [EXTRACTED]
- [[.generate_correction_report()]] - `method` [EXTRACTED]
- [[.get_drift_stats()]] - `method` [EXTRACTED]
- [[.get_module_profile()]] - `method` [EXTRACTED]
- [[.log_routing()]] - `method` [EXTRACTED]
- [[.test_concurrent_db_access()]] - `calls` [INFERRED]
- [[.test_custom_config()]] - `calls` [INFERRED]
- [[.test_db_created_on_init()_1]] - `calls` [INFERRED]
- [[.test_tables_exist()]] - `calls` [INFERRED]
- [[All 13 modules have role definitions.]] - `uses` [INFERRED]
- [[Code task to Omen = correct, returns None.]] - `uses` [INFERRED]
- [[Code task → Omen is correct.]] - `uses` [INFERRED]
- [[Config dict is stored.]] - `uses` [INFERRED]
- [[Correct routing is not flagged.]] - `uses` [INFERRED]
- [[Detects when modules drift from their designed specialization.]] - `rationale_for` [EXTRACTED]
- [[Empty logs produce 0.0 drift score.]] - `uses` [INFERRED]
- [[Empty stats are valid.]] - `uses` [INFERRED]
- [[Equal violations = stable trend.]] - `uses` [INFERRED]
- [[Examples list is capped at 5.]] - `uses` [INFERRED]
- [[GENERALIST_THRESHOLD is 5.]] - `uses` [INFERRED]
- [[Math task to Omen = violation.]] - `uses` [INFERRED]
- [[Math task → Omen is a violation.]] - `uses` [INFERRED]
- [[Module handling 5+ task types flagged as generalist.]] - `uses` [INFERRED]
- [[Module with no tasks has clean profile.]] - `uses` [INFERRED]
- [[Modules receiving very few tasks are flagged.]] - `uses` [INFERRED]
- [[Multiple logs are stored.]] - `uses` [INFERRED]
- [[Profile shows all task types handled.]] - `uses` [INFERRED]
- [[Provide a fresh DriftDetector instance.]] - `uses` [INFERRED]
- [[Provide a temporary database path.]] - `uses` [INFERRED]
- [[Report flags underused modules.]] - `uses` [INFERRED]
- [[Report names specific modules with violations.]] - `uses` [INFERRED]
- [[Report with no violations says so.]] - `uses` [INFERRED]
- [[Required tables exist after init.]] - `uses` [INFERRED]
- [[SQLite DB is created on init.]] - `uses` [INFERRED]
- [[Task description is persisted.]] - `uses` [INFERRED]
- [[TestAnalyzeDrift]] - `uses` [INFERRED]
- [[TestCorrectionReport]] - `uses` [INFERRED]
- [[TestDetectViolations]] - `uses` [INFERRED]
- [[TestDriftStats]] - `uses` [INFERRED]
- [[TestEdgeCases_7]] - `uses` [INFERRED]
- [[TestInit]] - `uses` [INFERRED]
- [[TestLogRouting]] - `uses` [INFERRED]
- [[TestModuleProfile]] - `uses` [INFERRED]
- [[Tests for Module Specialization Drift Detection.]] - `uses` [INFERRED]
- [[Two detectors can share a DB path.]] - `uses` [INFERRED]
- [[Unknown module gets 'unknown' role.]] - `uses` [INFERRED]
- [[Unknown module is not flagged.]] - `uses` [INFERRED]
- [[Unknown task type to known module is flagged (not in should_handle).]] - `uses` [INFERRED]
- [[Violation includes suggested correct modules.]] - `uses` [INFERRED]
- [[Violations are flagged at log time.]] - `uses` [INFERRED]
- [[detector()]] - `calls` [INFERRED]
- [[drift_detector.py]] - `contains` [EXTRACTED]
- [[drift_score increases with more violations.]] - `uses` [INFERRED]
- [[get_drift_stats returns expected keys.]] - `uses` [INFERRED]
- [[log_routing returns a log_id string.]] - `uses` [INFERRED]
- [[on_role_pct is calculated correctly.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Drift_Detector