---
source_file: "modules\shadow\retry_engine.py"
type: "code"
community: "Retry Engine"
location: "L37"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Retry_Engine
---

# FailureType

## Connections
- [[reset fatigue resets the fatigue counter to 0.]] - `uses` [INFERRED]
- [[After escalation, a local re-verification attempt is made.]] - `uses` [INFERRED]
- [[After escalation, three entries are stored answer, teaching, failure_pattern.]] - `uses` [INFERRED]
- [[All 12 strategy categories are used before declaring exhaustion.]] - `uses` [INFERRED]
- [[Classify failures as infrastructure vs model to avoid inflating fatigue.]] - `rationale_for` [EXTRACTED]
- [[Create an evaluate_fn that succeeds on a specific attempt number.      Args]] - `uses` [INFERRED]
- [[Each failed attempt records its failure_type classification.]] - `uses` [INFERRED]
- [[Each failed attempt uses a different strategy category.]] - `uses` [INFERRED]
- [[Escalation sends the original task and failure summary to Apex.]] - `uses` [INFERRED]
- [[Exceptions in execute_fn are caught and recorded as failures.]] - `uses` [INFERRED]
- [[First attempt succeeds — returns immediately, no retries.]] - `uses` [INFERRED]
- [[Fresh RetryEngine instance.]] - `uses` [INFERRED]
- [[Grimoire search failure is handled gracefully.]] - `uses` [INFERRED]
- [[Hardware impossibility detected in error causes early exit.]] - `uses` [INFERRED]
- [[Infrastructure failures (tool_loader empty) do NOT increment fatigue.]] - `uses` [INFERRED]
- [[Mock execute function that always raises.]] - `uses` [INFERRED]
- [[Mock execute function that returns a basic result.]] - `uses` [INFERRED]
- [[Model failures (bad LLM output) DO increment fatigue.]] - `uses` [INFERRED]
- [[No progress notifications when task succeeds before attempt 4.]] - `uses` [INFERRED]
- [[Only model failures increment fatigue, not infrastructure failures.]] - `uses` [INFERRED]
- [[Previous failure patterns are loaded from Grimoire before first attempt.]] - `uses` [INFERRED]
- [[Progress notifications fire at attempts 4, 8, and 12.]] - `uses` [INFERRED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[Session history records completed sessions with all attempts.]] - `uses` [INFERRED]
- [[Task succeeds on the 5th attempt after 4 failures.]] - `uses` [INFERRED]
- [[Tests for RetryEngine — 12-Attempt Strategy Rotation with Apex Escalation-Learni]] - `uses` [INFERRED]
- [[The teaching follow-up asks Apex to explain its approach vs our failures.]] - `uses` [INFERRED]
- [[Tool execution errors should be classified as infrastructure, not model.]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[Verify there are exactly 12 strategy categories.]] - `uses` [INFERRED]
- [[When tool_loader returns empty on first attempt, skip ALL remaining retries.]] - `uses` [INFERRED]
- [[classify_failure defaults to model failure for non-infrastructure errors.]] - `uses` [INFERRED]
- [[classify_failure identifies infrastructure errors from error strings.]] - `uses` [INFERRED]
- [[classify_failure reads tool_loader_empty from result dict.]] - `uses` [INFERRED]
- [[escalate_to_apex works when given a dict instead of RetrySession.]] - `uses` [INFERRED]
- [[get_strategy_for_attempt never returns a repeated strategy within a session.]] - `uses` [INFERRED]
- [[retry_engine.py]] - `contains` [EXTRACTED]
- [[should_escalate returns False when fewer than 12 attempts have been made.]] - `uses` [INFERRED]
- [[should_escalate returns True for hardware impossibility even before 12.]] - `uses` [INFERRED]
- [[should_escalate returns True for network impossibility.]] - `uses` [INFERRED]
- [[should_escalate returns True when all 12 attempts are exhausted.]] - `uses` [INFERRED]
- [[should_escalate works with dict representation of session.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Retry_Engine