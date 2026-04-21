# Plan: Routing & Module Targeting Fixes (Batch 2)

## Files to Modify
1. **`modules/shadow/orchestrator.py`** — `_fast_path_classify()` (lines 1728-1827) and `_step2_classify()` LLM prompt (lines 1448-1468), plus `_fallback_classify()` (lines 1500-1538)
2. **`tests/test_orchestrator.py`** — Add tests for all new routing rules

## Changes

### Step 1: Restructure fast-path keyword section with priority order and new modules

The current keyword section (lines 1728-1827) checks: Omen → Cipher → Wraith → Reaper → Cerberus. We need to:

**a) Add code-detection helper set** (used by Nova vs Omen conflict resolution):
```python
code_indicators = {"code", "function", "script", "program", "class", "module", "debug",
                   "compile", "api", "endpoint", "database", "sql", "python", "javascript",
                   "typescript", "rust", "java", "html", "css", "react", "django", "flask",
                   "bot", "parser", "handler", "decorator", "lambda", "variable", "method",
                   "lint", "refactor", "syntax", "algorithm", "snippet", "coding"}
```

**b) Reorder keyword checks to match priority spec:**

1. **Cipher math patterns** (digits + operators) — FIRST priority
   - Keep existing `has_math_symbol` and `has_numeric_expr` checks
   - Move them BEFORE Omen keywords
   
2. **Omen** (code keywords) — add `"compile"` to keywords, keep existing context matching
   
3. **Wraith** (reminders) — keep existing, add `"reminder"`, `"calendar"`, `"task"`, `"todo"`

4. **Sentinel** (security) — NEW
   - Keywords: `security`, `scan`, `vulnerability`, `threat`, `intrusion`, `firewall`, `integrity`, `breach`, `audit`
   - Phrases: `"security check"`, `"security scan"`, `"threat assessment"`
   
5. **Cipher word keywords** — existing math word keywords (calculate, compute, etc.) checked AFTER Sentinel
   - Split Cipher into two checks: pattern-first (priority 1), words-second (priority 5)

6. **Nova** (content creation) — NEW
   - Keywords: `draft`, `compose`, `blog`, `article`, `essay`, `paragraph`, `story`, `creative`, `content`, `post`, `copywriting`, `newsletter`
   - Context words (only route when NOT code): `write`, `generate`, `create`
   - Rule: if `code_indicators` present → skip Nova (Omen will catch it or already did)

7. **Morpheus** (discovery/exploration) — NEW
   - Keywords: `discover`, `explore`, `experiment`, `brainstorm`, `imagine`, `speculate`, `serendipity`, `unconventional`
   - Phrases: `"what if"`, `"cross-pollinate"`, `"creative connection"`

8. **Reaper** (research) — keep existing but AFTER Morpheus
   - Remove `"find"` as sole keyword (too generic, conflicts with Nova/Morpheus)
   - Keep phrases: `"look up"`, `"what is"`, `"who is"`

9. **Void** (metrics/monitoring) — NEW
   - Keywords: `metrics`, `monitoring`, `uptime`, `diagnostics`
   - Phrases: `"system status"`, `"system health"`, `"performance"`, `"health check"`, `"resource usage"`, `"cpu usage"`, `"memory usage"`, `"gpu usage"`, `"disk usage"`

10. **Harbinger** (briefings/reports) — NEW
    - Keywords: `briefing`, `alert`, `notification`
    - Phrases: `"daily briefing"`, `"morning briefing"`, `"status report"`, `"safety report"`

11. **Grimoire** (memory keywords) — keep `"remember"`, `"forget"`, `"recall"` but move LAST in keyword section

12. **Cerberus** (ethics) — keep existing position

### Step 2: Fix the × symbol bug (BUG 10)
The `has_numeric_expr` regex already handles `×` in the character class `[+\-*/×÷xX^%]`. But the problem is that `x` and `X` in the regex match normal letters. The fix: require digits on both sides (already done). The actual bug is that Cipher math patterns are checked AFTER Omen, so if any Omen keyword matches first, Cipher never runs. Moving Cipher pattern detection to position 1 fixes this.

Also: the `"x"` in the regex pattern could match words like "text". We should keep the digit-boundary requirement strict. The current regex `\d+\s*[...xX...]\s*\d+` already requires digits on both sides, so "text" won't match. The `×` symbol is fine.

### Step 3: Update LLM router prompt (BUG 11)
Replace the limited 5-module capabilities list with all 13 modules. Add clear, actionable descriptions for each.

### Step 4: Update `_fallback_classify()` 
Add fallback entries for the new modules (Sentinel, Void, Nova, Morpheus, Harbinger) so they're reachable even when LLM routing fails.

