# Cipher → Omen Tool Inventory Diff

**Phase A merge.** Branch: `phase-a/cipher-into-omen`.
**Invariant:** zero capability loss — every Cipher tool must have a
preserved equivalent in post-merge Omen, with feature parity.

Companion artifacts in this directory:
- `tool_inventory_pre.json` — pre-merge: all 7 Cipher tools + 40
  original Omen tools (47 entries).
- `tool_inventory_post.json` — post-merge: Omen.get_tools() (47
  entries: 40 original + 7 absorbed).
- Generator: [`scripts/phase_a_cipher_omen_inventory.py`](../../../scripts/phase_a_cipher_omen_inventory.py).

## Summary

| Metric | Value |
| --- | ---: |
| Pre-merge Cipher tools | 7 |
| Pre-merge Omen tools | 40 |
| Post-merge Omen tools | **47** (40 + 7) |
| Cipher tools missing in Omen post-merge | **0** |
| Tool names changed | **0** |
| Tools deduplicated | **0** |
| Schema-byte mismatches (description / parameters / permission_level) | **0** |
| Backward-compat aliases preserved (dispatch-only, not in get_tools()) | **2** |

**Result:** zero-tool-loss invariant satisfied without any rename or
dedup. Every Cipher tool name appears in `Omen.get_tools()` with
byte-identical schema, verified by per-name comparison of
`tool_inventory_pre.json` and `tool_inventory_post.json`.

## Per-tool fate (all 7 Cipher tools)

Every entry below has fate **"preserved as-is"** — same tool name,
same description, same parameters, same permission_level. Dispatch
moves from `Cipher.execute()` (async) to `Omen.execute()` (async),
which delegates to a `CipherTools` helper instance held on Omen
(see [`modules/omen/cipher_tools.py`](../../../modules/omen/cipher_tools.py)).
The user-visible behavior, inputs, and outputs are unchanged; the
`ToolResult.module` field stamps `"omen"` post-merge (was
`"cipher"`).

| Cipher tool | Omen post-merge equivalent | Fate |
| --- | --- | --- |
| `calculate` | `calculate` | preserved as-is |
| `unit_convert` | `unit_convert` | preserved as-is |
| `date_math` | `date_math` | preserved as-is |
| `percentage` | `percentage` | preserved as-is |
| `financial` | `financial` | preserved as-is |
| `statistics` | `statistics` | preserved as-is |
| `logic_check` | `logic_check` | preserved as-is |

## Backward-compat aliases (dispatch-only)

