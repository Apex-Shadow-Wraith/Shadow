# Commit 11 Sweep Diff — Master Review

**Status:** read-only inspection. No changes applied yet. Master
reviews this document, approves specific applications, and only then
the sweep executes (still scoped to commit 11).

Branch: `phase-a/sentinel-into-cerberus` at HEAD = commit 10
(`8974711` docs(phase-a): Sentinel→Cerberus tool inventory + diff).

## Current rg state

Baseline (pre-merge): 401 hits across 64 files (planning addendum 3).
After commits 1–10: rg over the working tree finds **49 files** with
`sentinel` references. Categorized below by addendum-3 bucket; the
default sweep applies only buckets A and B; buckets C and D are
preserved or flagged for Master review.

## Bucket A — REMOVE (default rules apply)

These have **already been removed** by commits 7, 8, and 9. Final
deletion in commit 11:

| Path | What gets deleted |
| --- | --- |
| `modules/sentinel/` (entire directory) | `sentinel.py`, `security_analyzer.py`, `threat_intelligence.py`, `config.py`, `__init__.py`, `__pycache__/` |

The whole-directory delete is the only behavioral change pending in
commit 11. Everything else has already shifted to bucket-A-clean
state.

## Bucket B — PORT + REMAP (already complete, commit 9)

`tests/test_sentinel.py`, `tests/test_sentinel_tool_selection.py`,
`tests/test_security_analyzer.py`, `tests/test_threat_intelligence.py`
were deleted and replaced by their `tests/test_cerberus_security*.py`
ports. No further sweep action.

## Bucket C — PRESERVE (default rule: leave alone)

Comment / breadcrumb references documenting the absorption. The
sweep does **not** touch these. Listed for transparency:

| Path | Hits | Why preserved |
| --- | ---: | --- |
| `plan.md` | 65 | Multi-session planning record (Cipher, Sentinel, Void merges). |
| `docs/phase-a/sentinel-cerberus/tool_diff.md` | 19 | This merge's own audit document. |
| `docs/phase-a/sentinel-cerberus/sweep_diff.md` | this file | Self-reference. |
| `docs/phase-a/void/pre_merge_tools.json` | 1 | Sibling merge's pre-merge inventory snapshot. |
| `docs/phase-a/void/post_merge_tools.json` | 1 | Sibling merge's post-merge inventory snapshot. |
| `docs/phase-a/void/regression_investigation.md` | 2 | Sibling merge's investigation record. |
| `modules/grimoire/grimoire.py:106` | 3 | `VALID_SOURCE_MODULES` retains "sentinel" for queryable historical entries (addendum 2 (b)). The new "cerberus.security" was added next to it. |
| `benchmarks/benchmark_2026-04-19.json` | 3 | Pre-merge benchmark artifact (frozen routing expectations). |
| `benchmarks/benchmark_2026-04-19_2.json` | 6 | Same. |
| `benchmarks/benchmark_2026-04-24.json` | 9 | Same. |
| `benchmarks/benchmark_tasks.json` | 1 | Same. |
| `modules/cerberus/security/__init__.py` | 1 | Subpackage docstring describing the absorption. |
| `modules/cerberus/security/core.py` | 10 | Module/class docstring + helpful internal comments noting historical lineage and the kept `data/sentinel_baseline.json` filename. |
| `modules/cerberus/security/analyzer.py` | 2 | Docstring header noting absorption. |
| `modules/cerberus/security/threat_intelligence.py` | 3 | Docstring header noting absorption. |
| `modules/cerberus/cerberus.py` | 4 | Inline comments documenting the absorption inside `__init__`, `execute()`, `get_tools()`. |
| `modules/cerberus/config.py` | 5 | `CerberusSecuritySettings` docstring explaining the kept baseline path. |
| `modules/shadow/proactive_engine.py` | 2 | Section comments noting absorption (waterfall + triggers). |
| `modules/shadow/task_chain.py` | 1 | Inline comment in `keyword_map`. |
| `modules/shadow/tool_loader.py` | 1 | Inline comment on `_CROSS_MODULE_KEYWORDS["cerberus"]`. |
| `modules/shadow/drift_detector.py` | 1 | Inline comment on the cerberus role/should_handle list. |
| `modules/shadow/orchestrator.py` | 2 | Two `# Cerberus security surface (absorbed from Sentinel, Phase A)` comments above the two security-keyword sites. |
| `modules/shadow/claudemd_generator.py` | 1 | Cerberus description string mentions absorption. |
| `modules/morpheus/cross_module_dreaming.py` | 2 | Cerberus description + the prompt-template example referencing the absorbed surface. |
| `tests/test_cerberus.py` | 2 | Test class comment + the test_tool_count comment ("Phase A merge: 15 + 24"). |
| `tests/test_cerberus_security.py` | 2 | Module docstring + the absorbed-tools comment. |
| `tests/test_cerberus_security_tool_selection.py` | 1 | Module docstring. |
| `tests/test_cerberus_security_analyzer.py` | 1 | Module docstring. |
| `tests/test_cerberus_security_threat_intelligence.py` | 1 | Module docstring. |
| `tests/test_cerberus_auto_registration.py` | 2 | Comments explaining the Phase A merge fixture-string change. |
| `scripts/phase_a_sentinel_cerberus_inventory.py` | 15 | This merge's own inventory generator (intentionally references both modules). |