### Step 5: Add tests
Add test cases in `tests/test_orchestrator.py`:
- BUG 6: "Run a security check on your system" → sentinel
- BUG 7: "Show me your system metrics" → void  
- BUG 8: "Write me a short paragraph about why landscaping is rewarding" → nova
- BUG 8 conflict: "Write a Python function to sort a list" → omen (not nova)
- BUG 9: "Discover something interesting about neural network architecture" → morpheus
- BUG 10: "What is 347 × 892?" → cipher
- BUG 10: "347 * 892" → cipher (not reaper)
- Conflict: "calculate 15% of 2400" → cipher (not reaper)
- Sentinel phrases: "threat assessment of my network" → sentinel
- Void phrases: "how is my system health" → void
- Nova vs Omen: "write a blog post about landscaping" → nova
- Morpheus: "what if we combined neural networks with landscaping scheduling" → morpheus
- Priority: math pattern before everything: "5 + 3" → cipher

---

# Cipher → Omen Merge — Hardening Addenda

Context: Phase A absorbs Cipher (7 tools) into Omen as a utility
sub-namespace. These two decision records lock in the integration
shape and the router opt-out mechanism before the commit sequence
begins. Zero tool loss is the invariant.

## DECISION 1 — Integration structure

### Cipher tool inventory (pre-merge)

| Tool             | Purpose (one line)                                           |
| ---------------- | ------------------------------------------------------------ |
| `calculate`      | Evaluate math expressions (AST-based, no eval). Returns result + steps. Falls back to `needs_reasoning` for natural-language input. |
| `unit_convert`   | Convert between length / weight / volume / area / digital / time / speed / temperature units. |
| `date_math`      | Date arithmetic: add/subtract days/weeks/months/years, diff between dates, day_of_week, business_days. |
| `percentage`     | Percentage ops: X% of Y, what-percent, percent-change, markup, margin. |
| `financial`      | Financial math: compound_interest, pmt, roi, break_even, profit_loss. Mandatory non-advice disclaimer in metadata. |
| `statistics`     | Descriptive stats on a list of numbers: mean/median/mode/stdev/variance/min/max/range/sum/percentiles. Alias: `data_analyze`. |
| `logic_check`    | Boolean logic: 1-3 variable truth tables + structural premise/conclusion analysis. Alias: `logic_verify`. |

All tools are pure functions, stdlib-only deps (`ast`, `math`,
`operator`, `re`, `statistics`, `calendar`, `datetime`, `itertools`),
no shared state, no DB/Grimoire/Cerberus coupling.

### Chosen option: (b) submodule helper — **name preservation over prefixing**

Create `modules/omen/cipher_tools.py` as a plain helper class
(`CipherTools`) alongside Omen's existing helpers
(`CodeAnalyzer`, `CodeSandbox`, `ModelEvaluator`, `Scratchpad`,
`TestGate`). Omen instantiates one in `__init__` and dispatches the
absorbed tool names through its existing `execute()` handler map.
**Tool names are preserved exactly — no `cipher_` prefix, no
`omen_calculate` rename.**

Rationale:
- **Zero-tool-loss invariant is trivially satisfied** when names are
  preserved — no rename documentation, no migration for downstream
  callers, no risk of a typo in the dispatch map dropping a tool.
- **Zero collision**: Omen's 40 existing tool names are all prefixed
  (`code_*`, `git_*`, `pattern_*`, `scaffold_*`, `sandbox_*`,
  `model_*`, `dependency_*`, `failure_*`) so the seven unprefixed
  Cipher names (`calculate`, `unit_convert`, `date_math`,
  `percentage`, `financial`, `statistics`, `logic_check`) drop in
  without conflict. Verified against `Omen().get_tools()` inventory.
- **Idiomatic to Omen**: helpers-at-same-level is already how Omen
  organizes its sub-capabilities. A submodule directory
  (`modules/omen/cipher/`) would be over-engineered for 7 pure
  functions; inlining into [omen.py](modules/omen/omen.py) (already
  3,274 lines) would compound the monolith.
- **Option (a) flat absorption with `omen_calculate` renames** was
  rejected: forces rename documentation, breaks any external caller
  that hardcoded the old names, and muddles Omen's otherwise-consistent
  `code_*` / `git_*` / `pattern_*` naming scheme.
- **Option (c) inline private helpers renamed to Omen-native** was
  rejected for the same reason plus the monolith concern.

### Post-merge tool name list (exact strings exposed by `Omen.get_tools()`)

