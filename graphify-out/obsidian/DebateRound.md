---
source_file: "modules\shadow\adversarial_sparring.py"
type: "code"
community: "Adversarial Sparring"
location: "L80"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Adversarial_Sparring
---

# DebateRound

## Connections
- [[.spar()]] - `calls` [EXTRACTED]
- [[.test_critique_pattern_metadata()]] - `calls` [INFERRED]
- [[.test_only_stores_resolved_issues()]] - `calls` [INFERRED]
- [[.test_stores_in_grimoire()]] - `calls` [INFERRED]
- [[Bullet points should be parsed into individual issues.]] - `uses` [INFERRED]
- [[Create a mock generate_fn that returns responses in order.]] - `uses` [INFERRED]
- [[Critique patterns should be stored via grimoire.store().]] - `uses` [INFERRED]
- [[Debate should stop early when critic finds no issues.]] - `uses` [INFERRED]
- [[Default max_rounds=3 should produce up to 3 rounds.]] - `uses` [INFERRED]
- [[Empty response should return empty list.]] - `uses` [INFERRED]
- [[High confidence → should NOT spar.]] - `uses` [INFERRED]
- [[If generate_fn fails, return the best available solution.]] - `uses` [INFERRED]
- [[Labeled issues (Issue, Bug, Error) should be extracted.]] - `uses` [INFERRED]
- [[Low confidence + code task → should spar.]] - `uses` [INFERRED]
- [[Math task with low confidence → should spar.]] - `uses` [INFERRED]
- [[Mixed numberedbulletlabeled formats should all be extracted.]] - `uses` [INFERRED]
- [[No initial_solution → solver generates from scratch.]] - `uses` [INFERRED]
- [[No issues found' should return empty list.]] - `uses` [INFERRED]
- [[None generate_fn should handle gracefully.]] - `uses` [INFERRED]
- [[Numbered lists should be parsed into individual issues.]] - `uses` [INFERRED]
- [[One round of solver-critic exchange.]] - `rationale_for` [EXTRACTED]
- [[Only issues from rounds where solver_addressed=True should be stored.]] - `uses` [INFERRED]
- [[Providing initial_solution should pass it to solver.]] - `uses` [INFERRED]
- [[Security task with low confidence → should spar.]] - `uses` [INFERRED]
- [[Simple greeting → should NOT spar.]] - `uses` [INFERRED]
- [[Solver and critic should be called in alternating order.]] - `uses` [INFERRED]
- [[Solver's prompt in round 2+ should contain critic's issues.]] - `uses` [INFERRED]
- [[Stats should reflect actual sparring history.]] - `uses` [INFERRED]
- [[Stats with no history should return zeros.]] - `uses` [INFERRED]
- [[Stored patterns should have correct metadata fields.]] - `uses` [INFERRED]
- [[TestCriticParsing]] - `uses` [INFERRED]
- [[TestDebateFlow]] - `uses` [INFERRED]
- [[TestEdgeCases]] - `uses` [INFERRED]
- [[TestGrimoireStorage]] - `uses` [INFERRED]
- [[TestQualityMetrics]] - `uses` [INFERRED]
- [[TestShouldSpar]] - `uses` [INFERRED]
- [[Tests for Adversarial Model Sparring — Dual-Instance Debate ====================]] - `uses` [INFERRED]
- [[Tests for confidence scoring and improvement detection.]] - `uses` [INFERRED]
- [[Tests for error handling and boundary conditions.]] - `uses` [INFERRED]
- [[Tests for parse_critic_issues().]] - `uses` [INFERRED]
- [[Tests for should_spar() decision method.]] - `uses` [INFERRED]
- [[Tests for store_critique_patterns().]] - `uses` [INFERRED]
- [[Tests for the core spar() method and debate mechanics.]] - `uses` [INFERRED]
- [[adversarial_sparring.py]] - `contains` [EXTRACTED]
- [[confidence_after = confidence_before when issues were found and fixed.]] - `uses` [INFERRED]
- [[duration_seconds should be positive.]] - `uses` [INFERRED]
- [[final_solution should be the solver's most recent output.]] - `uses` [INFERRED]
- [[improved=False when sparring didn't help.]] - `uses` [INFERRED]
- [[improved=True when sparring raised confidence.]] - `uses` [INFERRED]
- [[looks good'  'correct' signals should return empty list.]] - `uses` [INFERRED]
- [[max_rounds=1 should work correctly.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Adversarial_Sparring