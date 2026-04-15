---
source_file: "modules\apex\apex.py"
type: "code"
community: "Apex API Providers"
location: "L36"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Apex_API_Providers
---

# EscalationLog

## Connections
- [[.__init__()_2]] - `method` [EXTRACTED]
- [[._init_db()]] - `method` [EXTRACTED]
- [[.get_escalation_stats()]] - `method` [EXTRACTED]
- [[.get_frequent_escalation_types()]] - `method` [EXTRACTED]
- [[.get_recent_teaching_signals()]] - `method` [EXTRACTED]
- [[.initialize()]] - `calls` [EXTRACTED]
- [[.log_escalation()]] - `method` [EXTRACTED]
- [[.mark_local_retry_success()]] - `method` [EXTRACTED]
- [[.update_teaching_signal()]] - `method` [EXTRACTED]
- [[Apex now has 9 tools (4 original + 3 learning + 2 training).]] - `uses` [INFERRED]
- [[Apex query logs escalation in the SQLite escalation log.]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[Create a TeachingExtractor.]] - `uses` [INFERRED]
- [[Create an Apex instance with temp paths.]] - `uses` [INFERRED]
- [[Create an EscalationLog with a temp database.]] - `uses` [INFERRED]
- [[Create and initialize Apex.]] - `uses` [INFERRED]
- [[Escalation stores teaching signal in Grimoire when available.]] - `uses` [INFERRED]
- [[Execute escalation_frequent through Apex.execute().]] - `uses` [INFERRED]
- [[Execute escalation_stats through Apex.execute().]] - `uses` [INFERRED]
- [[Execute teaching_review through Apex.execute().]] - `uses` [INFERRED]
- [[Extract from task input + response, dict has required keys.]] - `uses` [INFERRED]
- [[Grimoire has matching result, returns its content.]] - `uses` [INFERRED]
- [[Grimoire raises exception, returns None gracefully.]] - `uses` [INFERRED]
- [[Grimoire set but no matching results, returns None.]] - `uses` [INFERRED]
- [[Log 4 escalations of same type, appears in frequent list.]] - `uses` [INFERRED]
- [[Log 5 escalations across 3 task types, verify stats breakdown.]] - `uses` [INFERRED]
- [[Log an escalation, verify entry in DB with correct fields.]] - `uses` [INFERRED]
- [[Log escalation - extract teaching - store signal - query - found.]] - `uses` [INFERRED]
- [[Log escalation, mark retry success, verify flag set.]] - `uses` [INFERRED]
- [[Log escalation, update with teaching signal, verify stored.]] - `uses` [INFERRED]
- [[Log escalations with cost, verify total in stats.]] - `uses` [INFERRED]
- [[Long input truncated to 200 chars in summary.]] - `uses` [INFERRED]
- [[Long response truncated to 500 chars in approach.]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[No grimoire set, returns None.]] - `uses` [INFERRED]
- [[Old escalations outside window are excluded.]] - `uses` [INFERRED]
- [[Only 1 escalation of a type, not in frequent list.]] - `uses` [INFERRED]
- [[SQLite-backed log of every Apex escalation.      Tracks what was escalated, wh]] - `rationale_for` [EXTRACTED]
- [[Task type passes through correctly.]] - `uses` [INFERRED]
- [[TeachingExtractor]] - `uses` [INFERRED]
- [[TestEscalationLogBasic]] - `uses` [INFERRED]
- [[TestEscalationStats]] - `uses` [INFERRED]
- [[TestEscalationTools]] - `uses` [INFERRED]
- [[TestFrequentEscalations]] - `uses` [INFERRED]
- [[TestFullCycle]] - `uses` [INFERRED]
- [[TestGrimoireIntegration]] - `uses` [INFERRED]
- [[TestTeachingExtractor]] - `uses` [INFERRED]
- [[TestToolCount]] - `uses` [INFERRED]
- [[Tests for Apex Escalation-Learning Cycle =======================================]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[TrainingDataPipeline]] - `uses` [INFERRED]
- [[apex.py]] - `contains` [EXTRACTED]
- [[esc_log()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Apex_API_Providers