These references either describe the merge, document historical
lineage, or are in frozen artifacts (benchmarks, sibling merge docs).
The default sweep rule does not modify any of them.

## Bucket D — MASTER REVIEW (no default action; awaiting your call)

Per addendum 3 master-locked decision: do NOT pre-review; surface
the per-file rg content here; Master decides which (if any) to
modify. The sweep does **not** touch these without explicit
approval. Per-file content shown so you can rule on each in one
pass.

### D.1 Active code references that look behavioral

| File | Hits | Content |
| --- | ---: | --- |
| `scripts/dump_tools.py:38` | 4 | Live import of `Sentinel` for tool dumping. **This file will break after `modules/sentinel/` deletion** unless its `KNOWN_MODULES` entry is removed. **Recommended: include in commit 11 sweep** — it's a sibling helper to the inventory script and would otherwise raise `ModuleNotFoundError` when run. |
| `config/cerberus_limits.yaml:245, 252` | 2 | YAML section-header comments ` # --- Sentinel security analyzer ---` and ` # --- Sentinel threat intelligence ---` above tool-name lists in `autonomous_tools`. Headers describe absorbed tool families. **Suggested: rewrite as `# --- Cerberus security analyzer (absorbed Sentinel) ---`** — keeps the section label honest about the new home. |
| `modules/cerberus/security/threat_intelligence.py:2526` | 1 | YARA rule template `'        author = "Shadow Sentinel"\n'`. **User-visible generated output**. Generated YARA rules carry this author string into customer-facing security artifacts. **Master call** — preserve as-is for branding continuity, or update to `"Shadow Cerberus"` to match the new home. |
| `modules/reaper/reaper.py:12, 761` | 2 | Historical docstring/comment about "Pre-Sentinel download safety". Comments only, no behavioral effect. **Master call** — leave as historical or rephrase. |
| `modules/reaper/config.py:165, 167, 168` | 4 | Same theme: "DOWNLOAD SAFETY RULES (Pre-Sentinel)" comment block. Comments only. **Master call** — leave or rephrase. |
| `modules/grimoire/grimoire_reader.py:15, 394` | 2 | Docstring example: `reader = GrimoireReader("sentinel")` and "What does Sentinel know?". Documentation example, no runtime effect. **Master call** — change to "cerberus" example or leave as-is. |
| `README.md:47, 67, 84` | 3 | Top-level project README still has "Sentinel" entry (1) in the module table, (2) in the "Security" architecture summary line, (3) in the project tree directory listing. **Master call** — likely deserves remap to reflect post-merge state. |
| `shadow/config/README.md:79` | 1 | Comment listing unmigrated dict-bridge modules: `(Grimoire, Wraith, Nova, Omen, Sentinel, Void, Morpheus, Cipher)`. Sentinel and Void are gone post-Phase-A. **Master call** — rewrite the list. |

### D.2 Test files using "sentinel" as fixture data / routing expectation