Cipher exposed two backward-compat aliases at the dispatch layer
(in `Cipher.execute()`'s handlers dict) that did NOT appear as
separate entries in `Cipher.get_tools()`. Omen preserves both
aliases identically — same dispatch behavior, still not advertised
in `Omen.get_tools()`:

| Alias | Canonical handler | Behavior |
| --- | --- | --- |
| `data_analyze` | `statistics` | Pre- and post-merge: dispatching `data_analyze` invokes the statistics implementation. Not in `get_tools()`. |
| `logic_verify` | `logic_check` | Pre- and post-merge: dispatching `logic_verify` invokes the logic_check implementation. Not in `get_tools()`. |

Aliases are exercised by
[`tests/test_omen_cipher_integration.py`](../../../tests/test_omen_cipher_integration.py)'s
`TestAbsorbedCipherSurface::test_data_analyze_alias_dispatches` and
`test_logic_verify_alias_dispatches`.

## Dedup decisions

**No dedup performed.** Cipher's 7 tool names and Omen's 40 tool
names had **zero collision pre-merge**:

| Naming surface | Convention |
| --- | --- |
| Omen's 40 pre-merge tools | All prefixed: `code_*`, `git_*`, `dependency_*`, `pattern_*`, `failure_*`, `scaffold_*`, `seed_*`, `sandbox_*`, `model_*` |
| Cipher's 7 tools | All unprefixed: `calculate`, `unit_convert`, `date_math`, `percentage`, `financial`, `statistics`, `logic_check` |

The unprefixed Cipher names dropped into Omen without any name
contention. No dedup decisions were required and none were made.
Per the planning addenda, no `tests/test_omen_cipher_dedup.py` is
required because zero dedup decisions were made. This document is
the dedup record.

## Cross-cutting changes (out of name-level scope)

These don't affect tool identity but accompany the merge:

1. **`ToolResult.module` stamp** — every absorbed tool now stamps
   `module="omen"` (was `"cipher"`) so the registry indexes the
   surface as part of Omen. The tool name, parameters, and return
   shape are unchanged; only the owning-module identifier differs.
   Verified by `TestAbsorbedToolModuleStamp` in
   [`tests/test_omen_cipher_integration.py`](../../../tests/test_omen_cipher_integration.py).

2. **Cipher routing target removed** — orchestrator's LLM router
   prompt, `_fallback_classify`, `_MODULE_NAMES`,
   `_MODULE_TASK_TYPES`, `_BARE_MODULE_WORDS`,
   `_EXPLICIT_MODULE_PHRASES`, and the system-prompt module list
   no longer mention `cipher`. The Priority 1 math-pattern
   fast-path retargets `target_module` from `"cipher"` to
   `"omen"`. The Priority 5 Cipher stem block was **deleted
   entirely** (not migrated to Omen) to fix the S41 over-matching
   bug — moving the same ambiguous stems
   (`differenc`/`price`/`total`/`logic`) to a new target_module
   would recreate the bug class. Math-keyword prose now flows
   through the LLM router; numeric expressions still fast-path
   (now to Omen). See commit 3
   (`refactor(router): remove Cipher routing target`).

3. **Step-planner re-ordering** — the
   `target_module == "omen"` branch in `_step4_plan` was moved
   above the generic `task_type` branches (alongside the
   `cerberus` and `grimoire` target_module branches). Pre-rebase
   it was positioned after `task_type == TaskType.QUESTION`,
   which short-circuited QUESTION-typed math input
   ("What is 15% of 340?") into the no-tool fallback. After the
   reorder, all omen-targeted tasks reach Omen's math sub-router
   regardless of task_type. The math sub-router (a new block at
   the top of the omen branch) checks for `convert`, `percent`,
   `finance`, `statistics`, `logic + true/false/valid`,
   `date diff`/`days between`, then falls back to the numeric-
   expression check; whichever matches dispatches the right
   absorbed Cipher tool. Verified by
   `TestStep4PlanModuleDispatch::test_omen_math_plan_uses_absorbed_cipher_tool`
   and the 12 cerberus-security-question tool-selection tests
   (which exercise the `target_module == "cerberus"` branch that
   still sits above the task_type checks — same pattern).

4. **`config.cipher` typed-settings field removed** — Cipher's
   pydantic settings class was empty (`BaseModel` with
   `extra="allow"`, no fields), so removal from
   `shadow.config.Settings` was a three-line deletion in commit 3.
   No new Omen settings were introduced; Omen still reads its
   pre-merge config keys (`teaching_mode`, `project_root`,
   `db_path`, etc.) through the dict bridge.

5. **`source_module` provenance for Grimoire writes** — the
   `VALID_SOURCE_MODULES` set in `modules/grimoire/grimoire.py`
   no longer accepts `"cipher"` as a writer tag (per commit 4
   bucket-A sweep). Pre-merge there were no live Grimoire-write
   sites tagging `"cipher"` (Cipher had no `grimoire=` argument
   wired in `main.py`), so no historical entries are affected.
   If any pre-merge `"cipher"`-tagged entries exist in long-lived
   Grimoire stores, they remain readable via free-form metadata
   queries; writer-side validation now rejects new
   `"cipher"`-tagged writes.

## Verification

End-to-end smoke (commits 1-5, pause-2 reports):

- Omen instantiates and initializes with the absorbed Cipher
  surface loaded (`self._cipher = CipherTools()` in
  `Omen.__init__`).
- `Omen.get_tools()` returns 47 tools, zero duplicates, zero
  collisions with pre-merge Omen names.
- `Omen.execute("calculate", {"expression": "347 * 892"})`
  dispatches via the absorbed surface and returns
  `ToolResult(module="omen", success=True, content={"result":
  309524.0, ...})`.
- `Omen.execute("data_analyze", {"data": [1,2,3]})` (alias)
  dispatches to the statistics handler and returns mean=2.0.
- Pre-existing Omen tools (e.g. `code_execute`, `git_status`,
  `pattern_search`) still work and still report `module="omen"`.
- Math-input fast-path: `"347 × 892"` →
  `_fast_path_classify` → `target_module="omen"` (Priority 1
  retargeted) → `_step4_plan` → `calculate` tool.
- Math-keyword prose without numeric pattern (e.g.
  `"calculate the cost of 3 yards"`) → no fast-path (Priority 5
  stem block deleted) → flows to LLM router.
- 110 tests pass across
  [`tests/test_omen_cipher_integration.py`](../../../tests/test_omen_cipher_integration.py)
  (commit 5).
- 12 cerberus security-question tool-selection tests pass
  (verified by Master at Pause 2 — confirms the step-planner
  reorder didn't regress non-Cipher target_module branches).

The
[`scripts/phase_a_cipher_omen_inventory.py`](../../../scripts/phase_a_cipher_omen_inventory.py)
script regenerates `tool_inventory_pre.json` and
`tool_inventory_post.json`. Its asserts that `pre_names ==
post_names` (no missing names, no extra names) returns clean (zero
missing, zero extra). Per-name byte comparison of the seven
absorbed tools' schemas (description / parameters /
permission_level) is also clean — verified by ad-hoc check during
commit 6 authoring; identical dicts on both sides.
