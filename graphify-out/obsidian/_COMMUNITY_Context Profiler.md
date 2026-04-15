---
type: community
cohesion: 0.07
members: 66
---

# Context Profiler

**Cohesion:** 0.07 - loosely connected
**Members:** 66 nodes

## Members
- [[._get_conn()]] - code - modules\shadow\context_profiler.py
- [[._insert_profiles()]] - code - tests\test_context_profiler.py
- [[._insert_wasteful_profiles()]] - code - tests\test_context_profiler.py
- [[.get_component_breakdown()]] - code - modules\shadow\context_profiler.py
- [[.get_optimization_suggestions()]] - code - modules\shadow\context_profiler.py
- [[.get_profile_count()]] - code - modules\shadow\context_profiler.py
- [[.get_usage_trend()]] - code - modules\shadow\context_profiler.py
- [[.get_waste_report()]] - code - modules\shadow\context_profiler.py
- [[.record_from_context_package()]] - code - modules\shadow\context_profiler.py
- [[.record_profile()]] - code - modules\shadow\context_profiler.py
- [[.test_auto_calculates_grimoire_referenced()]] - code - tests\test_context_profiler.py
- [[.test_auto_calculates_tool_usage_from_response()]] - code - tests\test_context_profiler.py
- [[.test_averages_calculated_correctly()]] - code - tests\test_context_profiler.py
- [[.test_calculates_unused_grimoire_tokens()]] - code - tests\test_context_profiler.py
- [[.test_calculates_unused_tool_tokens()]] - code - tests\test_context_profiler.py
- [[.test_empty_db_returns_empty()]] - code - tests\test_context_profiler.py
- [[.test_empty_db_returns_valid_structure()]] - code - tests\test_context_profiler.py
- [[.test_empty_db_returns_valid_zeros()]] - code - tests\test_context_profiler.py
- [[.test_extracts_correct_token_counts()]] - code - tests\test_context_profiler.py
- [[.test_frequent_trimming_suggests_compression()]] - code - tests\test_context_profiler.py
- [[.test_generates_plain_english_summary()]] - code - tests\test_context_profiler.py
- [[.test_graceful_handling_of_malformed_package()]] - code - tests\test_context_profiler.py
- [[.test_high_grimoire_waste_suggests_retrieval_tightening()]] - code - tests\test_context_profiler.py
- [[.test_high_history_suggests_compression()]] - code - tests\test_context_profiler.py
- [[.test_high_tool_waste_suggests_tool_filtering()]] - code - tests\test_context_profiler.py
- [[.test_identifies_biggest_waste_component()]] - code - tests\test_context_profiler.py
- [[.test_includes_percentages()]] - code - tests\test_context_profiler.py
- [[.test_no_issues_returns_empty()]] - code - tests\test_context_profiler.py
- [[.test_profile_count_increases()]] - code - tests\test_context_profiler.py
- [[.test_profile_count_starts_at_zero()]] - code - tests\test_context_profiler.py
- [[.test_record_assigns_id_if_missing()]] - code - tests\test_context_profiler.py
- [[.test_record_stores_to_sqlite()]] - code - tests\test_context_profiler.py
- [[.test_respects_day_range()]] - code - tests\test_context_profiler.py
- [[.test_returns_daily_data_points()]] - code - tests\test_context_profiler.py
- [[.test_returns_per_component_averages()]] - code - tests\test_context_profiler.py
- [[.test_sqlite_db_created_on_init()]] - code - tests\test_context_profiler.py
- [[.test_trim_frequency()]] - code - tests\test_context_profiler.py
- [[.test_usage_percent_auto_calculated()]] - code - tests\test_context_profiler.py
- [[Analyse profiles over the period and identify waste patterns.]] - rationale - modules\shadow\context_profiler.py
- [[Average token allocation per component with percentages and trends.]] - rationale - modules\shadow\context_profiler.py
- [[Build a ContextProfile from a ContextPackage and record it.          Auto-calcul]] - rationale - modules\shadow\context_profiler.py
- [[Context Window Profiler — Diagnostic Tool for LLM Context Usage ================]] - rationale - modules\shadow\context_profiler.py
- [[ContextProfile]] - code - modules\shadow\context_profiler.py
- [[Fresh profiler with a temporary database.]] - rationale - tests\test_context_profiler.py
- [[Helper to insert multiple profiles with defaults.]] - rationale - tests\test_context_profiler.py
- [[Insert profiles that trigger specific suggestions.]] - rationale - tests\test_context_profiler.py
- [[Profiler should not crash on a package missing expected attributes.]] - rationale - tests\test_context_profiler.py
- [[Return a new connection with row_factory set.]] - rationale - modules\shadow\context_profiler.py
- [[Returns a ContextProfile with realistic values.]] - rationale - tests\test_context_profiler.py
- [[Rule-based suggestions derived from the waste report.]] - rationale - modules\shadow\context_profiler.py
- [[Store a ContextProfile in SQLite. Returns the profile_id.]] - rationale - modules\shadow\context_profiler.py
- [[TestComponentBreakdown]] - code - tests\test_context_profiler.py
- [[TestDBCreation]] - code - tests\test_context_profiler.py
- [[TestOptimizationSuggestions]] - code - tests\test_context_profiler.py
- [[TestRecordFromContextPackage]] - code - tests\test_context_profiler.py
- [[TestRecordProfile]] - code - tests\test_context_profiler.py
- [[TestUsageTrend]] - code - tests\test_context_profiler.py
- [[TestWasteReport]] - code - tests\test_context_profiler.py
- [[Tests for modulesshadowcontext_profiler.py — Context Window Profiler.]] - rationale - tests\test_context_profiler.py
- [[Token usage over time for dashboards  briefings.          Returns {date, avg_t]] - rationale - modules\shadow\context_profiler.py
- [[Token-level snapshot of a single LLM call's context window.]] - rationale - modules\shadow\context_profiler.py
- [[Total number of profiles stored.]] - rationale - modules\shadow\context_profiler.py
- [[context_profiler.py]] - code - modules\shadow\context_profiler.py
- [[profiler()]] - code - tests\test_context_profiler.py
- [[sample_profile()]] - code - tests\test_context_profiler.py
- [[test_context_profiler.py]] - code - tests\test_context_profiler.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Context_Profiler
SORT file.name ASC
```

## Connections to other communities
- 24 edges to [[_COMMUNITY_Async Task Queue]]
- 5 edges to [[_COMMUNITY_Data Pipeline & Embeddings]]
- 1 edge to [[_COMMUNITY_Base Module & Apex API]]

## Top bridge nodes
- [[.record_profile()]] - degree 18, connects to 2 communities
- [[.get_waste_report()]] - degree 13, connects to 2 communities
- [[.get_profile_count()]] - degree 10, connects to 2 communities
- [[.record_from_context_package()]] - degree 9, connects to 2 communities
- [[.get_component_breakdown()]] - degree 8, connects to 2 communities