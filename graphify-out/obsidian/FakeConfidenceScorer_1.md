---
source_file: "tests\test_self_review.py"
type: "code"
community: "Async Task Queue"
location: "L13"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Async_Task_Queue
---

# FakeConfidenceScorer

## Connections
- [[.__init__()_121]] - `method` [EXTRACTED]
- [[.score_response()_3]] - `method` [EXTRACTED]
- [[.set_score()]] - `method` [EXTRACTED]
- [[.test_corrected_scores_higher_uses_corrected()]] - `calls` [EXTRACTED]
- [[.test_corrected_scores_lower_reverts_to_original()]] - `calls` [EXTRACTED]
- [[.test_duration_tracked()_1]] - `calls` [EXTRACTED]
- [[.test_generate_fn_failure_returns_original()]] - `calls` [EXTRACTED]
- [[.test_high_confidence_returns_original_no_review()]] - `calls` [EXTRACTED]
- [[.test_issues_found_triggers_regeneration()]] - `calls` [EXTRACTED]
- [[.test_low_confidence_triggers_review()]] - `calls` [EXTRACTED]
- [[.test_max_two_cycles_enforced()]] - `calls` [EXTRACTED]
- [[.test_no_generate_fn_returns_original()]] - `calls` [EXTRACTED]
- [[.test_no_issues_found_returns_original()]] - `calls` [EXTRACTED]
- [[.test_stats_after_reviews()]] - `calls` [EXTRACTED]
- [[Returns a configurable confidence score.]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]
- [[test_self_review.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Async_Task_Queue