---
source_file: "modules\shadow\self_review.py"
type: "code"
community: "Async Task Queue"
location: "L13"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# ReviewResult

## Connections
- [[.review()]] - `calls` [EXTRACTED]
- [[.test_review_result_has_all_fields()]] - `calls` [INFERRED]
- [[FakeConfidenceScorer_1]] - `uses` [INFERRED]
- [[High confidence responses skip review entirely.]] - `uses` [INFERRED]
- [[If generate_fn is None, return original response.]] - `uses` [INFERRED]
- [[If generate_fn raises, return original response gracefully.]] - `uses` [INFERRED]
- [[Low confidence responses trigger the review pass.]] - `uses` [INFERRED]
- [[Result of an adversarial self-review pass.]] - `rationale_for` [EXTRACTED]
- [[Return a generate_fn that returns responses in sequence.]] - `uses` [INFERRED]
- [[Return a simple generate_fn that always returns response.]] - `uses` [INFERRED]
- [[Returns a configurable confidence score.]] - `uses` [INFERRED]
- [[Review never exceeds max_cycles (default 2).]] - `uses` [INFERRED]
- [[ReviewResult tracks duration.]] - `uses` [INFERRED]
- [[TestGetReviewStats]] - `uses` [INFERRED]
- [[TestParseReviewIssues]] - `uses` [INFERRED]
- [[TestReview]] - `uses` [INFERRED]
- [[TestReviewResult]] - `uses` [INFERRED]
- [[TestShouldReview]] - `uses` [INFERRED]
- [[Tests for the Adversarial Self-Review Pass.]] - `uses` [INFERRED]
- [[When corrected response scores higher, it replaces the original.]] - `uses` [INFERRED]
- [[When corrected response scores lower, revert to original.]] - `uses` [INFERRED]
- [[When issues are found, a corrected response is generated.]] - `uses` [INFERRED]
- [[When reviewer says 'No issues found', return original.]] - `uses` [INFERRED]
- [[Without a confidence scorer, score defaults to 0.5 (below threshold).]] - `uses` [INFERRED]
- [[self_review.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Async_Task_Queue