Preserved from Cipher (7):
1. `calculate`
2. `unit_convert`
3. `date_math`
4. `percentage`
5. `financial`
6. `statistics`
7. `logic_check`

Backward-compat aliases still dispatched through Omen (2, same handlers):
- `data_analyze` → `CipherTools.statistics`
- `logic_verify` → `CipherTools.logic_check`

Aliases are NOT re-published as separate entries in `get_tools()` —
that matches Cipher's pre-merge schema (aliases are dispatch-only).

### Dedup analysis — no obvious Omen analog warrants collapse

| Cipher tool    | Omen overlap? | Verdict                             |
| -------------- | ------------- | ----------------------------------- |
| `calculate`    | None. `code_execute` can run arbitrary Python (including math) but uses a sandboxed subprocess, wildly different contract. | Preserve as-is. |
| `unit_convert` | None.         | Preserve as-is.                     |
| `date_math`    | None.         | Preserve as-is.                     |
| `percentage`   | None.         | Preserve as-is.                     |
| `financial`    | None.         | Preserve as-is; mandatory disclaimer metadata kept intact. |
| `statistics`   | None. `code_score` and `code_analyze` produce code-quality metrics, not descriptive statistics on user data. | Preserve as-is. |
| `logic_check`  | None.         | Preserve as-is.                     |

Conclusion: preserve all 7 tools verbatim. No dedup. Function bodies
port without modification — Phase A is the wrong time to touch
calculation logic.

---

## DECISION 2 — Router opt-out mechanism

### Chosen option: (a) — outright deletion of Cipher routing hardcodes

Cipher ceases to exist as a module post-merge (`modules/cipher/`
directory removed, `Cipher` class deleted, no entry in main.py's
registry). There is nothing to gate behind a flag. This aligns with
the Void session's approach in spirit: in both cases, the module
leaves the routing target set entirely. The difference is cosmetic —
Void uses `ModuleRegistry.is_routable()` because the Void class
still exists (as a daemon); Cipher needs no predicate because the
class is deleted outright. Both sessions agree: **no `enabled=False`
lazy-instantiation gate** — that would add a dict-bridge config
knob for a module that no longer exists.

Options considered and rejected:
- **(b) `config.cipher.enabled=False` + lazy instantiation**: adds
  dead config surface for a deleted module. Keeps the routing
  hardcodes alive behind a flag that must be flipped and forgotten.
  Worst of both worlds.
- **(c) Keep Cipher-stub module that routes everything to Omen**:
  indirection with no value. Breaks the "one identity, N modules"
  principle by splintering math into two consult points.

### Deletion checklist — every line that goes away

**File: [modules/shadow/orchestrator.py](modules/shadow/orchestrator.py)**

| Line(s)    | Current content (summary)                                    | Action                                                            |
| ---------- | ------------------------------------------------------------ | ----------------------------------------------------------------- |
| 1821       | LLM router prompt: `- cipher: Math, calculations, unit conversions, financial estimates, statistics, logic puzzles, data analysis. ANY math or numbers task.` | Delete line. Fold math/stats/finance capabilities into omen's prompt line. |
| 1887       | `fallback_classify()` — `"calculate"` → `target_module="cipher"` | Retarget to `"omen"`.                                             |
| 1911       | `fallback_classify()` — `"math"` stem → `target_module="cipher"` | Retarget to `"omen"`.                                             |
| 2350       | Module availability list: `"cipher"` in `["cipher", "omen", "nova", "void", "harbinger", "wraith", "cerberus", "shadow"]` | Remove `"cipher"`.                                                |
| 2356-2387  | `_STRONG_STEMS` — dedicated Cipher stem block (`"calculat"`, `"compute"`, `"solv"`, `"math"`, `"equation"`, `"multipl"`, `"divid"`, `"subtract"`, `"factorial"`, `"logarithm"`, `"derivativ"`, `"integral"`, `"price"`, `"cost"`, `"estimat"`, `"total"`, `"percentag"`, `"puzzle"`, `"riddle"`, `"logic"`) | Delete entire cipher block in `_STRONG_STEMS`.                    |
| 2468       | `TaskType` map: `"cipher": TaskType.ANALYSIS`                | Delete entry.                                                     |
| 2502       | Bare module words list: `"cipher"` in `["cipher", "omen", "harbinger", "wraith", "cerberus"]` | Remove `"cipher"`.                                                |
| 2517       | Explicit phrase routing tuple: `("ask cipher", "cipher")`    | Remove tuple.                                                     |
| 2553-2564  | Priority 1 math-pattern fast-path: `target_module="cipher"`  | **Retarget to `"omen"`**. Patterns (digits+ops, math symbols) are unambiguous — fast-path stays, just points to Omen. |
| 2688-2727  | Priority 5 Cipher stem block — the S41 over-matching bug     | **DELETE ENTIRELY** (block + `_cipher_stems`, `_cipher_exact`, `_cipher_ambiguous_stems`, `_skip_cipher` guard). Bug vanishes. |
| 4123-4180  | Step 4 tool-planner's Cipher-specific branch (maps classified `"cipher"` tasks to unit_convert / percentage / financial / statistics / logic_check / date_math / calculate) | Delete entire branch. When LLM routes a math task to omen, Omen's planner (or pattern planner) selects among the same tools. |

