---
type: community
cohesion: 0.04
members: 100
---

# Drift Detector

**Cohesion:** 0.04 - loosely connected
**Members:** 100 nodes

## Members
- [[.__init__()_65]] - code - modules\shadow\drift_detector.py
- [[._init_db()_5]] - code - modules\shadow\drift_detector.py
- [[.analyze_drift()]] - code - modules\shadow\drift_detector.py
- [[.detect_violations()]] - code - modules\shadow\drift_detector.py
- [[.generate_correction_report()]] - code - modules\shadow\drift_detector.py
- [[.get_drift_stats()]] - code - modules\shadow\drift_detector.py
- [[.get_module_profile()]] - code - modules\shadow\drift_detector.py
- [[.log_routing()]] - code - modules\shadow\drift_detector.py
- [[.test_actual_task_types()]] - code - tests\test_drift_detector.py
- [[.test_all_module_roles_defined()]] - code - tests\test_drift_detector.py
- [[.test_clean_report()]] - code - tests\test_drift_detector.py
- [[.test_concurrent_db_access()]] - code - tests\test_drift_detector.py
- [[.test_correct_module_returns_none()]] - code - tests\test_drift_detector.py
- [[.test_correct_routing_no_violation()]] - code - tests\test_drift_detector.py
- [[.test_custom_config()]] - code - tests\test_drift_detector.py
- [[.test_db_created_on_init()_1]] - code - tests\test_drift_detector.py
- [[.test_drift_score_reflects_violations()]] - code - tests\test_drift_detector.py
- [[.test_empty_logs_zero_drift()]] - code - tests\test_drift_detector.py
- [[.test_empty_profile()]] - code - tests\test_drift_detector.py
- [[.test_examples_limited()]] - code - tests\test_drift_detector.py
- [[.test_generalist_threshold_value()]] - code - tests\test_drift_detector.py
- [[.test_identifies_generalist_modules()]] - code - tests\test_drift_detector.py
- [[.test_identifies_underused_modules()]] - code - tests\test_drift_detector.py
- [[.test_log_correct_routing_no_violation()]] - code - tests\test_drift_detector.py
- [[.test_log_marks_violation()]] - code - tests\test_drift_detector.py
- [[.test_log_returns_id()]] - code - tests\test_drift_detector.py
- [[.test_log_stores_description()]] - code - tests\test_drift_detector.py
- [[.test_logs_accumulate()]] - code - tests\test_drift_detector.py
- [[.test_on_role_percentage()]] - code - tests\test_drift_detector.py
- [[.test_report_mentions_modules()]] - code - tests\test_drift_detector.py
- [[.test_report_mentions_underused()]] - code - tests\test_drift_detector.py
- [[.test_stats_structure()]] - code - tests\test_drift_detector.py
- [[.test_stats_trend_stable()]] - code - tests\test_drift_detector.py
- [[.test_stats_with_no_data()]] - code - tests\test_drift_detector.py
- [[.test_tables_exist()]] - code - tests\test_drift_detector.py
- [[.test_unknown_module_profile()]] - code - tests\test_drift_detector.py
- [[.test_unknown_module_returns_none()]] - code - tests\test_drift_detector.py
- [[.test_unknown_task_type()]] - code - tests\test_drift_detector.py
- [[.test_violation_detected()]] - code - tests\test_drift_detector.py
- [[.test_violation_includes_suggestions()]] - code - tests\test_drift_detector.py
- [[.test_wrong_module_returns_violation()]] - code - tests\test_drift_detector.py
- [[All 13 modules have role definitions.]] - rationale - tests\test_drift_detector.py
- [[Analyze routing logs for boundary violations and drift patterns.          Args]] - rationale - modules\shadow\drift_detector.py
- [[Code task to Omen = correct, returns None.]] - rationale - tests\test_drift_detector.py
- [[Code task → Omen is correct.]] - rationale - tests\test_drift_detector.py
- [[Config dict is stored.]] - rationale - tests\test_drift_detector.py
- [[Correct routing is not flagged.]] - rationale - tests\test_drift_detector.py
- [[Create tables for routing logs and drift analysis.]] - rationale - modules\shadow\drift_detector.py
- [[Detects when modules drift from their designed specialization.]] - rationale - modules\shadow\drift_detector.py
- [[Drift Detector — Module Specialization Drift Detection =========================]] - rationale - modules\shadow\drift_detector.py
- [[DriftDetector]] - code - modules\shadow\drift_detector.py
- [[Empty logs produce 0.0 drift score.]] - rationale - tests\test_drift_detector.py
- [[Empty stats are valid.]] - rationale - tests\test_drift_detector.py
- [[Equal violations = stable trend.]] - rationale - tests\test_drift_detector.py
- [[Examples list is capped at 5.]] - rationale - tests\test_drift_detector.py
- [[GENERALIST_THRESHOLD is 5.]] - rationale - tests\test_drift_detector.py
- [[Generate a plain-English report of drift patterns.          Returns]] - rationale - modules\shadow\drift_detector.py
- [[Get summary stats for Growth Engine integration.          Returns             D]] - rationale - modules\shadow\drift_detector.py
- [[Initialize drift detector with SQLite storage.          Args             db_pat]] - rationale - modules\shadow\drift_detector.py
- [[Math task to Omen = violation.]] - rationale - tests\test_drift_detector.py
- [[Math task → Omen is a violation.]] - rationale - tests\test_drift_detector.py
- [[Module handling 5+ task types flagged as generalist.]] - rationale - tests\test_drift_detector.py
- [[Module with no tasks has clean profile.]] - rationale - tests\test_drift_detector.py
- [[Modules receiving very few tasks are flagged.]] - rationale - tests\test_drift_detector.py
- [[Multiple logs are stored.]] - rationale - tests\test_drift_detector.py
- [[Profile a module's actual behavior vs its designed role.          Args]] - rationale - modules\shadow\drift_detector.py
- [[Profile shows all task types handled.]] - rationale - tests\test_drift_detector.py
- [[Provide a fresh DriftDetector instance.]] - rationale - tests\test_drift_detector.py
- [[Provide a temporary database path.]] - rationale - tests\test_drift_detector.py
- [[Real-time check does this routing make sense          Args             task_t]] - rationale - modules\shadow\drift_detector.py
- [[Record a routing decision.          Args             task_type Category of tas]] - rationale - modules\shadow\drift_detector.py
- [[Report flags underused modules.]] - rationale - tests\test_drift_detector.py
- [[Report names specific modules with violations.]] - rationale - tests\test_drift_detector.py
- [[Report with no violations says so.]] - rationale - tests\test_drift_detector.py
- [[Required tables exist after init.]] - rationale - tests\test_drift_detector.py
- [[SQLite DB is created on init.]] - rationale - tests\test_drift_detector.py
- [[Task description is persisted.]] - rationale - tests\test_drift_detector.py
- [[TestAnalyzeDrift]] - code - tests\test_drift_detector.py
- [[TestCorrectionReport]] - code - tests\test_drift_detector.py
- [[TestDetectViolations]] - code - tests\test_drift_detector.py
- [[TestDriftStats]] - code - tests\test_drift_detector.py
- [[TestEdgeCases_7]] - code - tests\test_drift_detector.py
- [[TestInit]] - code - tests\test_drift_detector.py
- [[TestLogRouting]] - code - tests\test_drift_detector.py
- [[TestModuleProfile]] - code - tests\test_drift_detector.py
- [[Tests for Module Specialization Drift Detection.]] - rationale - tests\test_drift_detector.py
- [[Two detectors can share a DB path.]] - rationale - tests\test_drift_detector.py
- [[Unknown module gets 'unknown' role.]] - rationale - tests\test_drift_detector.py
- [[Unknown module is not flagged.]] - rationale - tests\test_drift_detector.py
- [[Unknown task type to known module is flagged (not in should_handle).]] - rationale - tests\test_drift_detector.py
- [[Violation includes suggested correct modules.]] - rationale - tests\test_drift_detector.py
- [[Violations are flagged at log time.]] - rationale - tests\test_drift_detector.py
- [[detector()]] - code - tests\test_drift_detector.py
- [[drift_detector.py]] - code - modules\shadow\drift_detector.py
- [[drift_score increases with more violations.]] - rationale - tests\test_drift_detector.py
- [[get_drift_stats returns expected keys.]] - rationale - tests\test_drift_detector.py
- [[log_routing returns a log_id string.]] - rationale - tests\test_drift_detector.py
- [[on_role_pct is calculated correctly.]] - rationale - tests\test_drift_detector.py
- [[test_drift_detector.py]] - code - tests\test_drift_detector.py
- [[tmp_db()_1]] - code - tests\test_drift_detector.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Drift_Detector
SORT file.name ASC
```

## Connections to other communities
- 10 edges to [[_COMMUNITY_Data Pipeline & Embeddings]]
- 1 edge to [[_COMMUNITY_Module Lifecycle]]

## Top bridge nodes
- [[.log_routing()]] - degree 22, connects to 1 community
- [[.analyze_drift()]] - degree 13, connects to 1 community
- [[.get_module_profile()]] - degree 7, connects to 1 community
- [[.test_concurrent_db_access()]] - degree 6, connects to 1 community
- [[.__init__()_65]] - degree 4, connects to 1 community