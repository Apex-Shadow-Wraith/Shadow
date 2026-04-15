---
type: community
cohesion: 0.04
members: 50
---

# Model Evaluator & Nova

**Cohesion:** 0.04 - loosely connected
**Members:** 50 nodes

## Members
- [[.__init__()_37]] - code - modules\omen\model_evaluator.py
- [[.__init__()_35]] - code - modules\nova\nova.py
- [[.test_fetch_exception_raises()]] - code - tests\test_reaper_mcp.py
- [[.test_fetch_extracts_text()]] - code - tests\test_reaper_mcp.py
- [[.test_fetch_failure_returns_422()]] - code - tests\test_reaper_mcp.py
- [[.test_fetch_markdown_mode()]] - code - tests\test_reaper_mcp.py
- [[.test_fetch_missing_url_returns_422()]] - code - tests\test_reaper_mcp.py
- [[.test_fetch_passes_store_false()]] - code - tests\test_reaper_mcp.py
- [[.test_fetch_raw_mode()]] - code - tests\test_reaper_mcp.py
- [[.test_search_empty_results()_1]] - code - tests\test_reaper_mcp.py
- [[.test_search_exception_raises()]] - code - tests\test_reaper_mcp.py
- [[.test_search_missing_query_returns_422()]] - code - tests\test_reaper_mcp.py
- [[.test_search_restores_backend_after_override()]] - code - tests\test_reaper_mcp.py
- [[.test_search_returns_results()_1]] - code - tests\test_reaper_mcp.py
- [[.test_search_source_auto_default()]] - code - tests\test_reaper_mcp.py
- [[.test_search_source_parameter()]] - code - tests\test_reaper_mcp.py
- [[.test_search_with_title_url_snippet()]] - code - tests\test_reaper_mcp.py
- [[.test_server_not_initialized()]] - code - tests\test_reaper_mcp.py
- [[.test_source_brave()]] - code - tests\test_reaper_mcp.py
- [[.test_source_ddg()]] - code - tests\test_reaper_mcp.py
- [[.test_source_searxng()]] - code - tests\test_reaper_mcp.py
- [[.test_summarize_combines_sources()]] - code - tests\test_reaper_mcp.py
- [[.test_summarize_falls_back_to_snippets()]] - code - tests\test_reaper_mcp.py
- [[.test_summarize_no_results()]] - code - tests\test_reaper_mcp.py
- [[.test_summarize_respects_max_sources()]] - code - tests\test_reaper_mcp.py
- [[Backend should be restored after source override.]] - rationale - tests\test_reaper_mcp.py
- [[Create a mock Reaper instance with standard method signatures.]] - rationale - tests\test_reaper_mcp.py
- [[Create a test client with a mock Reaper.]] - rationale - tests\test_reaper_mcp.py
- [[Default source should be 'auto'.]] - rationale - tests\test_reaper_mcp.py
- [[Each result must have title, url, snippet.]] - rationale - tests\test_reaper_mcp.py
- [[Initialize the model evaluator.          Args             ollama_base_url Olla]] - rationale - modules\omen\model_evaluator.py
- [[MCP fetch should NOT store in Grimoire.]] - rationale - tests\test_reaper_mcp.py
- [[POST toolsreaper_fetch — fetch and extract from URL.]] - rationale - tests\test_reaper_mcp.py
- [[POST toolsreaper_search — web search.]] - rationale - tests\test_reaper_mcp.py
- [[POST toolsreaper_summarize — search + synthesize.]] - rationale - tests\test_reaper_mcp.py
- [[Search exceptions should propagate.]] - rationale - tests\test_reaper_mcp.py
- [[Server should return 503 if Reaper not initialized.]] - rationale - tests\test_reaper_mcp.py
- [[Source parameter should switch backend.]] - rationale - tests\test_reaper_mcp.py
- [[Test error handling on network failures._1]] - rationale - tests\test_reaper_mcp.py
- [[Test that source parameter switches between search backends.]] - rationale - tests\test_reaper_mcp.py
- [[TestErrorHandling]] - code - tests\test_reaper_mcp.py
- [[TestReaperFetch]] - code - tests\test_reaper_mcp.py
- [[TestReaperSearch]] - code - tests\test_reaper_mcp.py
- [[TestReaperSummarize]] - code - tests\test_reaper_mcp.py
- [[TestSourceSwitching]] - code - tests\test_reaper_mcp.py
- [[Tests for Reaper MCP Server. All web calls are mocked — no real network requests]] - rationale - tests\test_reaper_mcp.py
- [[When fetch_page fails, summarize from search snippets.]] - rationale - tests\test_reaper_mcp.py
- [[client()_1]] - code - tests\test_reaper_mcp.py
- [[mock_reaper()_2]] - code - tests\test_reaper_mcp.py
- [[test_reaper_mcp.py]] - code - tests\test_reaper_mcp.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Model_Evaluator_&_Nova
SORT file.name ASC
```

## Connections to other communities
- 1 edge to [[_COMMUNITY_Adversarial Sparring]]
- 1 edge to [[_COMMUNITY_Module Registry & Tools]]
- 1 edge to [[_COMMUNITY_Base Module & Apex API]]
- 1 edge to [[_COMMUNITY_Code Analyzer (Omen)]]
- 1 edge to [[_COMMUNITY_Async Task Queue]]

## Top bridge nodes
- [[client()_1]] - degree 6, connects to 2 communities
- [[.__init__()_35]] - degree 3, connects to 2 communities
- [[.__init__()_37]] - degree 3, connects to 1 community