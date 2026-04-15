---
source_file: "modules\shadow\context_manager.py"
type: "code"
community: "Context Compression"
location: "L29"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Context_Compression
---

# TokenBreakdown

## Connections
- [[.as_dict()]] - `method` [EXTRACTED]
- [[.build_context()]] - `calls` [EXTRACTED]
- [[.get_usage_report()]] - `calls` [EXTRACTED]
- [[An input that exceeds the limit alone should return an error, not crash.]] - `uses` [INFERRED]
- [[ContextCompressor]] - `uses` [INFERRED]
- [[Current input must never be modified by trimming.]] - `uses` [INFERRED]
- [[Default context manager with 128K limit.]] - `uses` [INFERRED]
- [[Estimate should be within 20% of known real-world values.]] - `uses` [INFERRED]
- [[Even with huge inputs, the assembled context must fit.]] - `uses` [INFERRED]
- [[Failure patterns should only be trimmed after tool_results, memories, and histor]] - `uses` [INFERRED]
- [[History trimming should keep at least 3 exchanges (6 messages).]] - `uses` [INFERRED]
- [[Report before any context is built.]] - `uses` [INFERRED]
- [[Small context manager for testing trimming (1000 token limit).]] - `uses` [INFERRED]
- [[System prompt must never be modified by trimming.]] - `uses` [INFERRED]
- [[Test calibration against actual token counts.]] - `uses` [INFERRED]
- [[Test config-driven behavior.]] - `uses` [INFERRED]
- [[Test context assembly.]] - `uses` [INFERRED]
- [[Test model context limit lookup.]] - `uses` [INFERRED]
- [[Test model switching.]] - `uses` [INFERRED]
- [[Test priority-based trimming.]] - `uses` [INFERRED]
- [[Test that output always fits within max_tokens.]] - `uses` [INFERRED]
- [[Test token estimation accuracy.]] - `uses` [INFERRED]
- [[Test usage reporting.]] - `uses` [INFERRED]
- [[TestBuildContext]] - `uses` [INFERRED]
- [[TestCalibration]] - `uses` [INFERRED]
- [[TestConfigIntegration]] - `uses` [INFERRED]
- [[TestEstimateTokens]] - `uses` [INFERRED]
- [[TestGetModelContextLimit]] - `uses` [INFERRED]
- [[TestGetUsageReport]] - `uses` [INFERRED]
- [[TestOverflowPrevention]] - `uses` [INFERRED]
- [[TestTrimContext]] - `uses` [INFERRED]
- [[TestUpdateModel]] - `uses` [INFERRED]
- [[Tests for Context Window Manager =================================== Validates t]] - `uses` [INFERRED]
- [[Token usage breakdown for each context component.]] - `rationale_for` [EXTRACTED]
- [[Tool results should be summarized, not just deleted, when possible.]] - `uses` [INFERRED]
- [[Tool results should be trimmed before memories or history.]] - `uses` [INFERRED]
- [[When trimming memories, keep highest relevance_score.]] - `uses` [INFERRED]
- [[With a 500 token limit, a big history should trigger trimming.]] - `uses` [INFERRED]
- [[check_history_overflow should correctly detect when adding a turn would overflow]] - `uses` [INFERRED]
- [[context_manager.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Context_Compression