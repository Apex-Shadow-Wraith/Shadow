# Commit 7 Sweep Diff — Master Review

**Status:** read-only inspection. No changes applied yet. Master
reviews this document, approves specific applications, and only then
the sweep executes (still scoped to commit 7).

Branch: `phase-a/cipher-into-omen` at HEAD = commit 6
(`0bfa733` docs(phase-a): Cipher → Omen tool inventory + diff).

## Current rg state

After commits 1–6: `rg -i cipher` over the working tree finds **63
files** with `cipher` references. Categorized below by addendum-3
bucket; the default sweep applies only buckets A and B; buckets C
and D are preserved or flagged for Master review.

## Bucket A — REMOVE (default rules apply)

These execute as part of commit 7 with no Master approval needed:

| Path | What gets deleted |
| --- | --- |
| `modules/cipher/` (entire directory) | `cipher.py`, `config.py`, `__init__.py`, `__pycache__/` |
| `tests/test_cipher.py` (861 lines, 115 tests) | Replaced by `tests/test_omen_cipher_integration.py` (110 tests, all green) in commit 5. The original file now references `from modules.cipher.cipher import Cipher` which no-ops post-deletion. |

The whole-directory delete plus the deprecated test file are the
only behavioral changes pending in commit 7. Everything else has
already shifted to bucket-A-clean state in commits 3 and 4.

## Bucket B — PORT + REMAP (already complete, commit 5)

`tests/test_cipher.py` was ported to
`tests/test_omen_cipher_integration.py` (110 tests). The old test
file is deleted under bucket A above. No further sweep action.

## Bucket C — PRESERVE (default rule: leave alone)

Comment / breadcrumb references documenting the absorption. The
sweep does **not** touch these. Listed for transparency:

