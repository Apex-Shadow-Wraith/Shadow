---
type: community
cohesion: 0.07
members: 42
---

# CLI Input & Fuzzy Match

**Cohesion:** 0.07 - loosely connected
**Members:** 42 nodes

## Members
- [[.test_all_known_commands_match_exactly()]] - code - tests\test_cli_input.py
- [[.test_clean_input_unchanged()]] - code - tests\test_cli_input.py
- [[.test_double_slash()]] - code - tests\test_cli_input.py
- [[.test_empty_string()]] - code - tests\test_cli_input.py
- [[.test_exact_match()]] - code - tests\test_cli_input.py
- [[.test_gin_garbage_with_spaces()]] - code - tests\test_cli_input.py
- [[.test_gin_log_prefix()]] - code - tests\test_cli_input.py
- [[.test_leading_whitespace()]] - code - tests\test_cli_input.py
- [[.test_no_match_empty()]] - code - tests\test_cli_input.py
- [[.test_no_match_gibberish()]] - code - tests\test_cli_input.py
- [[.test_only_slashes()]] - code - tests\test_cli_input.py
- [[.test_plain_text_no_slash()]] - code - tests\test_cli_input.py
- [[.test_quit_with_garbage()]] - code - tests\test_cli_input.py
- [[.test_random_prefix_chars()]] - code - tests\test_cli_input.py
- [[.test_slash_quit_with_garbage()]] - code - tests\test_cli_input.py
- [[.test_triple_slash()]] - code - tests\test_cli_input.py
- [[.test_typo_failuers()]] - code - tests\test_cli_input.py
- [[.test_typo_historry()]] - code - tests\test_cli_input.py
- [[.test_typo_hlep()]] - code - tests\test_cli_input.py
- [[.test_typo_quiit()]] - code - tests\test_cli_input.py
- [[.test_typo_satus()]] - code - tests\test_cli_input.py
- [[.test_typo_taks()]] - code - tests\test_cli_input.py
- [[.test_typo_takss()]] - code - tests\test_cli_input.py
- [[.test_whitespace_only()]] - code - tests\test_cli_input.py
- [[GIN-polluted quit should sanitize to quit.]] - rationale - tests\test_cli_input.py
- [[Non-command input should pass through stripped.]] - rationale - tests\test_cli_input.py
- [[Plain 'quit' preceded by garbage — no slash, so just strips.]] - rationale - tests\test_cli_input.py
- [[Simulates Ollama GIN debug output bleeding into the buffer.]] - rationale - tests\test_cli_input.py
- [[TestFuzzyMatchCommand]] - code - tests\test_cli_input.py
- [[TestQuitDetection]] - code - tests\test_cli_input.py
- [[TestSanitizeInput]] - code - tests\test_cli_input.py
- [[TestTaskCommand]] - code - tests\test_cli_input.py
- [[Tests for CLI input sanitization, fuzzy command matching, and quit handling.  Co]] - rationale - tests\test_cli_input.py
- [[Verify that task id is handled by handle_command.]] - rationale - tests\test_cli_input.py
- [[Verify that GIN noise and leading garbage are stripped.]] - rationale - tests\test_cli_input.py
- [[Verify that quit variants are caught before orchestrator.]] - rationale - tests\test_cli_input.py
- [[Verify that typos resolve to the correct command.]] - rationale - tests\test_cli_input.py
- [[fuzzy_match_command()]] - code - main.py
- [[sanitize_input()]] - code - main.py
- [[test_cli_input.py]] - code - tests\test_cli_input.py
- [[test_quit_variants_detected()]] - code - tests\test_cli_input.py
- [[test_task_command_recognized()]] - code - tests\test_cli_input.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/CLI_Input_&_Fuzzy_Match
SORT file.name ASC
```

## Connections to other communities
- 6 edges to [[_COMMUNITY_Module Registry & Tools]]
- 1 edge to [[_COMMUNITY_Adversarial Sparring]]
- 1 edge to [[_COMMUNITY_Introspection Dashboard]]
- 1 edge to [[_COMMUNITY_Async Task Queue]]

## Top bridge nodes
- [[sanitize_input()]] - degree 19, connects to 3 communities
- [[fuzzy_match_command()]] - degree 14, connects to 1 community
- [[test_task_command_recognized()]] - degree 2, connects to 1 community