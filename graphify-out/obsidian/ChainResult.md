---
source_file: "modules\shadow\chain_of_thought.py"
type: "code"
community: "Chain of Thought"
location: "L59"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Chain_of_Thought
---

# ChainResult

## Connections
- [[._execute_pipeline()]] - `calls` [EXTRACTED]
- [[.reason()]] - `calls` [EXTRACTED]
- [[.reason_custom()]] - `calls` [EXTRACTED]
- [[2 steps understand + execute.]] - `uses` [INFERRED]
- [[All 4 steps execute in order for complex tasks.]] - `uses` [INFERRED]
- [[Complete result of a chain-of-thought reasoning pass.]] - `rationale_for` [EXTRACTED]
- [[Complexity auto-detection from task text.]] - `uses` [INFERRED]
- [[Context string properly passed through.]] - `uses` [INFERRED]
- [[Generate function that always raises.]] - `uses` [INFERRED]
- [[High confidence after a step can skip remaining steps.]] - `uses` [INFERRED]
- [[Model call behavior and error handling.]] - `uses` [INFERRED]
- [[Only 1 step for simple tasks.]] - `uses` [INFERRED]
- [[Result dataclass has correct metadata.]] - `uses` [INFERRED]
- [[Returns a generate function that counts calls.]] - `uses` [INFERRED]
- [[Scorer that returns a fixed confidence value.]] - `uses` [INFERRED]
- [[Scorer that returns increasing confidence per call.]] - `uses` [INFERRED]
- [[Simple mock that echoes back a summary of the prompt.]] - `uses` [INFERRED]
- [[TestChainResult]] - `uses` [INFERRED]
- [[TestComplexPipeline]] - `uses` [INFERRED]
- [[TestContextHandling]] - `uses` [INFERRED]
- [[TestCustomPipeline]] - `uses` [INFERRED]
- [[TestEarlyExit]] - `uses` [INFERRED]
- [[TestEstimateComplexity]] - `uses` [INFERRED]
- [[TestGenerateFunction]] - `uses` [INFERRED]
- [[TestModeratePipeline]] - `uses` [INFERRED]
- [[TestReasoningStats]] - `uses` [INFERRED]
- [[TestSimplePipeline]] - `uses` [INFERRED]
- [[Tests for Chain-of-Thought Scaffolding ========================================]] - `uses` [INFERRED]
- [[_MockConfidenceScorer]] - `uses` [INFERRED]
- [[_SteppedConfidenceScorer]] - `uses` [INFERRED]
- [[chain_of_thought.py]] - `contains` [EXTRACTED]
- [[get_reasoning_stats returns valid data.]] - `uses` [INFERRED]
- [[reason_custom with user-defined steps.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Chain_of_Thought