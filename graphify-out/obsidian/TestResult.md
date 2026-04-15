---
source_file: "modules\omen\test_gate.py"
type: "code"
community: "Code Analyzer (Omen)"
location: "L25"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# TestResult

## Connections
- [[._parse_pytest_output()_1]] - `calls` [EXTRACTED]
- [[.test_not_success_when_failures()]] - `calls` [INFERRED]
- [[.test_success_when_all_pass()]] - `calls` [INFERRED]
- [[All tests passing should give success=True.]] - `uses` [INFERRED]
- [[Change that breaks tests should be reverted.]] - `uses` [INFERRED]
- [[Change that passes tests should be allowed, not reverted.]] - `uses` [INFERRED]
- [[Clean working tree should just return current HEAD.]] - `uses` [INFERRED]
- [[Edge cases for pytest output parsing.]] - `uses` [INFERRED]
- [[Even 1 fewer passing test should trigger revert.]] - `uses` [INFERRED]
- [[Exception during revert returns False.]] - `uses` [INFERRED]
- [[Failed revert returns False.]] - `uses` [INFERRED]
- [[Fresh gate should have empty history.]] - `uses` [INFERRED]
- [[Gate history should record decisions.]] - `uses` [INFERRED]
- [[GateResult should contain the checkpoint hash.]] - `uses` [INFERRED]
- [[Helper create a TestGate with mocked git root.]] - `uses` [INFERRED]
- [[History should be returned newest first.]] - `uses` [INFERRED]
- [[If baseline tests already fail, refuse to gate (not reverted).]] - `uses` [INFERRED]
- [[If change_fn raises, revert cleanly.]] - `uses` [INFERRED]
- [[If pass count goes up (new tests added), allow it.]] - `uses` [INFERRED]
- [[Long output should be truncated to 500 chars.]] - `uses` [INFERRED]
- [[Mock responses for create_checkpoint (clean tree).]] - `uses` [INFERRED]
- [[Mock subprocess result mimicking pytest output.]] - `uses` [INFERRED]
- [[Multiple gates in sequence should each work independently.]] - `uses` [INFERRED]
- [[New test failures should trigger revert.]] - `uses` [INFERRED]
- [[No pytest summary → all zeros, success=False.]] - `uses` [INFERRED]
- [[Output should be capped at 500 chars.]] - `uses` [INFERRED]
- [[Providing project_root should skip git detection.]] - `uses` [INFERRED]
- [[Result of a test suite run.]] - `rationale_for` [EXTRACTED]
- [[Should correctly parse pytest summary line.]] - `uses` [INFERRED]
- [[Should handle FileNotFoundError gracefully.]] - `uses` [INFERRED]
- [[Should handle timeout gracefully.]] - `uses` [INFERRED]
- [[Should raise RuntimeError if not in a git repo.]] - `uses` [INFERRED]
- [[Successful revert returns True.]] - `uses` [INFERRED]
- [[TestCreateCheckpoint]] - `uses` [INFERRED]
- [[TestExecuteWithGate]] - `uses` [INFERRED]
- [[TestGate without project_root should raise if git root detection fails.]] - `uses` [INFERRED]
- [[TestGateHistory]] - `uses` [INFERRED]
- [[TestNoGitRepo]] - `uses` [INFERRED]
- [[TestParseEdgeCases]] - `uses` [INFERRED]
- [[TestRevertToCheckpoint]] - `uses` [INFERRED]
- [[TestRunTests]] - `uses` [INFERRED]
- [[TestSequentialGates]] - `uses` [INFERRED]
- [[TestTestResult]] - `uses` [INFERRED]
- [[Tests for TestGate when no git repo is available.]] - `uses` [INFERRED]
- [[Tests for TestGate — Pre-Change Test Gate with Auto-Revert.]] - `uses` [INFERRED]
- [[Tests for TestGate.create_checkpoint.]] - `uses` [INFERRED]
- [[Tests for TestGate.execute_with_gate.]] - `uses` [INFERRED]
- [[Tests for TestGate.get_gate_history.]] - `uses` [INFERRED]
- [[Tests for TestGate.revert_to_checkpoint.]] - `uses` [INFERRED]
- [[Tests for TestGate.run_tests.]] - `uses` [INFERRED]
- [[Tests for TestResult dataclass.]] - `uses` [INFERRED]
- [[Tests for multiple sequential gate operations.]] - `uses` [INFERRED]
- [[create_checkpoint should return a valid commit hash.]] - `uses` [INFERRED]
- [[from_failure should produce errors=1, success=False.]] - `uses` [INFERRED]
- [[get_gate_history should respect the limit parameter.]] - `uses` [INFERRED]
- [[success=False when there are failures.]] - `uses` [INFERRED]
- [[success=True when failed==0 and errors==0 and total0.]] - `uses` [INFERRED]
- [[test_gate.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Code_Analyzer_(Omen)