**File: [modules/shadow/tool_loader.py](modules/shadow/tool_loader.py)**

| Line | Current content                                              | Action        |
| ---- | ------------------------------------------------------------ | ------------- |
| 276  | `"cipher": ["calculate", "math", "convert units"]` in `_CROSS_MODULE_KEYWORDS` | Delete entry. |

**File: [main.py](main.py)**

| Line | Current content                                         | Action        |
| ---- | ------------------------------------------------------- | ------------- |
| 52   | `Cipher = _try_import("modules.cipher.cipher", "Cipher")` | Delete line.  |
| 176  | `cipher = Cipher(module_configs.get("cipher", {})) if Cipher else None` | Delete line. |
| 204  | `cipher` in `all_modules` list                          | Remove item.  |

**File: [shadow/config/\_\_init\_\_.py](shadow/config/__init__.py)**

| Line | Current content                                         | Action        |
| ---- | ------------------------------------------------------- | ------------- |
| 58   | `from modules.cipher.config import CipherSettings`      | Delete line.  |
| 82   | `"cipher": "cipher"` in `_MODULE_FIELD_MAP`             | Delete entry. |
| 206  | `cipher: CipherSettings = Field(default_factory=CipherSettings)` | Delete field. |

**File: [config/config.yaml](config/config.yaml)**

| Line | Current content                                  | Action                                            |
| ---- | ------------------------------------------------ | ------------------------------------------------- |
| 56   | `- "cipher"` in `modules.load_on_startup` list   | Delete entry.                                     |
| 36   | `smart_brain.purpose: "Complex reasoning (Cipher, Omen, research)"` (prose) | Update string to drop Cipher reference.           |

**File tree**

| Path                                         | Action                                                               |
| -------------------------------------------- | -------------------------------------------------------------------- |
| [modules/cipher/cipher.py](modules/cipher/cipher.py)             | Delete.                                                              |
| [modules/cipher/\_\_init\_\_.py](modules/cipher/__init__.py)     | Delete.                                                              |
| [modules/cipher/config.py](modules/cipher/config.py)             | Delete.                                                              |
| [modules/cipher/](modules/cipher/)                               | Delete directory.                                                    |
| [tests/test_cipher.py](tests/test_cipher.py) (861 lines, 115 tests) | Delete; contents ported to `tests/test_omen_cipher_integration.py` with Omen fixture. |

**Other modules — grep sweep during commit 4**

[wraith/wraith.py](modules/wraith/wraith.py), [cerberus/*](modules/cerberus/),
[morpheus/*](modules/morpheus/),
[modules/shadow/chain_of_thought.py](modules/shadow/chain_of_thought.py),
[drift_detector.py](modules/shadow/drift_detector.py),
[introspection_dashboard.py](modules/shadow/introspection_dashboard.py),
[proactive_engine.py](modules/shadow/proactive_engine.py),
[task_chain.py](modules/shadow/task_chain.py),
[task_tracker.py](modules/shadow/task_tracker.py),
[behavioral_benchmark.py](modules/shadow/behavioral_benchmark.py),
[modules/apex/training_data_pipeline.py](modules/apex/training_data_pipeline.py),
[modules/grimoire/entity_extractor.py](modules/grimoire/entity_extractor.py),
[modules/omen/code_analyzer.py](modules/omen/code_analyzer.py) — grep
for the literal string `cipher` (case-insensitive). Prose-only
mentions are pruned or annotated; any import or routing hit is
cleaned. Per the Phase A non-goals, no behavior change in these
modules beyond removing the dead reference.

### Confirmation — alignment with Void session

Void session chose `ModuleRegistry.is_routable()` because Void
persists as a daemon — the class exists, but routing is disabled.
Cipher chooses outright deletion because the class ceases to exist.
**The two sessions agree on the principle** (Cipher is not a
routing target post-merge); the mechanism differs only because
Cipher's disposition differs (demoted-to-daemon vs absorbed-into-sibling).

No shared-file edits between this branch and the Void branch — both
sessions can commit independently without merge conflicts.

