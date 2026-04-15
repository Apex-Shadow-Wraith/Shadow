---
source_file: "modules\omen\tool_creator.py"
type: "code"
community: "Module Lifecycle"
location: "L78"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Module_Lifecycle
---

# ToolCreator

## Connections
- [[.__init__()_45]] - `method` [EXTRACTED]
- [[._check_code_safety()]] - `method` [EXTRACTED]
- [[._compute_signature()]] - `method` [EXTRACTED]
- [[._ensure_staging_dir()]] - `method` [EXTRACTED]
- [[._normalize_code()]] - `method` [EXTRACTED]
- [[.approve_tool()]] - `method` [EXTRACTED]
- [[.detect_pattern()]] - `method` [EXTRACTED]
- [[.get_creation_stats()]] - `method` [EXTRACTED]
- [[.get_staged_tools()]] - `method` [EXTRACTED]
- [[.propose_tool()]] - `method` [EXTRACTED]
- [[.reject_tool()]] - `method` [EXTRACTED]
- [[.stage_tool()]] - `method` [EXTRACTED]
- [[.test_approve_registers_with_cerberus()]] - `calls` [INFERRED]
- [[.test_cerberus_classifies_risk()]] - `calls` [INFERRED]
- [[.test_no_sandbox_skips_testing()]] - `calls` [INFERRED]
- [[.test_propose_generates_tests()]] - `calls` [INFERRED]
- [[.test_propose_with_generate_fn()]] - `calls` [INFERRED]
- [[.test_sandbox_fail_stays_proposed()]] - `calls` [INFERRED]
- [[.test_sandbox_pass_stages_tool()]] - `calls` [INFERRED]
- [[.test_sandbox_runs_tests()]] - `calls` [INFERRED]
- [[.test_stage_sends_notification()]] - `calls` [INFERRED]
- [[.test_staging_dir_created_if_not_exists()]] - `calls` [INFERRED]
- [[.validate_tool()]] - `method` [EXTRACTED]
- [[2 similar executions → no pattern (below default threshold of 3).]] - `uses` [INFERRED]
- [[3 similar executions → pattern detected.]] - `uses` [INFERRED]
- [[Approve unknown candidate_id → False.]] - `uses` [INFERRED]
- [[Autonomous tool creation pipeline with approval staging.      Detects repeated c]] - `rationale_for` [EXTRACTED]
- [[Cerberus mock classifies risk level.]] - `uses` [INFERRED]
- [[Custom threshold of 4 → 3 occurrences not enough.]] - `uses` [INFERRED]
- [[Different code structures → no shared pattern.]] - `uses` [INFERRED]
- [[Empty list → empty result.]] - `uses` [INFERRED]
- [[Fallback propose_tool wraps code without generate_fn.]] - `uses` [INFERRED]
- [[No cerberus → skip classification, can still stage.]] - `uses` [INFERRED]
- [[No notifier → tool staged, no crash.]] - `uses` [INFERRED]
- [[No sandbox → skip testing, stage with warning.]] - `uses` [INFERRED]
- [[Reject unknown candidate_id → False.]] - `uses` [INFERRED]
- [[Rejected tools remain in candidates for reference.]] - `uses` [INFERRED]
- [[Sandbox mock runs generated tests.]] - `uses` [INFERRED]
- [[Stats return valid data after operations.]] - `uses` [INFERRED]
- [[Stats updated on proposal.]] - `uses` [INFERRED]
- [[Test fail → status stays 'proposed'.]] - `uses` [INFERRED]
- [[Test pass → status 'staged'.]] - `uses` [INFERRED]
- [[TestApproveReject_1]] - `uses` [INFERRED]
- [[TestDetectPattern]] - `uses` [INFERRED]
- [[TestEdgeCases_21]] - `uses` [INFERRED]
- [[TestProposeTool]] - `uses` [INFERRED]
- [[TestStageTool]] - `uses` [INFERRED]
- [[TestValidateTool]] - `uses` [INFERRED]
- [[Tests for Autonomous Tool Creation Pipeline ====================================]] - `uses` [INFERRED]
- [[Three similar code executions (same structure).]] - `uses` [INFERRED]
- [[ToolCandidate has all required dataclass fields.]] - `uses` [INFERRED]
- [[approve_tool calls cerberus.register_tool.]] - `uses` [INFERRED]
- [[approve_tool sets status to 'approved'.]] - `uses` [INFERRED]
- [[creator()]] - `calls` [INFERRED]
- [[get_staged_tools returns staged candidates.]] - `uses` [INFERRED]
- [[propose_tool generates tests via generate_fn.]] - `uses` [INFERRED]
- [[propose_tool uses generate_fn to create code.]] - `uses` [INFERRED]
- [[reject_tool marks as rejected with reason.]] - `uses` [INFERRED]
- [[stage_tool sends Telegram notification via notifier.]] - `uses` [INFERRED]
- [[stage_tool writes .meta.json alongside tool file.]] - `uses` [INFERRED]
- [[stage_tool writes .py file to staging directory.]] - `uses` [INFERRED]
- [[staging_dir auto-created.]] - `uses` [INFERRED]
- [[tool_creator.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Module_Lifecycle