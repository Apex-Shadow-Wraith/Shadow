---
source_file: "modules\cerberus\reversibility.py"
type: "code"
community: "Base Module & Apex API"
location: "L29"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# ReversibilityEngine

## Connections
- [[.__init__()_6]] - `calls` [INFERRED]
- [[.__init__()_10]] - `method` [EXTRACTED]
- [[._init_db()_1]] - `method` [EXTRACTED]
- [[._record_snapshot()]] - `method` [EXTRACTED]
- [[._snapshot_config()]] - `method` [EXTRACTED]
- [[._snapshot_database()]] - `method` [EXTRACTED]
- [[._snapshot_external()]] - `method` [EXTRACTED]
- [[._snapshot_file()]] - `method` [EXTRACTED]
- [[.cleanup_expired()]] - `method` [EXTRACTED]
- [[.close()]] - `method` [EXTRACTED]
- [[.get_snapshot()]] - `method` [EXTRACTED]
- [[.list_snapshots()]] - `method` [EXTRACTED]
- [[.rollback()]] - `method` [EXTRACTED]
- [[.snapshot_before_action()]] - `method` [EXTRACTED]
- [[.test_snapshots_persist_across_instances()]] - `calls` [INFERRED]
- [[Analyze tool metadata and classify as autonomous or approval_required.]] - `uses` [INFERRED]
- [[Append to audit log. Append-only — entries cannot be modified.          Phase 1]] - `uses` [INFERRED]
- [[Basic PII removal from search queries.          Phase 1 regex patterns for comm]] - `uses` [INFERRED]
- [[Cerberus]] - `uses` [INFERRED]
- [[Cerberus performance stats for daily safety report.]] - `uses` [INFERRED]
- [[Cerberus shutdown. Log final stats.]] - `uses` [INFERRED]
- [[Cerberus — Ethics, Safety, and Accountability ==================================]] - `uses` [INFERRED]
- [[Cerberus — Ethics, Safety, and Accountability.]] - `uses` [INFERRED]
- [[Cerberus's MCP tools.]] - `uses` [INFERRED]
- [[Check action against hard limits. These are permanent.]] - `uses` [INFERRED]
- [[Check tool against permission tier system.          Known autonomous tools pass]] - `uses` [INFERRED]
- [[Create a ReversibilityEngine with temp directories.]] - `uses` [INFERRED]
- [[Create a sample SQLite database with test data.]] - `uses` [INFERRED]
- [[Create a sample file to snapshot.]] - `uses` [INFERRED]
- [[Create a snapshot if this tool writes data. Returns snapshot_id or None.]] - `uses` [INFERRED]
- [[Create the cerberus_audit_log table if it doesn't exist.]] - `uses` [INFERRED]
- [[Detect credential-like patterns in text.]] - `uses` [INFERRED]
- [[Execute a Cerberus tool (safety_check, audit_log, etc.).]] - `uses` [INFERRED]
- [[Fast-path ethical lookup against curated biblical topics.          Searches topi]] - `uses` [INFERRED]
- [[Load hard limits from protected config file.]] - `uses` [INFERRED]
- [[Manages pre-action snapshots for rollback capability.      Every file modificati]] - `rationale_for` [EXTRACTED]
- [[Post-execution hook. Safety net after tool runs.          From Session 12 'Post]] - `uses` [INFERRED]
- [[Pre-execution hook. Wraps every tool call in Step 5.          From Session 12 ']] - `uses` [INFERRED]
- [[Query audit log for false positive calibration stats.          Args]] - `uses` [INFERRED]
- [[Record a false positive in the audit log for calibration.          Args]] - `uses` [INFERRED]
- [[Register a tool with Cerberus safety classification.          If classification]] - `uses` [INFERRED]
- [[Result of a safety check.]] - `uses` [INFERRED]
- [[Return list of tools auto-registered this session.          Used by DailySafetyR]] - `uses` [INFERRED]
- [[SafetyCheckResult]] - `uses` [INFERRED]
- [[SafetyVerdict]] - `uses` [INFERRED]
- [[Scan a model response for confabulation phrases.          Returns a dict with ``]] - `uses` [INFERRED]
- [[Shadow's safety gate.      Architecture Cerberus runs as a rule engine with LLM]] - `uses` [INFERRED]
- [[Structured result from a Cerberus safety check.      Block loudly, not silently.]] - `uses` [INFERRED]
- [[TestCleanupExpired]] - `uses` [INFERRED]
- [[TestConfigSnapshot]] - `uses` [INFERRED]
- [[TestDatabaseSnapshot]] - `uses` [INFERRED]
- [[TestExternalSnapshot]] - `uses` [INFERRED]
- [[TestFileSnapshot]] - `uses` [INFERRED]
- [[TestInvalidActionType]] - `uses` [INFERRED]
- [[TestListSnapshots]] - `uses` [INFERRED]
- [[TestSQLitePersistence]] - `uses` [INFERRED]
- [[Tests for Cerberus Reversibility Engine ========================================]] - `uses` [INFERRED]
- [[The safety gate. Step 4 of the decision loop.          Every plan passes through]] - `uses` [INFERRED]
- [[Verify config file hasn't been tampered with.]] - `uses` [INFERRED]
- [[Write a heartbeat file for the watchdog to monitor.          Called at the end o]] - `uses` [INFERRED]
- [[engine()_4]] - `calls` [INFERRED]
- [[reversibility.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Base_Module_&_Apex_API