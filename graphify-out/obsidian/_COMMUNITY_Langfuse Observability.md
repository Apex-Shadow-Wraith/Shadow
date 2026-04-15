---
type: community
cohesion: 0.25
members: 8
---

# Langfuse Observability

**Cohesion:** 0.25 - loosely connected
**Members:** 8 nodes

## Members
- [[Decorator for Orchestrator.process_input().      Emits a Langfuse trace with inp]] - rationale - modules\shadow\observability.py
- [[Return a Langfuse client if credentials are configured, else None.]] - rationale - modules\shadow\observability.py
- [[Shadow Observability — Langfuse Tracing ========================================]] - rationale - modules\shadow\observability.py
- [[Without env vars, _get_langfuse_client returns None.]] - rationale - tests\test_observability.py
- [[_get_langfuse_client()]] - code - modules\shadow\observability.py
- [[observability.py]] - code - modules\shadow\observability.py
- [[test_get_langfuse_client_returns_none_without_keys()]] - code - tests\test_observability.py
- [[trace_interaction()]] - code - modules\shadow\observability.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Langfuse_Observability
SORT file.name ASC
```

## Connections to other communities
- 1 edge to [[_COMMUNITY_Module Registry & Tools]]

## Top bridge nodes
- [[test_get_langfuse_client_returns_none_without_keys()]] - degree 3, connects to 1 community