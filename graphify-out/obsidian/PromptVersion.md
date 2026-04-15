---
source_file: "modules\shadow\prompt_evolver.py"
type: "code"
community: "Prompt Evolution"
location: "L47"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Prompt_Evolution
---

# PromptVersion

## Connections
- [[.evolve_prompt()]] - `calls` [EXTRACTED]
- [[.get_version_history()]] - `calls` [EXTRACTED]
- [[.rollback()_1]] - `calls` [EXTRACTED]
- [[A versioned snapshot of a module's system prompt.]] - `rationale_for` [EXTRACTED]
- [[Activating a nonexistent version returns False.]] - `uses` [INFERRED]
- [[Activating a version retires the current one.]] - `uses` [INFERRED]
- [[Analysis of module with no prompt returns error.]] - `uses` [INFERRED]
- [[Compare returns correct scores and better version.]] - `uses` [INFERRED]
- [[Comparing with nonexistent version returns error.]] - `uses` [INFERRED]
- [[Create a PromptEvolver with mocked Grimoire.]] - `uses` [INFERRED]
- [[Create a PromptEvolver with temp database.]] - `uses` [INFERRED]
- [[Create a mock Grimoire that returns patterns.]] - `uses` [INFERRED]
- [[Create a temporary database path.]] - `uses` [INFERRED]
- [[Edge case and error handling tests._1]] - `uses` [INFERRED]
- [[Evolution adds patterns from Grimoire.]] - `uses` [INFERRED]
- [[Evolution removes instructions that were never referenced.]] - `uses` [INFERRED]
- [[Evolution stats with no data returns zeros.]] - `uses` [INFERRED]
- [[Evolution stats with real data returns correct values.]] - `uses` [INFERRED]
- [[Evolution with no active prompt returns None.]] - `uses` [INFERRED]
- [[Evolved prompt has 'testing' status.]] - `uses` [INFERRED]
- [[First registration creates version 1.]] - `uses` [INFERRED]
- [[Instructions never referenced are identified as unused.]] - `uses` [INFERRED]
- [[Instructions not referenced don't appear in stats.]] - `uses` [INFERRED]
- [[Instructions with high confidence are identified as effective.]] - `uses` [INFERRED]
- [[Instructions with low confidence are identified as harmful.]] - `uses` [INFERRED]
- [[Missing Grimoire patterns are identified.]] - `uses` [INFERRED]
- [[Module with no registered prompt handles gracefully.]] - `uses` [INFERRED]
- [[No evolution with empty task history.]] - `uses` [INFERRED]
- [[Recording without an active prompt returns False.]] - `uses` [INFERRED]
- [[Referenced instructions accumulate stats correctly.]] - `uses` [INFERRED]
- [[Registration for different modules is independent.]] - `uses` [INFERRED]
- [[Rollback restores the previous version.]] - `uses` [INFERRED]
- [[Rollback with no previous version returns None.]] - `uses` [INFERRED]
- [[Rollback with only one version returns None.]] - `uses` [INFERRED]
- [[SQLite database is created on initialization.]] - `uses` [INFERRED]
- [[Second registration for same module creates version 2.]] - `uses` [INFERRED]
- [[Task outcome is stored correctly.]] - `uses` [INFERRED]
- [[TestAnalysis]] - `uses` [INFERRED]
- [[TestEdgeCases_16]] - `uses` [INFERRED]
- [[TestEvolution]] - `uses` [INFERRED]
- [[TestRegistration_1]] - `uses` [INFERRED]
- [[TestScheduling]] - `uses` [INFERRED]
- [[TestTaskTracking]] - `uses` [INFERRED]
- [[TestVersionManagement]] - `uses` [INFERRED]
- [[Tests for Prompt Evolver — Dynamic System Prompt Evolution =====================]] - `uses` [INFERRED]
- [[Tests for evolution scheduling.]] - `uses` [INFERRED]
- [[Tests for prompt analysis.]] - `uses` [INFERRED]
- [[Tests for prompt evolution.]] - `uses` [INFERRED]
- [[Tests for prompt registration.]] - `uses` [INFERRED]
- [[Tests for task outcome recording.]] - `uses` [INFERRED]
- [[Tests for version activation, rollback, comparison.]] - `uses` [INFERRED]
- [[Version history is returned newest first.]] - `uses` [INFERRED]
- [[evolve_prompt returns None when no changes are needed.]] - `uses` [INFERRED]
- [[prompt_evolver.py]] - `contains` [EXTRACTED]
- [[should_evolve returns False when few tasks since last evolution.]] - `uses` [INFERRED]
- [[should_evolve returns False when no active prompt.]] - `uses` [INFERRED]
- [[should_evolve returns True when 100+ tasks recorded.]] - `uses` [INFERRED]
- [[should_evolve returns True when performance is declining.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Prompt_Evolution