Default rule = leave alone unless the test now fails. **All 201
tests in the targeted scope pass at HEAD**, but these test files
contain historical references that may or may not be behavioral —
listed for your judgment:

| File | Hits | Likely category |
| --- | ---: | --- |
| `tests/test_orchestrator.py` | 48 | Routing-test expectations; many will now expect "cerberus" instead of "sentinel". Targeted scope didn't run this; behavior post-merge depends on whether tests assert sentinel routing. |
| `tests/test_message_bus.py` | 54 | Uses "sentinel" as arbitrary source_module string in fixtures. |
| `tests/test_module_state.py` | 18 | Module-state fixtures. |
| `tests/test_proactive_engine.py` | 19 | Proactive-trigger tests (companion to commit 8's edits). |
| `tests/test_cross_module_dreaming.py` | 7 | Morpheus × Sentinel dream combinations. |
| `tests/test_training_data_pipeline.py` | 6 | Training-data routing examples. |
| `tests/test_shadow_memory.py` | 6 | Test data using "sentinel" as source. |
| `tests/test_task_chain.py` | 5 | Task-chain module references. |
| `tests/test_tool_loader.py` | 4 | Tool-loader routing expectations. |
| `tests/test_grimoire_reader.py` | 4 | Uses "sentinel" as arbitrary module filter (test fixture). |
| `tests/test_grimoire_faceted_tags.py` | 4 | Tag-validator tests; may need "cerberus.security" added. |
| `tests/test_morning_briefing.py` | 3 | Briefing fixtures. |
| `tests/test_contextual_routing.py` | 4 | Routing expectations. |
| `tests/test_integration.py` | 4 | Integration-test routes. |
| `tests/test_base_module_capabilities.py` | 2 | Base-module behavior expectations. |
| `tests/test_import_speed.py` | 4 | Measures sentinel module import time. **Will break after `modules/sentinel/` deletion** if the test imports sentinel directly. |
| `tests/test_self_improvement.py` | 2 | Fixtures. |
| `tests/test_task_queue.py` | 1 | Task-queue fixtures. |
| `tests/test_drift_detector.py` | 1 | Drift-detector expectations. |
| `tests/test_context_compressor.py` | 1 | Compressor fixtures. |
| `tests/test_fallback_transparency.py` | 1 | Fallback-routing expectations. |
| `tests/test_behavioral_benchmark.py` | 1 | Already remapped in commit 8 (`expected_module="cerberus"`); the remaining hit is likely a fixture string or comment. |

## Recommended sweep — what I plan to execute in commit 11

**With Master approval only.** Default-rule baseline (no-questions-asked):

1. **Delete `modules/sentinel/` recursively** — the whole directory.
   This is the only "guaranteed safe per the merge plan" action.

**Beyond the default — items I think are obvious and recommend including:**

2. **`scripts/dump_tools.py`** — drop the `("sentinel", "modules.sentinel.sentinel", "Sentinel")` entry from `KNOWN_MODULES`. Without this the script crashes when run; it's a sibling helper to the inventory generator and should match.

**Bucket D items I would defer to Master pending your call:**

3. `config/cerberus_limits.yaml:245, 252` — section-header rewrite.
4. `modules/cerberus/security/threat_intelligence.py:2526` — YARA `author` string.
5. `README.md:47, 67, 84` — project README absorption update.
6. `shadow/config/README.md:79` — unmigrated-modules list update.
7. `modules/reaper/reaper.py:12, 761` — historical comments.
8. `modules/reaper/config.py:165–168` — historical comment block.
9. `modules/grimoire/grimoire_reader.py:15, 394` — docstring examples.
10. `tests/test_import_speed.py` — likely breaks after sentinel directory delete; may need adjustment.
11. The other 21 test files — leave alone unless a specific one is flagged.

## Decision needed from Master

For each of items 2–11 above, please indicate **APPROVE** (include in
commit 11 sweep), **DEFER** (leave for a later cleanup pass), or
**SKIP** (not needed — leave as-is).

Item 1 (the `modules/sentinel/` directory deletion) is the
non-negotiable core of commit 11 and will execute regardless.

After your decisions, I will execute the approved subset, run the
final smoke (boot test + targeted tests + tool inventory), then
commit. No `git push`. No merge to `main`.
