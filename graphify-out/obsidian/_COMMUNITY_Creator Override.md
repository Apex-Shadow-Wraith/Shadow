---
type: community
cohesion: 0.04
members: 94
---

# Creator Override

**Cohesion:** 0.04 - loosely connected
**Members:** 94 nodes

## Members
- [[TODO Phase 2 — add cryptographic device signatures]] - rationale - modules\cerberus\creator_override.py
- [[TODO Phase 3 — add Face ID verification for creator_authorize]] - rationale - modules\cerberus\creator_override.py
- [[._is_tier_4_forbidden()]] - code - modules\cerberus\creator_override.py
- [[._validate_source()]] - code - modules\cerberus\creator_override.py
- [[.creator_authorize()]] - code - modules\cerberus\creator_override.py
- [[.creator_exception()]] - code - modules\cerberus\creator_override.py
- [[.get_false_positive_report()]] - code - modules\cerberus\creator_override.py
- [[.is_category_authorized()]] - code - modules\cerberus\creator_override.py
- [[.test_authorize_internal_module_rejected()]] - code - tests\test_creator_override.py
- [[.test_authorize_invalid_token()]] - code - tests\test_creator_override.py
- [[.test_authorize_logged_with_reasoning()]] - code - tests\test_creator_override.py
- [[.test_authorize_requires_nonempty_reasoning()]] - code - tests\test_creator_override.py
- [[.test_authorize_requires_reasoning()]] - code - tests\test_creator_override.py
- [[.test_authorize_tier4_forbidden()]] - code - tests\test_creator_override.py
- [[.test_authorize_updates_permanently()]] - code - tests\test_creator_override.py
- [[.test_counts_exceptions_per_category()]] - code - tests\test_creator_override.py
- [[.test_empty_report()_1]] - code - tests\test_creator_override.py
- [[.test_env_var_fallback()]] - code - tests\test_creator_override.py
- [[.test_exception_allows_one_time()]] - code - tests\test_creator_override.py
- [[.test_exception_blocks_next_time()]] - code - tests\test_creator_override.py
- [[.test_exception_does_not_learn()]] - code - tests\test_creator_override.py
- [[.test_exception_internal_module_rejected()]] - code - tests\test_creator_override.py
- [[.test_exception_invalid_token()]] - code - tests\test_creator_override.py
- [[.test_exception_logged()]] - code - tests\test_creator_override.py
- [[.test_exception_tier4_forbidden()]] - code - tests\test_creator_override.py
- [[.test_external_sources_accepted()]] - code - tests\test_creator_override.py
- [[.test_flags_frequent_categories()]] - code - tests\test_creator_override.py
- [[.test_generates_unique_ids()]] - code - tests\test_creator_override.py
- [[.test_id_format()]] - code - tests\test_creator_override.py
- [[.test_no_token_configured_rejects_all()]] - code - tests\test_creator_override.py
- [[.test_report_includes_authorized_categories()]] - code - tests\test_creator_override.py
- [[.test_unflagged_low_count()]] - code - tests\test_creator_override.py
- [[.test_unknown_source_rejected()]] - code - tests\test_creator_override.py
- [[.test_verify_hardware_auth_invalid()]] - code - tests\test_creator_override.py
- [[.test_verify_hardware_auth_valid()]] - code - tests\test_creator_override.py
- [[.verify_hardware_auth()]] - code - modules\cerberus\creator_override.py
- [[After exception, the category is NOT permanently authorized.]] - rationale - tests\test_creator_override.py
- [[All defined external sources are accepted.]] - rationale - tests\test_creator_override.py
- [[Authorizations are logged with reasoning stored permanently.]] - rationale - tests\test_creator_override.py
- [[Calling exception once doesn't prevent future blocks.]] - rationale - tests\test_creator_override.py
- [[Categories with  3 exceptions are not flagged.]] - rationale - tests\test_creator_override.py
- [[Categories with = 3 exceptions are flagged for calibration.]] - rationale - tests\test_creator_override.py
- [[Check if a category has been permanently authorized by the creator.]] - rationale - modules\cerberus\creator_override.py
- [[Check if the action falls under Tier 4 forbidden — no override possible.]] - rationale - modules\cerberus\creator_override.py
- [[Create a temp .env file with a known auth token.]] - rationale - tests\test_creator_override.py
- [[Creator Override System ======================== When Cerberus blocks an action,]] - rationale - modules\cerberus\creator_override.py
- [[CreatorOverride with a known token.]] - rationale - tests\test_creator_override.py
- [[CreatorOverride with no token configured.]] - rationale - tests\test_creator_override.py
- [[Each call generates a unique blocked action ID.]] - rationale - tests\test_creator_override.py
- [[Exceptions are logged with timestamp and details.]] - rationale - tests\test_creator_override.py
- [[IDs follow the blocked-{hex} format.]] - rationale - tests\test_creator_override.py
- [[Internal modules cannot call creator_authorize.]] - rationale - tests\test_creator_override.py
- [[Internal modules cannot call creator_exception.]] - rationale - tests\test_creator_override.py
- [[Invalid auth token is rejected.]] - rationale - tests\test_creator_override.py
- [[Invalid auth token rejected for authorize.]] - rationale - tests\test_creator_override.py
- [[Invalid token fails verification.]] - rationale - tests\test_creator_override.py
- [[No exceptions = empty report.]] - rationale - tests\test_creator_override.py
- [[One-time exception. Action executes THIS TIME ONLY.          Cerberus does NOT l]] - rationale - modules\cerberus\creator_override.py
- [[OverrideResult]] - code - modules\cerberus\creator_override.py
- [[Permanent authorization. Cerberus LEARNS from this.          The category is rec]] - rationale - modules\cerberus\creator_override.py
- [[Reject calls from internal modules. Only external sources allowed.]] - rationale - modules\cerberus\creator_override.py
- [[Report includes list of permanently authorized categories.]] - rationale - tests\test_creator_override.py
- [[Report on categories with frequent creator exceptions.          Categories with]] - rationale - modules\cerberus\creator_override.py
- [[Result of an override attempt.]] - rationale - modules\cerberus\creator_override.py
- [[TestAuthentication]] - code - tests\test_creator_override.py
- [[TestBlockedActionId]] - code - tests\test_creator_override.py
- [[TestCreatorAuthorize]] - code - tests\test_creator_override.py
- [[TestCreatorException]] - code - tests\test_creator_override.py
- [[TestFalsePositiveReport]] - code - tests\test_creator_override.py
- [[TestSourceValidation]] - code - tests\test_creator_override.py
- [[Tests for Creator Override System ==================================== Verifies]] - rationale - tests\test_creator_override.py
- [[Tests for auth token verification.]] - rationale - tests\test_creator_override.py
- [[Tests for blocked action ID generation.]] - rationale - tests\test_creator_override.py
- [[Tests for false positive tracking and reporting.]] - rationale - tests\test_creator_override.py
- [[Tests for one-time exception overrides.]] - rationale - tests\test_creator_override.py
- [[Tests for permanent authorization overrides.]] - rationale - tests\test_creator_override.py
- [[Tests that only external sources can invoke overrides.]] - rationale - tests\test_creator_override.py
- [[Tier 4 forbidden actions cannot be authorized permanently.]] - rationale - tests\test_creator_override.py
- [[Tier 4 forbidden actions cannot be overridden by exception.]] - rationale - tests\test_creator_override.py
- [[Token can be loaded from environment variable.]] - rationale - tests\test_creator_override.py
- [[Tracks exception counts per category.]] - rationale - tests\test_creator_override.py
- [[Unknown sources are rejected.]] - rationale - tests\test_creator_override.py
- [[Valid token passes verification.]] - rationale - tests\test_creator_override.py
- [[Verify creator authentication token.          Phase 1 Simple token comparison a]] - rationale - modules\cerberus\creator_override.py
- [[With no token configured, all overrides are rejected.]] - rationale - tests\test_creator_override.py
- [[creator_authorize permanently reclassifies a category.]] - rationale - tests\test_creator_override.py
- [[creator_authorize rejects empty reasoning.]] - rationale - tests\test_creator_override.py
- [[creator_authorize rejects whitespace-only reasoning.]] - rationale - tests\test_creator_override.py
- [[creator_exception grants a one-time pass.]] - rationale - tests\test_creator_override.py
- [[creator_override.py]] - code - modules\cerberus\creator_override.py
- [[env_file()]] - code - tests\test_creator_override.py
- [[override()]] - code - tests\test_creator_override.py
- [[override_no_token()]] - code - tests\test_creator_override.py
- [[test_creator_override.py]] - code - tests\test_creator_override.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Creator_Override
SORT file.name ASC
```

## Connections to other communities
- 60 edges to [[_COMMUNITY_Base Module & Apex API]]
- 2 edges to [[_COMMUNITY_Module Lifecycle]]
- 1 edge to [[_COMMUNITY_Ethics Engine (Cerberus)]]

## Top bridge nodes
- [[.creator_exception()]] - degree 21, connects to 2 communities
- [[.creator_authorize()]] - degree 16, connects to 2 communities
- [[OverrideResult]] - degree 48, connects to 1 community
- [[TestCreatorAuthorize]] - degree 11, connects to 1 community
- [[TestCreatorException]] - degree 11, connects to 1 community