---
source_file: "modules\cerberus\creator_override.py"
type: "code"
community: "Creator Override"
location: "L53"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Creator_Override
---

# OverrideResult

## Connections
- [[.creator_authorize()]] - `calls` [EXTRACTED]
- [[.creator_exception()]] - `calls` [EXTRACTED]
- [[After exception, the category is NOT permanently authorized.]] - `uses` [INFERRED]
- [[All defined external sources are accepted.]] - `uses` [INFERRED]
- [[Authorizations are logged with reasoning stored permanently.]] - `uses` [INFERRED]
- [[Calling exception once doesn't prevent future blocks.]] - `uses` [INFERRED]
- [[Categories with  3 exceptions are not flagged.]] - `uses` [INFERRED]
- [[Categories with = 3 exceptions are flagged for calibration.]] - `uses` [INFERRED]
- [[Cerberus — Ethics, Safety, and Accountability.]] - `uses` [INFERRED]
- [[Create a temp .env file with a known auth token.]] - `uses` [INFERRED]
- [[CreatorOverride with a known token.]] - `uses` [INFERRED]
- [[CreatorOverride with no token configured.]] - `uses` [INFERRED]
- [[Each call generates a unique blocked action ID.]] - `uses` [INFERRED]
- [[Exceptions are logged with timestamp and details.]] - `uses` [INFERRED]
- [[IDs follow the blocked-{hex} format.]] - `uses` [INFERRED]
- [[Internal modules cannot call creator_authorize.]] - `uses` [INFERRED]
- [[Internal modules cannot call creator_exception.]] - `uses` [INFERRED]
- [[Invalid auth token is rejected.]] - `uses` [INFERRED]
- [[Invalid auth token rejected for authorize.]] - `uses` [INFERRED]
- [[Invalid token fails verification.]] - `uses` [INFERRED]
- [[No exceptions = empty report.]] - `uses` [INFERRED]
- [[Report includes list of permanently authorized categories.]] - `uses` [INFERRED]
- [[Result of an override attempt.]] - `rationale_for` [EXTRACTED]
- [[TestAuthentication]] - `uses` [INFERRED]
- [[TestBlockedActionId]] - `uses` [INFERRED]
- [[TestCreatorAuthorize]] - `uses` [INFERRED]
- [[TestCreatorException]] - `uses` [INFERRED]
- [[TestFalsePositiveReport]] - `uses` [INFERRED]
- [[TestSourceValidation]] - `uses` [INFERRED]
- [[Tests for Creator Override System ==================================== Verifies]] - `uses` [INFERRED]
- [[Tests for auth token verification.]] - `uses` [INFERRED]
- [[Tests for blocked action ID generation.]] - `uses` [INFERRED]
- [[Tests for false positive tracking and reporting.]] - `uses` [INFERRED]
- [[Tests for one-time exception overrides.]] - `uses` [INFERRED]
- [[Tests for permanent authorization overrides.]] - `uses` [INFERRED]
- [[Tests that only external sources can invoke overrides.]] - `uses` [INFERRED]
- [[Tier 4 forbidden actions cannot be authorized permanently.]] - `uses` [INFERRED]
- [[Tier 4 forbidden actions cannot be overridden by exception.]] - `uses` [INFERRED]
- [[Token can be loaded from environment variable.]] - `uses` [INFERRED]
- [[Tracks exception counts per category.]] - `uses` [INFERRED]
- [[Unknown sources are rejected.]] - `uses` [INFERRED]
- [[Valid token passes verification.]] - `uses` [INFERRED]
- [[With no token configured, all overrides are rejected.]] - `uses` [INFERRED]
- [[creator_authorize permanently reclassifies a category.]] - `uses` [INFERRED]
- [[creator_authorize rejects empty reasoning.]] - `uses` [INFERRED]
- [[creator_authorize rejects whitespace-only reasoning.]] - `uses` [INFERRED]
- [[creator_exception grants a one-time pass.]] - `uses` [INFERRED]
- [[creator_override.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Creator_Override