| Path | Hits | Why preserved |
| --- | ---: | --- |
| `plan.md` | 58 | Multi-session planning record (Cipher, Sentinel, Void merges). |
| `docs/phase-a/cipher-omen/tool_diff.md` | 42 | This merge's own audit document. |
| `docs/phase-a/cipher-omen/sweep_diff.md` | this file | Self-reference. |
| `docs/phase-a/cipher-omen/tool_inventory_pre.json` | many | Pre-merge schema dump of all 7 Cipher tools (commit 6). |
| `docs/phase-a/cipher-omen/tool_inventory_post.json` | many | Post-merge schema dump (commit 6). |
| `docs/phase-a/sentinel-cerberus/sweep_diff.md` | 2 | Sibling merge's record (mentions Cipher in passing as a future merge). |
| `docs/phase-a/void/pre_merge_tools.json` | 1 | Sibling merge's pre-merge inventory snapshot. |
| `docs/phase-a/void/post_merge_tools.json` | 1 | Sibling merge's post-merge inventory snapshot. |
| `docs/phase-a/void/regression_investigation.md` | 2 | Sibling merge's investigation record. |
| `docs/dual_pattern_investigation.md` | 3 | Pre-Phase-A historical investigation, frozen. |
| `scripts/phase_a_cipher_omen_inventory.py` | 16 | This merge's own inventory generator (intentionally references both modules). |
| `modules/omen/cipher_tools.py` | 7 | The absorbed implementation file — class name `CipherTools`, logger name `shadow.omen.cipher`, file/class docstrings credit the absorption. Intentional branding. |
| `modules/omen/omen.py` | 14 | Phase A absorption: import line, instantiation comment, dispatch dict (9 entries: 7 tools + 2 aliases), `get_tools()` schema entries, comment block markers. |
| `modules/shadow/orchestrator.py` | 19 | Phase A absorption comments: LLM router prompt mentioning absorbed math, `_fallback_classify` comments, `_STRONG_STEMS` Phase A note (deletion comment), Priority 1 retarget note, Priority 5 deletion note, math sub-router descriptions ("absorbed Cipher"), system-prompt module list note. |
| `modules/shadow/proactive_engine.py` | 3 | Phase A comments above the math-validation triggers (renamed from "Cipher" to credit absorption). |
| `modules/shadow/task_chain.py` | 1 | Phase A comment above `keyword_map["omen"]` documenting Cipher's keywords were folded in. |
| `modules/shadow/tool_loader.py` | 1 | Phase A comment on `_CROSS_MODULE_KEYWORDS["omen"]` documenting the keyword fold. |
| `modules/shadow/drift_detector.py` | 1 | Phase A comment above `MODULE_SPECIALIZATIONS["omen"]` (role renamed `code` → `code_and_math`). |
| `modules/shadow/claudemd_generator.py` | 1 | Omen description string mentions absorption. |
| `modules/shadow/chain_of_thought.py` | 1 | Module docstring "Feeds into" line credits absorption. |
| `modules/shadow/behavioral_benchmark.py` | 1 | Phase A comment above the math benchmark fixtures (now `expected_module="omen"`). |
| `modules/morpheus/cross_module_dreaming.py` | 2 | Omen description mentions absorbed surface; dream-prompt example references "Omen (math, absorbed Cipher)". |
| `modules/cerberus/emergency_shutdown.py` | 1 | Phase A comment above the safe-tool list (`# Math/stats/finance — absorbed Cipher → Omen`). |
| `modules/wraith/wraith.py` | 1 | Phase A comment in the math-keyword suggestion routing. |
| `modules/base.py` | 1 | ModuleRegistry docstring mentions absorption. |
| `tests/test_omen_cipher_integration.py` | 8 | The new regression suite — class names (`TestAbsorbedCipherSurface`), test names (`test_data_analyze_alias`, etc.), module docstring. Intentional. |
| `tests/test_omen.py` | 4 | Phase A test additions — comment + tool-name list verifying all 7 absorbed tools present. |
| `tests/test_orchestrator.py` | 23 | Renamed test functions (`test_calculate_keyword_no_fastpath_post_merge`, `test_math_pattern_priority_before_omen_code`, etc.) plus comments documenting the deletion of Priority 5 stem block + step-planner reorder + module list. |
| `tests/test_informational_guard.py` | 13 | TestInformationalGuardCipher class — renamed assertions documenting the deleted stem block + Priority 1 retarget. |
| `tests/test_decision_loop.py` | 10 | MockOmenAbsorbedMathModule class + TestMathRouting tests. Intentional. |
| `tests/test_contextual_routing.py` | 5 | Phase A documentation in renamed contextual tests. |
| `tests/test_integration.py` | 2 | Phase A docstring + count comment. |
| `tests/test_omen_cipher_integration.py` | 8 | (Listed twice — same file, double-counted in the rg pass.) |
| `tests/test_benchmarks.py` | 4 | TestOmenAbsorbedCipherBenchmark — renamed class + comment. |
| `tests/test_shadow_memory.py` | 2 | Module description prose in test data. |
| `tests/test_self_improvement.py` | 2 | Fixture-string `cipher` (passes — see D.2 below). |
| `tests/test_growth_engine.py` | 1 | Fixture-string `cipher` (passes). |
| `tests/test_confidence_calibration.py` | 8 | Fixture-string `cipher` (all 25 tests pass). |
| `tests/test_training_data_pipeline.py` | 6 | Fixture-string `cipher` (all 36 tests pass). |
| `tests/test_retry_engine.py` | 6 | Fixture-string `cipher` (all 35 tests pass). |
| `tests/test_workflow_store.py` | 7 | Fixture-string `cipher` (all 27 tests pass). |
| `tests/test_tool_loader_retry_integration.py` | 9 | Fixture-string `cipher` (all 18 tests pass). |
| `tests/test_emergency_shutdown.py` | 4 | Fixture-string `cipher` (all 68 tests pass). |
| `tests/test_lora_tracker.py` | 3 | Fixture-string `cipher`. |
| `tests/test_operational_history.py` | 3 | Fixture-string `cipher`. |
| `tests/test_context_orchestrator.py` | 2 | Fixture-string `cipher`. |
| `tests/test_fallback_transparency.py` | 2 | Fixture-string `cipher`. |
| `tests/test_behavioral_benchmark.py` | 2 | Fixture-string `cipher`. |
| `tests/test_cerberus_auto_registration.py` | 1 | Fixture-string `cipher`. |
| `tests/test_proactive_engine.py` | 1 | Fixture-string `cipher`. |
| `tests/test_confidence_scorer.py` | 1 | Fixture-string `cipher`. |
| `tests/test_benchmark_suite.py` | 1 | Fixture-string `cipher`. |
| `tests/test_wraith.py` | 1 | Fixture-string `cipher`. |
| `tests/test_tool_loader.py` | 1 | Fixture-string `cipher`. |
| `benchmarks/benchmark_2026-04-19.json` | 16 | Pre-merge benchmark artifact (frozen routing expectations). |
| `benchmarks/benchmark_2026-04-19_2.json` | 16 | Same. |
| `benchmarks/benchmark_2026-04-24.json` | 17 | Same. |
| `benchmarks/benchmark_tasks.json` | 5 | Same. |

