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

---

# Sentinel → Cerberus Merge — Hardening Addenda

Context: Phase A absorbs Sentinel (24 tools) into Cerberus (15 tools,
rising to 39). These three addenda lock in three decisions that
surfaced as un-decided risks during planning — watchdog lockfile
ownership, Grimoire `source_module` provenance, and the commit-11
sweep rule — before the 11-commit merge sequence begins. Branch:
`phase-a/sentinel-into-cerberus` (not yet created).

### Addendum 1: Watchdog Lockfile Contract

#### Current state

`CerberusWatchdog` ([modules/cerberus/watchdog.py](modules/cerberus/watchdog.py))
owns a single-file lock with existence-based semantics — no `flock`,
`fcntl`, `portalocker`, or OS-level file locking. The lockfile:

- **Path:** `DEFAULT_LOCK_PATH = Path("C:/Shadow/data/cerberus_lock")`
  ([watchdog.py:38](modules/cerberus/watchdog.py#L38)). (Note: the
  `C:/` default is a stale Windows-era path and is almost certainly
  overridden at construction time on Citadel via `lock_path=` kwarg;
  that drift is out of scope for this merge but flagged.)
- **Acquisition:** `on_cerberus_down(last_heartbeat)` writes a JSON
  blob via plain `open(..., "w")` in `_lock_path`
  ([watchdog.py:199-208](modules/cerberus/watchdog.py#L199-L208)).
  Acquired only when the watchdog detects a stale heartbeat.
- **Check:** static `is_locked(lock_path=None)` — `path.exists()`
  truth check only ([watchdog.py:228-240](modules/cerberus/watchdog.py#L228)).
  The orchestrator invokes this at Step 1 of every request
  ([orchestrator.py:1032-1033](modules/shadow/orchestrator.py#L1032)).
- **Release:** static `clear_lock(lock_path=None)` — `path.unlink()`
  ([watchdog.py:242-256](modules/cerberus/watchdog.py#L242)).

#### Sentinel lifecycle-lock investigation

`rg -n 'flock|fcntl|portalocker|pidfile|pid_file|threading\.Lock|multiprocessing\.Lock|asyncio\.Lock' modules/sentinel/`
returns **zero matches**. Sentinel has no lockfile, no process lock,
no in-process concurrency primitive. Only persistent I/O is
`baseline.json` write on shutdown (plain file write, no lock).

#### Decision: **(a)** — CerberusWatchdog retains sole ownership; SecuritySurface introduces no lockfile.

#### Rationale

Sentinel has nothing to carry over. Option (b) (separate lockfile)
would create a new failure surface for no gain — there is no
concurrency scenario that would benefit. Option (c) (shared
sequential acquisition) would require SecuritySurface to know how
to create/respect the Cerberus watchdog semantics, and since the
existing watchdog already halts all Cerberus dispatch (including
security routes) when Cerberus is unhealthy, SecuritySurface
inherits the halt for free by virtue of living inside Cerberus.

#### Boot sequence (post-merge)

1. `main.py` constructs `Cerberus(config)`.
2. `Cerberus.__init__` constructs `SecuritySurface(config)` in
   memory; no lockfile touched, no heartbeat written.
3. `await cerberus.initialize()` runs `self._security.initialize()`
   which loads `data/sentinel_baseline.json` and creates the
   quarantine dir. Still no lockfile interaction.
4. `CerberusWatchdog` runs its own lifecycle (typically spawned by
   the orchestrator or a systemd unit) and writes/reads the
   existing `cerberus_lock` file independently.
5. Every orchestrator request passes Step 1:
   `CerberusWatchdog.is_locked()`. If the lockfile exists, all
   requests are rejected — including security requests that
   would have hit `SecuritySurface`.

#### Failure mode

If the lockfile already exists at boot (prior crash): `is_locked()`
returns True. Every request — including absorbed Sentinel tools —
returns the watchdog-halt response at Step 1. SecuritySurface is
never entered because the orchestrator halts upstream of Cerberus
dispatch. Master clears the lockfile via
`CerberusWatchdog.clear_lock()` or manual `rm`, same recovery
path as today. No change in operator contract.

### Addendum 2: Grimoire `source_module` Provenance

#### Write-site inventory (Sentinel → Grimoire)

Exactly **2** write sites in `modules/sentinel/` pass
`source_module="sentinel"` to `grimoire.remember(...)`:

| File:line | Context | Caller |
| --- | --- | --- |
| [modules/sentinel/security_analyzer.py:836](modules/sentinel/security_analyzer.py#L836) | `store_security_knowledge()` | firewall-concept learning, called by `security_learn` tool |
| [modules/sentinel/threat_intelligence.py:2207](modules/sentinel/threat_intelligence.py#L2207) | `store_threat_knowledge()` | threat-intel storage, called by `threat_knowledge_store` tool |

Both paths no-op when `self._grimoire is None` — the current runtime
state, since `main.py` never wires Grimoire into Sentinel.

#### Query-site inventory (filter on `source_module="sentinel"`)

Exhaustive grep across the repo for hardcoded `source_module="sentinel"`
filters in production code: **zero.** Every query site that filters
by `source_module` does so via a parameter:

- [modules/grimoire/grimoire_reader.py:414](modules/grimoire/grimoire_reader.py#L414) —
  `get_module_knowledge(module_name)` runs `WHERE source_module = ?`
  with `module_name` as a runtime parameter. Not a hardcoded filter.
- [modules/grimoire/mcp_server.py:163](modules/grimoire/mcp_server.py#L163) —
  `module_filter` variable passed by the external MCP client.

Downstream callers of `get_module_knowledge` — Morpheus
cross-module-dreaming, drift detector, behavioral benchmark, the
introspection dashboard — never hardcode the literal string
`"sentinel"` as a `source_module` filter; they iterate lists of
expected modules maintained in `modules/shadow/` (which commit 8
updates independently).

Places where the literal `"sentinel"` appears as a `source_module`
value (not a filter) — **writer-side validation + test fixtures only**:

- [modules/grimoire/grimoire.py:106](modules/grimoire/grimoire.py#L106) —
  `VALID_SOURCE_MODULES` enum-set (writer-side validator; rejects
  `remember()` calls with unknown `source_module`).
- [tests/test_grimoire_reader.py:269, 271, 281](tests/test_grimoire_reader.py#L269) —
  test passes `"sentinel"` as an arbitrary filter argument; the
  underlying SQLite is populated via raw INSERT (no validator).
- [tests/test_security_analyzer.py:551](tests/test_security_analyzer.py#L551) —
  asserts `call_kwargs[1]["source_module"] == "sentinel"`; this
  test moves to `tests/test_cerberus_security_analyzer.py` as part
  of the merge and its assertion follows the new tag.
- [tests/test_message_bus.py:131, 421, 432](tests/test_message_bus.py#L131) —
  message-bus fixtures using `"sentinel"` as an arbitrary source
  identifier (not a Grimoire filter).
- [tests/test_morning_briefing.py:231](tests/test_morning_briefing.py#L231) —
  fixture dict.

#### Decision: **(b)** — new writes use `source_module="cerberus.security"`.

Historical entries remain tagged `"sentinel"`. `VALID_SOURCE_MODULES`
gains `"cerberus.security"` and retains `"sentinel"` for historical
compatibility; a future cleanup may retire `"sentinel"` once
confidence is high that no legacy entries remain queryable. No
migration script.

#### Rationale

- Option (a) forever-tagging new writes as `"sentinel"` makes the
  provenance stamp lie about which module actually produced the
  entry post-merge — a user reading `source_module: sentinel` on
  a memory written in 2027 would have no idea the module was gone.
- Option (c) migration is unnecessary risk: the dev box has almost
  no persisted Sentinel memories today (Grimoire was intentionally
  fresh on Linux per CLAUDE.md; the RunPod Grimoire was not
  restored). The migration script would mutate near-zero rows at
  high script-correctness cost.
- Option (b) splits history between two tags but the split is
  honest: `"sentinel"` means "pre-merge", `"cerberus.security"`
  means "post-merge". Since no production code hardcodes a filter
  on `"sentinel"`, the split has zero propagation cost.

#### Required updates (option b)

Validator source of truth — `modules/grimoire/grimoire.py:104-108`:

```python
VALID_SOURCE_MODULES = {
    "apex", "omen", "reaper", "morpheus", "cipher", "manual", "ingestor",
    "grimoire", "wraith", "cerberus", "sentinel", "harbinger", "nova",
    "void", "shadow",
    "cerberus.security",   # added in commit 8
}
```

Required write-site edits (happen naturally when ports land):

1. `modules/cerberus/security/analyzer.py` (port of
   `security_analyzer.py:836`) — `source_module="cerberus.security"`.
2. `modules/cerberus/security/threat_intelligence.py` (port of
   `threat_intelligence.py:2207`) — `source_module="cerberus.security"`.

Required test-assertion update:

3. `tests/test_cerberus_security_analyzer.py` (the port of
   `tests/test_security_analyzer.py:551`) — assertion changes to
   `call_kwargs[1]["source_module"] == "cerberus.security"`.

**Total required query/assertion sites to update: 1** — the
test_security_analyzer port's assertion. All other `"sentinel"`
literals in test fixtures (`test_message_bus.py`,
`test_morning_briefing.py`, `test_grimoire_reader.py`) are
arbitrary placeholders and can be left alone (test passes
regardless) or cleaned up as hygiene. Those are Master-review
calls, not required edits.

No production-code change is required on the read side.

#### Runtime caveat

SecurityAnalyzer and ThreatIntelligence accept an optional
`grimoire=` argument but `main.py` has never wired one in (unlike
Reaper's explicit post-construction Grimoire attachment). So both
write sites no-op today. Post-merge, behavior is preserved: if
Cerberus chooses not to wire Grimoire into SecuritySurface, both
writes still no-op. If Cerberus does wire Grimoire later, writes
land with the new tag. This decision is documented in
`tool_diff.md` per the merge plan.

### Addendum 3: Commit 11 Sweep Rule

#### Raw rg result

`rg -i sentinel` across the working tree:

- **401 total occurrences across 64 files** (all file types).
- **377 occurrences across 55 .py files** (code-only).

#### Categorization

**Bucket A — REMOVE** (live imports, class references, routing-target
string literals; covered by commits 7–8, deleted entirely in commit 11):

| File | Hits | Commit |
| --- | ---: | --- |
| main.py | 3 | 7 |
| shadow/config/__init__.py | 4 | 7 |
| shadow/config/sources.py | 1 | 7 |
| config/config.yaml | 1 | 7 |
| modules/shadow/orchestrator.py | 21 | 7 |
| modules/cerberus/cerberus.py (`_INTERNAL_MODULES`) | 1 | 8 |
| modules/cerberus/creator_override.py | 1 | 8 |
| modules/cerberus/emergency_shutdown.py | 1 | 8 |
| modules/wraith/wraith.py | 1 | 8 |
| modules/shadow/proactive_engine.py | 11 | 8 |
| modules/shadow/task_chain.py | 2 | 8 |
| modules/shadow/task_tracker.py | 1 | 8 |
| modules/shadow/tool_loader.py | 1 | 8 |
| modules/shadow/behavioral_benchmark.py | 3 | 8 |
| modules/shadow/drift_detector.py | 1 | 8 |
| modules/shadow/introspection_dashboard.py | 2 | 8 |
| modules/shadow/claudemd_generator.py | 1 | 8 |
| modules/shadow/confidence_scorer.py | 1 | 8 |
| modules/morpheus/cross_module_dreaming.py | 2 | 8 |
| modules/omen/code_analyzer.py | 3 | 8 |
| modules/grimoire/entity_extractor.py | 1 | 8 |
| modules/sentinel/ (all files) | 29 | 11 (directory deleted) |

**Bucket A subtotal: 91 hits.**

**Bucket B — PORT + REMAP** (test files tracking the absorbed code;
commit 9):

| File | Hits | Action |
| --- | ---: | --- |
| tests/test_sentinel.py | 68 | delete; replaced by `tests/test_cerberus_security.py` |
| tests/test_sentinel_tool_selection.py | 19 | delete; replaced by `tests/test_cerberus_security_tool_selection.py` |
| tests/test_security_analyzer.py | 3 | port imports + assertion → `tests/test_cerberus_security_analyzer.py` |
| tests/test_threat_intelligence.py | 2 | port imports → `tests/test_cerberus_security_threat_intelligence.py` |
| tests/test_cerberus_auto_registration.py | 2 | update `_INTERNAL_MODULES` expectation |
| tests/test_behavioral_benchmark.py | 1 | remap `expected_module` |

**Bucket B subtotal: 95 hits.**

**Bucket C — PRESERVE** (historical docs, validator enum, data,
benchmark artifacts):

| File | Hits | Rationale |
| --- | ---: | --- |
| modules/grimoire/grimoire.py:106 (`VALID_SOURCE_MODULES`) | 1 | per addendum 2 — keep "sentinel" for historical entries, add "cerberus.security" |
| docs/dual_pattern_investigation.md | 4 | session report; historical record of investigation |
| README.md | 3 | historical context; no behavioral dependence |
| plan.md | 5 (rising after this append) | this-session planning record |
| shadow/config/README.md | 1 | historical comment |
| benchmarks/benchmark_2026-04-19.json | 3 | benchmark artifact (routing expectations pre-merge) |
| benchmarks/benchmark_2026-04-19_2.json | 4 | same |
| benchmarks/benchmark_tasks.json | 1 | same |
| data/sentinel_baseline.json (gitignored) | — | intentional per plan |

**Bucket C subtotal: 22 hits** (excluding gitignored data files).

**Bucket D — MASTER REVIEW** (test fixtures + ambiguous mentions;
case-by-case judgment):

| # | File | Hits | Why |
| -: | --- | ---: | --- |
| 1 | tests/test_orchestrator.py | 44 | routing-test expectations; most remap to "cerberus", some incidental |
| 2 | tests/test_message_bus.py | 50 | `"sentinel"` used as arbitrary source_module string in fixtures |
| 3 | tests/test_module_state.py | 18 | module-state fixtures |
| 4 | tests/test_proactive_engine.py | 17 | proactive-trigger tests (companion to commit 8's edits) |
| 5 | tests/test_cross_module_dreaming.py | 7 | Morpheus × Sentinel dream combinations — needs remap |
| 6 | tests/test_training_data_pipeline.py | 6 | training-data routing examples |
| 7 | tests/test_shadow_memory.py | 6 | test data using "sentinel" as source |
| 8 | tests/test_task_chain.py | 5 | task-chain module references |
| 9 | tests/test_tool_loader.py | 4 | tool-loader routing expectations |
| 10 | tests/test_grimoire_reader.py | 4 | uses "sentinel" as arbitrary module filter (test-fixture only) |
| 11 | tests/test_grimoire_faceted_tags.py | 4 | tag-validator tests; likely needs "cerberus.security" added |
| 12 | tests/test_morning_briefing.py | 3 | briefing fixtures |
| 13 | tests/test_contextual_routing.py | 3 | routing expectations |
| 14 | tests/test_integration.py | 2 | integration-test routes |
| 15 | tests/test_base_module_capabilities.py | 2 | base-module behavior expectations |
| 16 | tests/test_import_speed.py | 2 | measures sentinel module import time |
| 17 | tests/test_self_improvement.py | 2 | fixtures |
| 18 | tests/test_task_queue.py | 1 | task-queue fixtures |
| 19 | tests/test_drift_detector.py | 1 | drift-detector expectations |
| 20 | tests/test_context_compressor.py | 1 | compressor fixtures |
| 21 | tests/test_fallback_transparency.py | 1 | fallback-routing expectations |
| 22 | config/cerberus_limits.yaml | 2 | may contain sentinel-specific rules that need to fold into cerberus |
| 23 | modules/sentinel/threat_intelligence.py:2521 | 1 | YARA rule template `author = "Shadow Sentinel"` — user-visible generated output; master call |
| 24 | modules/reaper/reaper.py:12, 761 | 2 | historical docstring comments about "pre-Sentinel" download safety |
| 25 | modules/reaper/config.py:165-168 | 3 | same historical comment in config module |
| 26 | modules/grimoire/grimoire_reader.py:15, 394 | 2 | docstring example uses `GrimoireReader("sentinel")` |

**Bucket D subtotal: 193 hits across 26 files.**

Counting check: 91 + 95 + 22 + 193 = **401** ✓.

#### Decision rules (explicit)

- **REMOVE** (bucket A): live imports, live class references, live
  string literals in the orchestrator/router/config/internal-module
  lists. All removals happen in commits 7–8 and 11. Any residual
  bucket-A hit after commit 11 is a sweep failure and must be
  fixed before the commit lands.
- **PORT + REMAP** (bucket B): test files tracking the absorbed
  code. Delete/rewrite/port in commit 9. None of these files
  should still contain `sentinel` after the commit except as an
  arbitrary fixture string where the test doesn't care.
- **PRESERVE** (bucket C): historical docs, session reports,
  validator enums with a stated "keep for historical entries"
  purpose, benchmark artifacts, gitignored data files. The sweep
  at the end of commit 11 must not flag them.
- **MASTER REVIEW** (bucket D): every file in the table above.
  Before commit 11, Master reads the diff produced by the dry-run
  command below and decides per-file whether each hit is
  behavioral (remap to cerberus / cerberus.security) or test
  fixture (leave or clean as hygiene).

#### Dry-run command

Before commit 11 lands, produce a categorized diff so Master can
eyeball what would change:

```bash
# 1. What would be fully deleted (entire files / directory)
find modules/sentinel -type f; ls tests/test_sentinel*.py

# 2. What would be edited (live references being rewritten)
rg -n --type py 'sentinel|Sentinel' main.py shadow/config modules/shadow \
  modules/cerberus modules/wraith modules/morpheus modules/omen \
  modules/grimoire/entity_extractor.py

# 3. What would remain after the merge (expected historical/preserved)
rg -n -i sentinel README.md plan.md shadow/config/README.md \
  docs/dual_pattern_investigation.md modules/grimoire/grimoire.py \
  modules/reaper benchmarks/

# 4. Bucket D residue — what Master must eyeball per-file
rg -l -i sentinel tests/ | grep -v test_sentinel | \
  xargs -I{} sh -c 'echo "--- {} ---"; rg -n -i sentinel "{}"'
```

#### Files flagged for Master review before commit 11 lands

**M = 26 files** — the full Bucket D table above, rows 1–26.

