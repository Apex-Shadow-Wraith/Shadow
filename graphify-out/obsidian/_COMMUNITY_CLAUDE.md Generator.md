---
type: community
cohesion: 0.02
members: 125
---

# CLAUDE.md Generator

**Cohesion:** 0.02 - loosely connected
**Members:** 125 nodes

## Members
- [[._count_all_tools()]] - code - modules\shadow\claudemd_generator.py
- [[._count_commits()]] - code - modules\shadow\claudemd_generator.py
- [[._count_tests()]] - code - modules\shadow\claudemd_generator.py
- [[._get_tool_count()]] - code - modules\shadow\claudemd_generator.py
- [[._git_log()]] - code - modules\shadow\claudemd_generator.py
- [[._section_coding_conventions()]] - code - modules\shadow\claudemd_generator.py
- [[._section_creator()]] - code - modules\shadow\claudemd_generator.py
- [[._section_decisions()]] - code - modules\shadow\claudemd_generator.py
- [[._section_file_structure()]] - code - modules\shadow\claudemd_generator.py
- [[._section_header()]] - code - modules\shadow\claudemd_generator.py
- [[._section_known_issues()]] - code - modules\shadow\claudemd_generator.py
- [[._section_modules()]] - code - modules\shadow\claudemd_generator.py
- [[._section_overview()]] - code - modules\shadow\claudemd_generator.py
- [[._section_recent_changes()]] - code - modules\shadow\claudemd_generator.py
- [[._section_tech_stack()]] - code - modules\shadow\claudemd_generator.py
- [[._section_test_status()]] - code - modules\shadow\claudemd_generator.py
- [[._section_testing()]] - code - modules\shadow\claudemd_generator.py
- [[._section_venv()]] - code - modules\shadow\claudemd_generator.py
- [[.generate()_1]] - code - modules\shadow\claudemd_generator.py
- [[.generate()]] - code - modules\harbinger\safety_report.py
- [[.test_blocks_populated()]] - code - tests\test_safety_report.py
- [[.test_calculation()]] - code - tests\test_safety_report.py
- [[.test_count_commits()]] - code - tests\test_claudemd_generator.py
- [[.test_count_commits_failure()]] - code - tests\test_claudemd_generator.py
- [[.test_count_tests_handles_failure()]] - code - tests\test_claudemd_generator.py
- [[.test_count_tests_handles_timeout()]] - code - tests\test_claudemd_generator.py
- [[.test_count_tests_parses_output()]] - code - tests\test_claudemd_generator.py
- [[.test_counts_by_type()]] - code - tests\test_safety_report.py
- [[.test_creates_schema()]] - code - tests\test_safety_report.py
- [[.test_creates_yaml()]] - code - tests\test_safety_report.py
- [[.test_decisions_with_grimoire()]] - code - tests\test_claudemd_generator.py
- [[.test_decisions_without_grimoire()]] - code - tests\test_claudemd_generator.py
- [[.test_generate_contains_all_sections()]] - code - tests\test_claudemd_generator.py
- [[.test_generate_contains_coding_conventions()]] - code - tests\test_claudemd_generator.py
- [[.test_generate_contains_critical_policies()]] - code - tests\test_claudemd_generator.py
- [[.test_generate_contains_module_codenames()]] - code - tests\test_claudemd_generator.py
- [[.test_generate_contains_permissions()]] - code - tests\test_claudemd_generator.py
- [[.test_generate_contains_project_header()]] - code - tests\test_claudemd_generator.py
- [[.test_generate_creates_file()]] - code - tests\test_claudemd_generator.py
- [[.test_generate_custom_output_path()]] - code - tests\test_claudemd_generator.py
- [[.test_generate_returns_absolute_path()]] - code - tests\test_claudemd_generator.py
- [[.test_git_log_handles_exception()]] - code - tests\test_claudemd_generator.py
- [[.test_git_log_handles_failure()]] - code - tests\test_claudemd_generator.py
- [[.test_git_log_parses_commits()]] - code - tests\test_claudemd_generator.py
- [[.test_grimoire_empty_results()]] - code - tests\test_claudemd_generator.py
- [[.test_grimoire_query_exception()]] - code - tests\test_claudemd_generator.py
- [[.test_known_issues_with_grimoire()]] - code - tests\test_claudemd_generator.py
- [[.test_known_issues_without_grimoire()]] - code - tests\test_claudemd_generator.py
- [[.test_only_target_date_included()]] - code - tests\test_safety_report.py
- [[.test_readable_output()]] - code - tests\test_safety_report.py
- [[.test_recent_changes_section_handles_no_git()]] - code - tests\test_claudemd_generator.py
- [[.test_recent_changes_section_uses_git_log()]] - code - tests\test_claudemd_generator.py
- [[.test_returns_zeroed_summary()]] - code - tests\test_safety_report.py
- [[.test_structure_includes_top_level()]] - code - tests\test_claudemd_generator.py
- [[.test_structure_lists_modules()]] - code - tests\test_claudemd_generator.py
- [[.test_structure_missing_modules_dir()]] - code - tests\test_claudemd_generator.py
- [[.test_structure_shows_other_dirs()]] - code - tests\test_claudemd_generator.py
- [[.test_tech_stack_shows_model_names()]] - code - tests\test_claudemd_generator.py
- [[.test_tech_stack_with_missing_models()]] - code - tests\test_claudemd_generator.py
- [[.test_triggered_above_threshold()]] - code - tests\test_safety_report.py
- [[.test_update_existing_section()]] - code - tests\test_claudemd_generator.py
- [[.test_update_nonexistent_section_appends()]] - code - tests\test_claudemd_generator.py
- [[.test_update_preserves_other_sections()]] - code - tests\test_claudemd_generator.py
- [[.test_update_when_no_file_exists()]] - code - tests\test_claudemd_generator.py
- [[.update_section()]] - code - modules\shadow\claudemd_generator.py
- [[Build a tree of modules directory.]] - rationale - modules\shadow\claudemd_generator.py
- [[Count total commits on current branch.]] - rationale - modules\shadow\claudemd_generator.py
- [[Create a minimal Shadow project tree for testing.]] - rationale - tests\test_claudemd_generator.py
- [[Daily Safety Report Generator for Cerberus audit logs.  Queries the cerberus_aud]] - rationale - modules\harbinger\safety_report.py
- [[Generate CLAUDE.md from current Shadow state.          Returns the absolute file]] - rationale - modules\shadow\claudemd_generator.py
- [[Get last N git commits.]] - rationale - modules\shadow\claudemd_generator.py
- [[If CLAUDE.md doesn't exist, update_section falls back to generate.]] - rationale - tests\test_claudemd_generator.py
- [[If modules doesn't exist, show a fallback message.]] - rationale - tests\test_claudemd_generator.py
- [[Insert audit log entries into the test database.]] - rationale - tests\test_safety_report.py
- [[Key architecture decisions from Grimoire.]] - rationale - modules\shadow\claudemd_generator.py
- [[Minimal config dict pointing at the tmp project.]] - rationale - tests\test_claudemd_generator.py
- [[Module codenames with live tool counts when available.]] - rationale - modules\shadow\claudemd_generator.py
- [[Pull unresolved bug_fix memories from Grimoire.]] - rationale - modules\shadow\claudemd_generator.py
- [[Query the audit log for date and compute all report metrics.          Args]] - rationale - modules\harbinger\safety_report.py
- [[Rough count of all tools across modules.]] - rationale - modules\shadow\claudemd_generator.py
- [[Run pytest --co -q to count discovered tests.]] - rationale - modules\shadow\claudemd_generator.py
- [[Run pytest --co -q to count tests.]] - rationale - modules\shadow\claudemd_generator.py
- [[Test _count_tests with mocked subprocess.]] - rationale - tests\test_claudemd_generator.py
- [[Test _git_log and _count_commits with mocked subprocess.]] - rationale - tests\test_claudemd_generator.py
- [[Test _section_file_structure.]] - rationale - tests\test_claudemd_generator.py
- [[Test that sections degrade gracefully without Grimoire.]] - rationale - tests\test_claudemd_generator.py
- [[TestBlocksList]] - code - tests\test_safety_report.py
- [[TestCalibrationAlerts]] - code - tests\test_safety_report.py
- [[TestDateFiltering]] - code - tests\test_safety_report.py
- [[TestEnsureTable]] - code - tests\test_safety_report.py
- [[TestFalsePositiveRate]] - code - tests\test_safety_report.py
- [[TestFileStructure]] - code - tests\test_claudemd_generator.py
- [[TestFormatForHarbinger]] - code - tests\test_safety_report.py
- [[TestGenerate]] - code - tests\test_claudemd_generator.py
- [[TestGenerateCounts]] - code - tests\test_safety_report.py
- [[TestGenerateEmptyDay]] - code - tests\test_safety_report.py
- [[TestGitLog]] - code - tests\test_claudemd_generator.py
- [[TestGrimoireFallback]] - code - tests\test_claudemd_generator.py
- [[TestSaveReport]] - code - tests\test_safety_report.py
- [[TestTechStack]] - code - tests\test_claudemd_generator.py
- [[TestTestCount]] - code - tests\test_claudemd_generator.py
- [[TestUpdateSection]] - code - tests\test_claudemd_generator.py
- [[Tests for ClaudeMDGenerator — CLAUDE.md dynamic context generator.]] - rationale - tests\test_claudemd_generator.py
- [[Tests for DailySafetyReport — Cerberus audit log reporting.]] - rationale - tests\test_safety_report.py
- [[Tests for the full generate() method.]] - rationale - tests\test_claudemd_generator.py
- [[Tests for update_section().]] - rationale - tests\test_claudemd_generator.py
- [[Try to count tools for a module by inspecting get_tools().]] - rationale - modules\shadow\claudemd_generator.py
- [[Update just one section of existing CLAUDE.md without regenerating everything.]] - rationale - modules\shadow\claudemd_generator.py
- [[Verify tech stack section pulls from config.]] - rationale - tests\test_claudemd_generator.py
- [[_collect_auto_registrations()]] - code - modules\harbinger\safety_report.py
- [[_collect_blocks()]] - code - modules\harbinger\safety_report.py
- [[_compute_calibration_alerts()]] - code - modules\harbinger\safety_report.py
- [[_compute_false_positive_rate()]] - code - modules\harbinger\safety_report.py
- [[_compute_summary()]] - code - modules\harbinger\safety_report.py
- [[_detect_anomalies()]] - code - modules\harbinger\safety_report.py
- [[_ensure_table()]] - code - modules\harbinger\safety_report.py
- [[_insert_entries()]] - code - tests\test_safety_report.py
- [[config()_1]] - code - tests\test_claudemd_generator.py
- [[format_for_harbinger()]] - code - modules\harbinger\safety_report.py
- [[generator()]] - code - tests\test_claudemd_generator.py
- [[safety_report.py]] - code - modules\harbinger\safety_report.py
- [[save_report()]] - code - modules\harbinger\safety_report.py
- [[test_claudemd_generator.py]] - code - tests\test_claudemd_generator.py
- [[test_safety_report.py]] - code - tests\test_safety_report.py
- [[tmp_project()]] - code - tests\test_claudemd_generator.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/CLAUDE.md_Generator
SORT file.name ASC
```

## Connections to other communities
- 47 edges to [[_COMMUNITY_Async Task Queue]]
- 23 edges to [[_COMMUNITY_Base Module & Apex API]]
- 6 edges to [[_COMMUNITY_Module Lifecycle]]
- 4 edges to [[_COMMUNITY_Data Pipeline & Embeddings]]
- 2 edges to [[_COMMUNITY_Cross-Reference & Security]]
- 2 edges to [[_COMMUNITY_Module Registry & Tools]]
- 1 edge to [[_COMMUNITY_Adversarial Sparring]]

## Top bridge nodes
- [[.generate()_1]] - degree 39, connects to 3 communities
- [[.generate()]] - degree 11, connects to 3 communities
- [[_insert_entries()]] - degree 11, connects to 2 communities
- [[.update_section()]] - degree 9, connects to 2 communities
- [[._section_known_issues()]] - degree 8, connects to 2 communities