These references either describe the merge, document historical
lineage, are in frozen artifacts (benchmarks, sibling merge docs),
or are inert fixture strings whose tests pass. The default sweep
rule does not modify any of them.

## Bucket D — MASTER REVIEW (no default action; awaiting your call)

Per addendum 3 master-locked decision: do NOT pre-review; surface
the per-file rg content here; Master decides which (if any) to
modify. The sweep does **not** touch these without explicit
approval. Per-file content shown so you can rule on each in one
pass.

### D.1 Active code references that look behavioral

| File | Hits | Content |
| --- | ---: | --- |
| `scripts/dump_tools.py:31` | 1 | Live import tuple: `("cipher", "modules.cipher.cipher", "Cipher")` in `KNOWN_MODULES`. **This file will break after `modules/cipher/` deletion** unless its `KNOWN_MODULES` entry is removed. **Pre-approved at Pause 1: include in commit 7 sweep.** Audit of the rest of `KNOWN_MODULES`: post-Phase-A active modules only (apex, cerberus, grimoire, harbinger, morpheus, nova, omen, reaper, shadow, wraith). **No void or sentinel entries** — those were already cleaned by their respective merge sessions. Just the cipher tuple needs removal. |

### D.2 Test files that NOW FAIL because of commit 4's bucket-A edits

These tests were not touched by commit 5's routing port because they
test module-validation behavior in non-orchestrator code (drift
detector, task tracker, cross-module dreaming). Commit 4 dropped
`"cipher"` from those modules' module-recognition sets, so the
tests' fixtures now reference an unrecognized module. **All 21
failures are direct consequences of commit 4 — they're not
Sentinel-staleness or pre-existing.**

| File | Failing tests | Failure reason |
| --- | ---: | --- |
| `tests/test_drift_detector.py` | 8 | Fixtures call `detector.log_routing("math", "cipher")` and assert `"cipher" in result["suggested_modules"]`. Commit 4 removed `"cipher"` from `MODULE_SPECIALIZATIONS` in [`drift_detector.py:55`](../../../modules/shadow/drift_detector.py); fold its should_handle into omen. |
| `tests/test_task_tracker.py` | 8 | Fixtures call `tracker.create("...", "cipher")`. Commit 4 removed `"cipher"` from `VALID_MODULES` in [`task_tracker.py:32-35`](../../../modules/shadow/task_tracker.py); now raises `ValueError: Invalid module: cipher`. |
| `tests/test_cross_module_dreaming.py` | 5 | One test asserts `len(MODULE_DESCRIPTIONS) == 13`; another expects `"cipher"` in unexplored-pair combinations; another evaluates dreams using "cipher"+other module pairings. Commit 4 dropped `"cipher"` from `MODULE_DESCRIPTIONS` in [`cross_module_dreaming.py:40`](../../../modules/morpheus/cross_module_dreaming.py). |

