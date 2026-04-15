---
type: community
cohesion: 0.05
members: 72
---

# Embedding Router

**Cohesion:** 0.05 - loosely connected
**Members:** 72 nodes

## Members
- [[.__init__()_17]] - code - modules\grimoire\embedding_router.py
- [[.classify_query()]] - code - modules\grimoire\embedding_router.py
- [[.get_all_collections_for_search()]] - code - modules\grimoire\embedding_router.py
- [[.get_collection_name()]] - code - modules\grimoire\embedding_router.py
- [[.get_embedding_model()]] - code - modules\grimoire\embedding_router.py
- [[.get_routing_stats()]] - code - modules\grimoire\embedding_router.py
- [[.route_for_storage()]] - code - modules\grimoire\embedding_router.py
- [[.route_query()]] - code - modules\grimoire\embedding_router.py
- [[.search_routed()]] - code - modules\grimoire\grimoire_module.py
- [[.setup_method()]] - code - tests\test_embedding_router.py
- [[.setup_method()_3]] - code - tests\test_embedding_router.py
- [[.setup_method()_2]] - code - tests\test_embedding_router.py
- [[.setup_method()_1]] - code - tests\test_embedding_router.py
- [[.test_business_keyword_invoice()]] - code - tests\test_embedding_router.py
- [[.test_business_keyword_schedule()]] - code - tests\test_embedding_router.py
- [[.test_classifies_from_content_when_no_domain_tags()]] - code - tests\test_embedding_router.py
- [[.test_classifies_from_content_when_no_metadata()]] - code - tests\test_embedding_router.py
- [[.test_code_keyword_bug()]] - code - tests\test_embedding_router.py
- [[.test_code_keyword_def()]] - code - tests\test_embedding_router.py
- [[.test_code_keyword_import()]] - code - tests\test_embedding_router.py
- [[.test_code_keyword_sql()]] - code - tests\test_embedding_router.py
- [[.test_collection_name_code()]] - code - tests\test_embedding_router.py
- [[.test_collection_name_default()]] - code - tests\test_embedding_router.py
- [[.test_collection_name_unknown_domain()]] - code - tests\test_embedding_router.py
- [[.test_custom_config()_1]] - code - tests\test_embedding_router.py
- [[.test_default_config_has_all_domains()]] - code - tests\test_embedding_router.py
- [[.test_empty_query()]] - code - tests\test_embedding_router.py
- [[.test_get_all_collections()]] - code - tests\test_embedding_router.py
- [[.test_mixed_content_code_dominant()]] - code - tests\test_embedding_router.py
- [[.test_natural_language_default()]] - code - tests\test_embedding_router.py
- [[.test_route_business_query()]] - code - tests\test_embedding_router.py
- [[.test_route_code_query()]] - code - tests\test_embedding_router.py
- [[.test_route_natural_language_query()]] - code - tests\test_embedding_router.py
- [[.test_route_unknown_domain_fallback()]] - code - tests\test_embedding_router.py
- [[.test_search_routed_calls_router()]] - code - tests\test_embedding_router.py
- [[.test_search_routed_falls_back_to_base()]] - code - tests\test_embedding_router.py
- [[.test_search_routed_without_router()]] - code - tests\test_embedding_router.py
- [[.test_stats_empty_initially()]] - code - tests\test_embedding_router.py
- [[.test_stats_track_per_domain()]] - code - tests\test_embedding_router.py
- [[.test_update_routing_config()]] - code - tests\test_embedding_router.py
- [[.test_uses_metadata_domain_tags()]] - code - tests\test_embedding_router.py
- [[.test_uses_metadata_domain_tags_list()]] - code - tests\test_embedding_router.py
- [[.test_very_short_query()]] - code - tests\test_embedding_router.py
- [[.test_whitespace_only_query()]] - code - tests\test_embedding_router.py
- [[.update_routing_config()]] - code - modules\grimoire\embedding_router.py
- [[Classify, get model, get collection — all in one call.]] - rationale - modules\grimoire\embedding_router.py
- [[Determine which collection to store content in.]] - rationale - modules\grimoire\embedding_router.py
- [[Determine which domain a query belongs to using rule-based classification.]] - rationale - modules\grimoire\embedding_router.py
- [[Embedding Router — Domain-Specific Embedding Routing for Grimoire ==============]] - rationale - modules\grimoire\embedding_router.py
- [[EmbeddingRouter]] - code - modules\grimoire\embedding_router.py
- [[GrimoireModule.search_routed should use the embedding router.]] - rationale - tests\test_embedding_router.py
- [[Return all domain-specific collection names for broad searches.]] - rationale - modules\grimoire\embedding_router.py
- [[Return domain-specific collection name with suffix applied.]] - rationale - modules\grimoire\embedding_router.py
- [[Return queries routed per domain and model usage distribution.]] - rationale - modules\grimoire\embedding_router.py
- [[Return the embedding model name for a domain, falling back to default.]] - rationale - modules\grimoire\embedding_router.py
- [[Route Grimoire queries to domain-specific embedding models and collections.]] - rationale - modules\grimoire\embedding_router.py
- [[TestClassifyQuery]] - code - tests\test_embedding_router.py
- [[TestCollections]] - code - tests\test_embedding_router.py
- [[TestConfiguration]] - code - tests\test_embedding_router.py
- [[TestGrimoireIntegration_1]] - code - tests\test_embedding_router.py
- [[TestRouteForStorage]] - code - tests\test_embedding_router.py
- [[TestRouteQuery]] - code - tests\test_embedding_router.py
- [[TestRoutingStats]] - code - tests\test_embedding_router.py
- [[Tests for Embedding Router — Domain-Specific Embedding Routing =================]] - rationale - tests\test_embedding_router.py
- [[Unknown domain falls back to default (no suffix).]] - rationale - tests\test_embedding_router.py
- [[Update routing for a domain (e.g., swap in a code-optimized model).]] - rationale - modules\grimoire\embedding_router.py
- [[When code keywords outnumber business keywords, classify as code.]] - rationale - tests\test_embedding_router.py
- [[When domain-specific collection returns nothing, fall back to base.]] - rationale - tests\test_embedding_router.py
- [[embedding_router.py]] - code - modules\grimoire\embedding_router.py
- [[get_embedding_model falls back to default for unknown domains.]] - rationale - tests\test_embedding_router.py
- [[search_routed without a router falls back to regular recall.]] - rationale - tests\test_embedding_router.py
- [[test_embedding_router.py]] - code - tests\test_embedding_router.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Embedding_Router
SORT file.name ASC
```

## Connections to other communities
- 25 edges to [[_COMMUNITY_Module Registry & Tools]]
- 9 edges to [[_COMMUNITY_Base Module & Apex API]]
- 2 edges to [[_COMMUNITY_Cross-Reference & Security]]

## Top bridge nodes
- [[EmbeddingRouter]] - degree 46, connects to 3 communities
- [[.search_routed()]] - degree 7, connects to 3 communities
- [[TestClassifyQuery]] - degree 15, connects to 1 community
- [[.route_for_storage()]] - degree 10, connects to 1 community
- [[TestCollections]] - degree 8, connects to 1 community