**Recommended fix per file:** simple fixture remapping `cipher` →
`omen` (since math/stats/finance tasks now route to omen, the
tests' module-name fixture should follow). Same shape as commit 5's
test_orchestrator.py port. Estimated ~25 line edits across the
three files; no logic changes, just fixture renames.

### D.3 Reference docs that MAY be stale

| File | Hits | Content |
| --- | ---: | --- |
| `README.md:48-91` | 3 | Already updated in commit 4 (Cipher row dropped from module table; Cipher entry removed from project-structure tree; absorption noted in the Phase-A consolidation paragraph). Remaining 3 hits are Phase-A absorption credit comments — bucket C. **Verify or no action.** |
| `shadow/config/README.md:79` | 1 | Already updated in commit 4 (Cipher removed from the unmigrated dict-bridge modules list). The single remaining hit is the post-merge text. **Verify or no action.** |
| `tests/test_import_speed.py` | 0 | Already updated in commit 5 (cipher import dropped from cold-import list). Zero remaining hits. **No action.** |

## Recommended sweep — what I plan to execute in commit 7

**With Master approval only.** Default-rule baseline (no-questions-asked):

1. **Delete `modules/cipher/` recursively** — the whole directory.
   This is the only "guaranteed safe per the merge plan" action.
2. **Delete `tests/test_cipher.py`** — superseded by
   `tests/test_omen_cipher_integration.py`. Same default-rule logic
   as Sentinel's deletion of `tests/test_sentinel.py` in commit 11.

**Beyond the default — items pre-approved at Pause 1:**

3. **`scripts/dump_tools.py`** — drop the
   `("cipher", "modules.cipher.cipher", "Cipher")` entry from
   `KNOWN_MODULES`. Pre-approved at Pause 1 ("fold into commit 7,
   not 5/6"). Audit found no other dead-module entries to drop —
   void and sentinel were already gone.

**Bucket D items I would defer to Master pending your call:**

4. **D.2 fixture remapping** — port `tests/test_drift_detector.py`,
   `tests/test_task_tracker.py`, and
   `tests/test_cross_module_dreaming.py` fixtures from `"cipher"` →
   `"omen"`. This is needed to clear 21 test failures directly
   caused by my commit 4 module-validation cleanups. Without these
   ports, the gate criterion *"Targeted tests green"* fails.
   Recommended: include in commit 7 to keep the merge-caused-and-
   merge-fixed change stack contiguous.

5. **D.3 README verifications** — already updated, no further work
   needed unless Master sees something stale.

## Decision needed from Master

For each of items 4–5 above, please indicate **APPROVE** (include in
commit 7 sweep), **DEFER** (leave for a later cleanup pass), or
**SKIP** (not needed — leave as-is).

Items 1–3 are pre-approved or default-rule and will execute
regardless. Item 1 (the `modules/cipher/` directory deletion) is
the non-negotiable core of commit 7.

After your decisions, I will execute the approved subset, run the
final smoke (boot test + targeted tests + tool inventory), then
commit. No `git push`. No merge to `main`.

## Final-gate criteria (per Master's spec)

All five must pass before commit 7 lands:

1. Targeted tests green (`test_omen*`, `test_orchestrator` excluding
   pre-existing sentinel staleness, `test_tool_loader`).
2. Tool inventory diff: zero capability loss (already attested in
   commit 6 — both pre and post inventories have the 47 same names,
   byte-identical schemas for the 7 absorbed tools).
3. Boot smoke test: orchestrator registry holds 9 active modules
   (apex, cerberus, grimoire, harbinger, nova, omen, reaper, shadow,
   wraith) — no cipher, no sentinel, no morpheus, no void.
4. Cipher stem over-matching bug structurally resolved (Cipher no
   longer a routing target — verified in commit 3, rerun the
   assertion live during the smoke).
5. All 7 Cipher tools callable through `Omen.execute()` in live test
   (verified in commit 2; rerun during the smoke).
