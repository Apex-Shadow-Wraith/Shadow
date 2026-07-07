# Wargame Plan — Omen (Parts 1–2: Fronts 1, 2, 4, 5)

> **Split notice.** Front 3 (self-repair / self-recreation) lives in
> `wargames/plans/omen-part3-selfmod.md` with its own red-team. Seam justified
> in the LEDGER. This file covers **Front 1 (full coding capability)**,
> **Front 2 (self-analysis)**, **Front 4 (host repair)**, and **Front 5 (the
> Gates & Autonomy Ledger)** which spans both files.
>
> **This is a wargame, not an execution.** Every move below is a route for the
> Opus 4.8 executor to run later. Nothing here mutates state; the plan is read-only.

---

## 0. Recon result — what Omen ACTUALLY is right now (plan against this, not the brief)

All claims below are quoted `file:line` from the live tree. Where recon could
not settle a fact, it is a `RECON NEEDED` mark with the exact settling command,
**not** a guess.

### 0.1 Module boundary and real tool set
- Omen is `modules/omen/omen.py` (3373 lines). It absorbed Cipher
  (`modules/omen/cipher_tools.py`, imported at `omen.py:37`).
- The **real** dispatch table is the `handlers` dict at `omen.py:575-628`, NOT
  the docs. It contains **47 dispatch keys** (44 unique tools + 3
  backward-compat aliases: `data_analyze`→`statistics` `omen.py:625`,
  `logic_verify`→`logic_check` `omen.py:627`; `code_analyze` alias family).
  CLAUDE.md/README say "21" — **stale drift**, record it.
  - **SETTLED in recon:** `./shadow_env/bin/python -c "from modules.omen.omen
    import Omen; o=Omen(); print(len(o.get_tools()))"` prints **47**. The
    `handlers` dict carries the same 47 plus 2 backward-compat aliases
    (`data_analyze`, `logic_verify`) not advertised in `get_tools()` — so every
    advertised tool has a handler (no orphaned schema). Re-run the one-liner to
    confirm no drift; recon settled it at **47 tools vs docs' 21**.
- Subsystems: `sandbox.py` (CodeSandbox), `code_analyzer.py` (CodeAnalyzer),
  `model_evaluator.py` (ModelEvaluator), `test_gate.py` (TestGate),
  `scratchpad.py` (Scratchpad), `cipher_tools.py` (CipherTools),
  `tool_creator.py` (ToolCreator — **appears orphaned**, see 0.6).

### 0.2 Intelligence source — the ceiling on "self-analysis"
- `code_review` (`omen.py:1179-1225`) is a **structural stub**: it computes
  `has_docstrings = ('"""' in code or "'''" in code)` (`omen.py:1211`),
  `has_error_handling = ("try:" in code or "except" in code)`,
  line/function/class counts, and returns
  `"note": "Full code review requires LLM (Phase 2+). Structural analysis
  only."` (`omen.py:1217`). **No model call. This is the central Front-1 gap.**
- **SETTLED in recon (CORRECTED after red-team — the first draft mis-stated
  this):** the intelligence picture is split, not uniform:
  - **Code *generation* IS model-driven today.** `_code_generate`
    (`omen.py:3176-3265+`) makes a **live local-Gemma call**: it builds an
    Ollama `/api/chat` payload with `model = config["code_model"]` default
    `"gemma4:26b"` (`omen.py:3199`), POSTs to
    `{ollama_base_url}/api/chat` (`omen.py:3242`) via
    `urllib.request.urlopen(req, timeout=60)` (`omen.py:3249`), uses a
    `write_code` tool-call, and **falls back to a plain-prompt code-extraction**
    if the tool path fails. (Its system prompt — "No disclaimers, no safety
    caveats… Just write the code," `omen.py:3215` — is consistent with the
    abliterated model.) So Front 1 does **not** need to wire a model for
    generation; it is already wired.
  - **Code *review* and *analysis* are heuristic — no model.** `_code_review`
    (`omen.py:1179-1225`) is the structural stub (string checks + the
    "requires LLM (Phase 2+)" note at `omen.py:1217`). `CodeAnalyzer`
    (`code_analyzer.py`) is AST/heuristic and uses `requests` only to *fetch a
    URL* for `code_analyze_url` (`code_analyzer.py:247`) — no model in the
    judgment path (`"strategy": ["shadow","apex","reaper"]` at
    `code_analyzer.py:975` is a static data field, not a call). `ModelEvaluator`
    hits Ollama (`model_evaluator.py:132`) but for model *evaluation*, not code
    judgment.
  - **Conclusion:** Omen can already *generate* code with the local model; it
    **cannot yet *review/judge* code with a model** — that is the real Front-1
    gap. Apex escalation is still required for hard reviews and for
    self-modification beyond what local Gemma reliably handles; the local model
    is the floor, Master's review the backstop.
- **Ceiling statement (carries into every front):** Omen's code *generation* is
  bounded by the local abliterated Gemma (already wired); its code *judgment*
  (review/analysis) is heuristic today and must be raised to model-driven in
  Front 1. Either way, "find real flaws" / "recreate himself" is bounded by the
  model: local Gemma is the floor; **Apex (Claude API) escalation is required for
  hard reviews and any self-modification beyond boilerplate**; Master's review is
  the real backstop. The plan must never imply Omen can autonomously
  out-engineer its own base model.

### 0.3 The write-and-ship surface (what can touch real code today)
- `code_edit` (`omen.py:1544-1618`): find-and-replace file write via
  `path.write_text` (`omen.py:1606`). Guards: destination must resolve inside
  `self._project_root` and must not match `PROTECTED_PATHS = {"config",
  ".git", ".env"}` (`omen.py:443`, checked `omen.py:1568-1575`); `old_text`
  must appear exactly once. **No snapshot, no test, no approval in the handler.**
  `permission_level: "autonomous"` in `get_tools()`.
  - **CRITICAL:** `PROTECTED_PATHS` does **not** include `modules/`. So
    `code_edit` can autonomously rewrite `modules/cerberus/*.py`,
    `modules/omen/omen.py` (its own code), any module. Only `config/`, `.git/`,
    `.env` are refused.
- `git_commit` (`omen.py:1277-1334`): runs `git add -A` (or named files) then
  `git commit -m`. Docstring says "requires approval
  (permission_level = approval_required)" (`omen.py:1280`) and `get_tools()`
  marks it `approval_required` — **but nothing enforces that** (see 0.4).
  Also: `cerberus_limits.yaml` lists `git_commit` under `autonomous_tools`
  — a direct contradiction of `get_tools()`. Record the conflict.
- `sandbox_execute / sandbox_validate / sandbox_to_production /
  sandbox_cleanup` (`omen.py:2783-2921`). `sandbox_to_production` is the
  promotion path — see Part 3. It has no `PROTECTED_PATHS` guard on its
  destination (`sandbox.py:1073-1147`): it can overwrite `.env`, `config/`,
  `.git/`, anything, unlike `code_edit`.

### 0.4 What ACTUALLY gates a write to Shadow's own code today
Traced end to end. The finding is Shadow's signature failure mode — **"looks
governed but isn't."**

- Live dispatch path: `orchestrator._step5_execute` (`orchestrator.py:5152`).
  Every tool call is wrapped in `cerberus.execute("hook_pre_tool", …)`
  (`orchestrator.py:5207`). The result is enforced **only** for
  `SafetyVerdict.DENY` (`orchestrator.py:5213`, tool skipped) and
  `SafetyVerdict.MODIFY` (`orchestrator.py:5222`, params rewritten).
  **`APPROVAL_REQUIRED` is not handled — control falls through to
  `module.execute(...)` at `orchestrator.py:5254`.**
- The plan-build gate (`orchestrator.py:4609-4651`) has the same hole: an
  `APPROVAL_REQUIRED` verdict is only `logger.info`'d (`orchestrator.py:4642-
  4649`) and then `plan.cerberus_approved = True` is set **unconditionally**
  (`orchestrator.py:4651`). Only `DENY` returns early.
- `_pre_tool_hook` (`cerberus.py`, body around `cerberus.py:1283`-ish, read in
  recon) is **rule-driven from `config/cerberus_limits.yaml`
  `hooks.pre_tool`**, and it **never returns `APPROVAL_REQUIRED`**. It returns
  `DENY` only when a configured deny rule's `applies_to` list contains the tool
  and its pattern matches; otherwise `ALLOW`. The deny rules are:
  - `shell_metacharacters` → `applies_to: [bash_execute, code_execute]`
    (reads `tool_params["command"]`; Omen's `code_execute` takes `code`, not
    `command`, so it never matches).
  - `protected_path_write` → `applies_to: [file_write]` (paths:
    `config/cerberus_limits.yaml`, `config/shadow_config.yaml` only). **Omen's
    write tool is `code_edit`, not `file_write` — never matched.**
  - `unapproved_external` → `applies_to: [email_send, notification_send]`.
  **None of `code_edit`, `sandbox_to_production`, `git_commit` appear in any
  deny rule.** So the pre-hook returns `ALLOW` for all of them.
- `_maybe_snapshot` (`cerberus.py:1283`) would snapshot a write: `code_edit`
  **is** in `_WRITE_TOOLS` (`cerberus.py:1277-1281`), and Cerberus **does**
  build its own `ReversibilityEngine` (`cerberus.py:137-146`). **But
  `_maybe_snapshot` reads `tool_params.get("path")` while Omen's `code_edit`
  uses `file_path` (`omen.py:1550`)** — so the snapshot silently no-ops on a
  parameter-name mismatch. `sandbox_to_production` is not in `_WRITE_TOOLS`, so
  the pre-hook never snapshots it.
- **Net enforcement reality (live path):**

  | Tool | classification | pre-hook blocks? | snapshot? | Net |
  |---|---|---|---|---|
  | `code_edit` | autonomous | no | attempts, no-ops (`path`≠`file_path`) | **executes, unsnapshotted**; only omen `PROTECTED_PATHS` (config/.git/.env) guards it — **not `modules/`** |
  | `git_commit` | approval_required (get_tools) / autonomous (yaml) | no | n/a | **executes** (auto `git add -A` + commit) |
  | `sandbox_to_production` | never_autonomous → APPROVAL_REQUIRED | no | n/a | **executes** (verdict unenforced); only TestGate (best-effort) + a currently-RED baseline accidentally block |
  | `model_pull` | never_autonomous → APPROVAL_REQUIRED | no | n/a | **executes** (httpx pull over network) |

- **The only hard gates that actually fire today:**
  1. `code_edit`'s own `PROTECTED_PATHS = {config, .git, .env}` (`omen.py:443`)
     — 3 prefixes, **not** `modules/`.
  2. TestGate on `sandbox_to_production` (`test_gate.py`) — but best-effort init
     (`omen.py:476-485`, `None` on failure) and it **blocks today only because
     the baseline suite is RED** (`test_gate.py:260`: if `pre_test.success` is
     False, `allowed=False`). That is an accident, not a designed gate.
  3. Emergency-shutdown "Cerberus self-modification" trigger
     (`emergency_shutdown.py:244-254`) checks a `target_path` against
     `cerberus_protected_paths = [modules/cerberus/, config/cerberus_limits.yaml]`
     — **but only if something calls the evaluator with `system_state`
     containing `target_path`.** RECON NEEDED (see 0.7).

### 0.5 Is `sandbox_to_production` reachable autonomously?
Yes in principle: it is a registered tool in `handlers` (`omen.py:608`) and
`get_tools()`. If the router emits a step with `tool: "sandbox_to_production"`,
`_step5_execute` dispatches it and the `APPROVAL_REQUIRED` verdict does not stop
it. **SETTLED in recon (partial):** `_step4_plan` (`orchestrator.py:4027`)
hard-codes explicit tools per task-type — `apex_query`, `experiment_list`,
`morpheus_report`, `decision_queue_read`, `notification_send`,
`briefing_compile`, `template_list`, `format_email` — and **does not name
`sandbox_to_production` or `code_edit`**; code-task steps carry `tool: None`
(`orchestrator.py:4044,4076,...`), deferring tool choice to the downstream
tool-loader/LLM tool-calling layer. **RECON NEEDED (executor, before Part 3):**
confirm whether the tool-loader (`modules/shadow/tool_loader.py`) exposes
`sandbox_to_production`/`code_edit` to the LLM tool-caller for a `tool: None`
Omen step —
`grep -n "sandbox_to_production\|code_edit\|list_tools\|permission_level" modules/shadow/tool_loader.py`.
If those tools are in the loaded schema for code tasks, they are autonomously
reachable and the gate must be real. **Treat "reachable" as the working
assumption for gate design regardless (fail-safe): the whole point of Front 5 is
that a reachable dangerous tool arrives wearing its gate.**

### 0.6 Pattern DB, failure learning, tool_creator — wired or orphaned?
- `SEED_PATTERNS` (`omen.py:57-...`) and `VALID_PATTERN_CATEGORIES`
  (`omen.py:45-54`) exist. `pattern_store/search/apply` and
  `failure_log/search/stats` are real handlers (`omen.py:1693-1996`) backed by
  `omen_patterns` / `omen_failures` SQLite tables (`omen.py:522-561`).
  **SETTLED in recon:** `SEED_PATTERNS` is read only by `_seed_patterns`
  (`omen.py:2365`, which *populates* the DB); `_code_generate` does not consult
  patterns or failures. **The pattern/failure DBs are write-mostly side stores
  — not wired into the generation or execution decision path.** Front 1's
  "convention-matching generation" (Move 1.3) must therefore *add* the read; it
  can't assume one exists.
- `tool_creator.py` (`ToolCreator`: `detect_pattern`→`propose_tool`→
  `validate_tool`→`stage_tool` writes staging → `approve_tool` moves to prod +
  `cerberus.register_tool`). **SETTLED in recon: ORPHANED — zero importers.**
  `grep -rn "tool_creator\|ToolCreator" modules/ --include=*.py` (excluding the
  file itself) returns empty. It is a real, gated autonomous-tool-creation
  subsystem that is **not wired in**. Record it as dead-but-present; do not treat
  its `approve_tool` gate as live. If a future front wires it, it arrives with
  its Cerberus-registration gate (`tool_creator.py:454`) — but that is out of
  scope here.

### 0.7 Standing policy vs. live behavior
- CLAUDE.md: never push (Master pushes manually), don't commit if tests fail,
  no architecture decisions in Claude Code sessions, don't bypass Cerberus,
  don't edit `.env`, merges are Master's manual `--no-ff`.
- **Live auto-commit surface:** `TestGate.create_checkpoint`
  (`test_gate.py:114-150`) runs `git add -A` + `git commit` autonomously as a
  side effect of `execute_with_gate`. This is an active autonomous git write
  that predates this mission. It never pushes, and it is a *checkpoint* commit,
  but it *does* sweep every dirty working-tree file into a commit. Front 5 must
  gate/scope it.
- `RECON NEEDED:` does anything feed `target_path` + `active_module` into
  `emergency_shutdown`'s evaluator on a code write? Settling command:
  `grep -rn "check_shutdown\|should_shutdown\|target_path\|evaluate.*state\|active_module" modules/shadow/ modules/cerberus/ | grep -v "__pycache__"`.
  If no caller populates `target_path` from the `code_edit`/`copy_to_production`
  path, Trigger 2 is **dormant w.r.t. code writes** and Front 5 must wire it.
  This is a gate the plan cannot assume is live.

### 0.8 Tests — verify by collection, never by grep
**SETTLED in recon: 386 tests collected, 0 collection errors** across the 9
Omen-related files, via the command below (collection only, mutated nothing).
The executor re-runs it to confirm no drift:
```
cd ~/dev/Shadow && ./shadow_env/bin/python -m pytest --collect-only -q \
  tests/test_omen.py tests/test_omen_enhanced.py tests/test_omen_tools.py \
  tests/test_omen_sandbox.py tests/test_omen_cipher_integration.py \
  tests/test_omen_node.py tests/test_sandbox.py tests/test_code_analyzer.py \
  tests/test_model_evaluator.py 2>&1 | tail -3
```
Expected: a total collected count and zero collection errors. Any collection
error is a blocker to fix before building (a module that won't import can't be
gated). **Separately**, the current *pass* state of `pytest tests/ -x -q` is
load-bearing for every gate that depends on a green baseline — see Abort A1.

---

## FRONT 1 — Full coding capability (the daily brain)

**Gap (corrected after red-team):** `code_generate` is **already model-driven**
(live local-Gemma call, 0.2); the real gap is `code_review`, which is a
structural stub with no model. **Target:** Omen writes code Master would accept,
catches bugs a good reviewer catches, and explains its work when Master is
learning — without ever implying it out-thinks its base model.

### Move 1.1 — Confirm the intelligence wiring (settled in recon; re-verify, don't re-decide)
Recon settled this (0.2): `_code_generate` calls local Gemma via Ollama
(`omen.py:3242,3249`); `_code_review`/`CodeAnalyzer` have no model. Re-verify
against the live tree before building, because a moved line would mislead a later
move:
`grep -nE "urlopen|/api/chat|ollama_base_url|api/generate" modules/omen/omen.py`
- **Expected observation:** the grep returns live calls inside `_code_generate`
  (an `urlopen` to `/api/chat` and/or `/api/generate`), and **no** such call
  inside `_code_review` (lines `omen.py:1179-1225`).
- **Fork (settled, but keep the trigger for drift):**
  - **Trigger A —** grep matches an Ollama call in `_code_generate` (expected):
    proceed; Move 1.2 *adds* a model path to `code_review` and **reuses**
    `_code_generate`'s Ollama-call helper rather than building a new client.
  - **Trigger B —** grep shows the call has moved *into* `_code_review` already
    (tree drifted forward): Move 1.2 becomes a contract-hardening of an existing
    path, not a green-field add.
- **Most likely failure:** the grep matches a *comment* mentioning "LLM" (like
  `omen.py:1217`) rather than a live call. Counter: confirm the match is inside
  a function body that executes (an actual `urlopen`), not a docstring/constant,
  by reading the surrounding 10 lines before deciding the fork.

### Move 1.2 — Upgrade `code_review` from stub to real review (local-first, Apex-escalated)
Build a review that produces **findings**, not structural counts. Contract:
- Input: `code` or `file_path` (same as today, `omen.py:1188-1199`).
- Output `ToolResult.content` is a list of findings; each finding is a dict
  `{file, line, severity ∈ {critical,high,medium,low}, category, message,
  proposed_fix}` plus a `summary` and a `driver` field
  (`"gemma-local"` | `"apex"` | `"structural-fallback"`).
- Driver policy: local Gemma via the existing model surface for routine review;
  **escalate to Apex** when (a) the file exceeds an N-line/complexity threshold,
  or (b) local review returns low confidence, or (c) the caller passes
  `deep=True`. If neither model is reachable, fall back to the current
  structural analysis but stamp `driver="structural-fallback"` and
  `success=True` with an explicit `degraded: true` — **never silently pretend a
  stub is a review** (fail-loud, per CLAUDE.md).
- Model name comes from config, never hardcoded (CLAUDE.md coding conventions).
- **Do not ask the model to emit its chain-of-thought.** Request the findings
  array and the proposed fix per finding as structured output only. (Brief
  constraint: reasoning-extraction phrasing can trip a safeguard.)

- **Expected observation:** on a file with a known planted bug (see 1.4),
  `code_review` returns at least one finding whose `line` is within ±2 of the
  bug and whose `severity` ≥ `high`; `driver` is `gemma-local` or `apex`, not
  `structural-fallback`.
- **Most likely failure:** the local model returns prose, not parseable
  findings, so the parser yields zero findings and the tool reports a clean
  file (false negative — the dangerous direction). Cause: no structured-output
  contract enforced. Counter: require the model to return a strict JSON array;
  if parsing fails, retry once with a repair prompt; if still unparseable, set
  `degraded: true` and `success=False` with the raw output attached — a review
  that can't be parsed is a failed review, not a clean file.
- **Fork:** if the local model is not installed/reachable (`model_list` returns
  empty or connection refused), Trigger → run in `structural-fallback` and flag
  `degraded`; do not block the build, but 1.4 verification must then run against
  Apex or be marked BLOCKED on model availability.

### Move 1.3 — `code_generate` / scaffolding match Shadow's conventions
Verify `SEED_PATTERNS` are actually consumed by generation (0.6). If the 0.6
grep shows they are a write-only store, wire `_code_generate` to retrieve and
apply the relevant `SEED_PATTERN` (e.g. `base_module_init`,
`tool_handler_dispatch`) so generated modules match the BaseModule shape at
`omen.py:57-244`.
- **Expected observation:** `code_generate` for "a new BaseModule named Foo"
  produces a class subclassing `BaseModule` with `__init__/initialize/execute/
  shutdown/get_tools`, and `code_score` (`omen.py:2171`) on the output returns
  a score ≥ the score of the current template output (regression-free).
- **Most likely failure:** generated code references `SEED_PATTERNS`
  placeholders (`{{module_name}}`) left unsubstituted. Cause: template fill not
  run. Counter: assert no `{{` remains in generated output; fail the tool if it
  does.

### Move 1.4 — Verify Front 1 against known-bad code (live)
Create (in a scratch dir under `data/`, not the repo) **four** small Python
files with planted defects — three keyword-detectable and, critically, **one
semantic bug with no keyword signature**:
- (a) a bare `except: pass` swallowing an error,
- (b) an off-by-one / wrong boundary,
- (c) a SQL string built by f-string concatenation,
- (d) **a logic inversion** — e.g. `if balance > 0: raise InsufficientFunds` —
  inside a function that **has** a docstring and a `try/except`, so every
  structural check (`has_docstrings`, `has_error_handling`) reports it clean.
  Structural analysis *cannot* catch (d); only a model reading semantics can.
Run `code_review` on each.
- **Expected observation (pass) — ALL must hold:**
  1. each of the 4 files yields ≥1 finding at the right line, severity ≥ high,
     with a `proposed_fix` that, applied, removes the defect;
  2. **`driver ∈ {gemma-local, apex}` on every file — never
     `structural-fallback`** (a fallback stub can fake (a)–(c) off keywords but
     is blind to (d); requiring a real driver closes the false-green);
  3. file (d) specifically is found — this is the proof the review is *semantic*,
     not string-matching. Record all four findings arrays verbatim.
- **Fail (blocker), any of:** file (d) returns zero findings; OR any file's
  `driver == structural-fallback`; OR any keyword bug is missed. A green result
  that rests on `structural-fallback` certifies nothing — treat it as FAIL, not
  PASS. Front 1 is not landed; do not sign off.
- **Fork:** if the local model is unreachable so every file is
  `structural-fallback`, Trigger → this run cannot certify Front 1; re-run
  against Apex (`deep=True`) or mark Front 1 **BLOCKED on model availability**
  (Abort A2). Never accept a structural-fallback pass.
- **When it runs:** after 1.2 and 1.3 are built, before Front-1 sign-off.
- **This is the only proof Front 1 works.** Built is not done.
- **Hazard (red-team):** running `code_review`/`code_generate` during this move
  must **not** trip `TestGate.create_checkpoint`'s `git add -A` auto-commit
  (0.7). These four files live under `data/` (gitignored) and no move here calls
  `sandbox_to_production`, so TestGate is not invoked — assert `git status`
  is unchanged by the whole of Move 1.4 as a guard.

### Move 1.5 — Preserve the dual mandate (build fast / teach)
The teaching behavior is real config: `self._teaching_mode`
(`omen.py:456`, from `config["teaching_mode"]`). Front 1 must not remove it.
When `teaching_mode` is on, `code_review`/`code_generate` attach an
`explanation` field (plain-language why, for the learner); when off, findings
only. **Expected observation:** with `teaching_mode=True`, the 1.4 findings
carry a non-empty `explanation`; with `False`, they do not. **Failure:**
teaching text leaks into fast-mode output → assert `explanation` absent when
`teaching_mode` is False.

---

## FRONT 2 — Self-analysis (know your own code, propose only)

**Target:** a standing, repeatable capability to audit Shadow's whole codebase
(Omen included) and produce a **ranked findings report** with `file:line`
evidence and a proposed fix per finding. **Every finding is a proposal. Front 2
never writes.** Its output feeds Front 3 (gated).

### Move 2.1 — Confirm read scope and the read-only guarantee
`code_analyze_self` (`omen.py:2565`), `code_analyze_dir` (`omen.py:2530`),
`code_analyze_file` (`omen.py:2496`) already read code. `_is_within_project`
(`omen.py:2485`) bounds reads to the project. Front 2 composes these with the
upgraded `code_review` (Front 1) over a file list.
- **CRITICAL tool-choice directive (pass-2 HIGH):** the audit must use
  `code_analyze_file` / `code_analyze_dir` (recon-verified: these do **not** call
  `grimoire.remember`) composed with `code_review`. It must **NOT** use
  `code_analyze_self` — that tool **unconditionally writes Grimoire** at
  `omen.py:2637` (`grimoire.remember(source="self_analysis", trust_level=0.9,
  check_duplicates=False)`) whenever a `grimoire` handle is in config. Using it
  would trip Abort A4 on move one (Front 2 is proposal-only, it must not mutate
  memory). If the ranked whole-repo metrics that only `code_analyze_self`
  produces are wanted, construct the analyzer/Omen with `grimoire=None` for the
  audit path so the `if grimoire:` guard at `omen.py:2634` skips the write —
  and assert the Grimoire row count is unchanged regardless (the read-only proof
  below is the backstop).
- **Expected observation:** running the Front-2 audit over `modules/omen/`
  returns a findings report and **nothing under version control OR under `data/`
  changed except the one intended report file** (see the read-only proof below).
- **Read-only proof (red-team fix — `git status` alone is insufficient):** the
  audit writes its report into gitignored `data/`, so `git status --porcelain`
  would show clean **even if the audit wrote elsewhere under `data/` or into
  Grimoire's SQLite/Chroma DBs**. So the proof is three-part: (a)
  `git status --porcelain` empty before == after (no repo write); (b) a
  recursive mtime/size snapshot of `data/` before vs after differs **only** by
  the single intended `data/reports/self_analysis/<ts>.json` file; (c) the
  Grimoire memory row count and the Chroma collection count are unchanged
  (Front 2 does **not** call `remember()` — assert row counts equal before and
  after). Any other delta = Front 2 wrote where it must not; **Trigger →
  Abort A4** (Front 2 is proposal-only, it must not mutate memory).
- **Most likely failure:** a finding's `file:line` points at a line that has
  since shifted (stale offset). Cause: report generated against an unsaved
  buffer. Counter: the audit records the file's git blob hash alongside each
  finding; a consumer (Front 3) must re-verify the hash before acting.

### Move 2.2 — Rank and de-duplicate; compose with (not duplicate) the bug-hunt
Front 2 is **Omen auditing itself on demand**; the separate bug-hunt mission is
a whole-system sweep. To avoid duplication, Front 2 tags each finding with
`source: "omen-self-analysis"` and writes to a distinct report path
(`data/reports/self_analysis/<timestamp>.json`, under `data/`, gitignored — NOT
the repo). Ranking key: severity, then blast radius (does the file appear in
`graphify-out/GRAPH_REPORT.md` as a god node — e.g. `ToolResult`).
- **Expected observation:** the report is a ranked JSON array; the top finding
  has the highest severity; the file is written under `data/reports/` and does
  **not** show in `git status` (gitignored).
- **Failure:** report lands inside the repo tree and appears in `git status`.
  Counter: assert the output path resolves under `data/` and is gitignored
  before writing.

### Move 2.3 — Verify Front 2 finds a real, pre-known flaw
Point the audit at the **two files** that contain the recon's known
*file-local* bugs (a file-scoped audit cannot see cross-file bugs, so the
verification only asks for what is findable within a file):
- `modules/cerberus/cerberus.py` → the **`path` vs `file_path` parameter
  mismatch** in `_maybe_snapshot` (recon 0.4) — a real "looks governed but
  isn't" bug, visible by reading that one function against `_WRITE_TOOLS`.
- `modules/omen/sandbox.py` → **`copy_to_production` deletes an existing file on
  rollback via `dst.unlink()`** and has **no destination path guard** (recon
  0.3) — both visible within `copy_to_production` itself.
- **Expected observation (pass), concrete:** the report contains a finding whose
  `file` is `modules/cerberus/cerberus.py`, whose `line` is within ±3 of the
  `_maybe_snapshot` `tool_params.get("path")` read, `severity ≥ high`, and whose
  `proposed_fix` string aligns the parameter name (mentions `file_path`); **and**
  a finding whose `file` is `modules/omen/sandbox.py` pointing at the
  `dst.unlink()` rollback with a `proposed_fix` that restores from snapshot.
  Record both findings verbatim.
- **Fail:** the audit misses **either** file-local bug. **Fork (trigger):** if
  Front 2 misses *both*, → Front 2's model path is too weak for self-audit;
  escalate the audit to Apex (`deep=True`) and re-run before sign-off; if it
  still misses both under Apex, mark Front 2 **WEAK** and require Master
  spot-check of every self-analysis report until the model path improves.
- **Scope note (red-team):** the *cross-file* bug (unenforced
  `APPROVAL_REQUIRED`, which spans `get_tools` → registry → cerberus →
  orchestrator) is **out of scope for a file-scoped audit** and is NOT part of
  this pass condition — surfacing it requires the whole-system bug-hunt mission
  or a multi-file audit mode. Do not penalize Front 2 for missing it here;
  record it as a known limitation of on-demand self-analysis.

---

## FRONT 4 — Repair Master's machine (conservative default, gated)

**Default scope: read-only host diagnostics + proposed fixes Master runs. No
autonomous host writes, ever, in default scope.**

### Move 4.1 — Build read-only host diagnostics (low-risk, high-value)
A diagnostics capability that reads: disk (`df`, SMART status), memory
(`free`, `dmesg` for OOM), service status (`systemctl --user status <unit>` —
read-only), package state (`apt list --installed` / version queries), GPU
(`nvidia-smi`), and log tails. All **read-only** commands. These are the class
that diagnosed the 8TB-drive link-down and the EXPO-freeze (per project memory).
- **RECON NEEDED:** the exact allow-list of diagnostic commands must be
  Master-approved and stored in config, not hardcoded. Settling question to
  Master: "Which host-diagnostic commands may Omen run unattended?" Until
  answered, the capability is **BLOCKED** on the command allow-list. Do not
  invent it. Ship the *mechanism* (an allow-listed read-only runner) with an
  **empty** allow-list that Master fills.
- **Expected observation:** with a one-entry allow-list (`df -h`), the
  diagnostic tool runs `df -h`, returns parsed output, and **refuses** any
  command not on the list with an explicit error.
- **Most likely failure:** a "read-only" command has a writing flag (e.g.
  `systemctl` without `status`, or `smartctl -t` which *starts* a self-test).
  Cause: allow-list entries are command *names* not full argv. Counter: the
  allow-list is exact-argv or a strict prefix with a denied-flag set; anything
  ambiguous is refused.

### Move 4.2 — Host writes are gated proposals only
Installing a package, changing a service, editing a host config, touching
firmware/BIOS-adjacent settings → Omen emits the **exact command** and a
plain-language description of what it does and its blast radius. Omen does not
run it. Master runs it or approves it. No `sudo`, no destructive `systemctl`,
no `.env` edits autonomously — already denied in CLAUDE.md and
`.claude/settings.local.json`; Front 4 honors and extends that.
- **Expected observation:** a "fix the 8TB drive mount" request returns a
  proposal object `{command, explanation, blast_radius, reversible: bool}` and
  performs **no** host write; `history`/process list shows no execution.
- **Failure:** the proposal path executes the command. Counter: the host-write
  tool has no execution branch at all in default scope — it only formats
  proposals. Executing is a *different* tool that is `never_autonomous` and
  Master-gated (Front 5).

---

## FRONT 5 — The Gates & Autonomy Ledger (the contract)

> This is SUCCESS point 9 and the mission's most important deliverable. It spans
> this file and Part 3. Every dangerous move is listed with: **what goes wrong
> ungated**, the **gate**, and the **earned-by** condition. **The recon proved
> most of these gates are currently decorative (0.4). Front 5's build is to make
> them real — wire the check, don't just name it.**

### 5.0 The load-bearing repairs (make the decorative gates real)
These are build items, each with a verification that fails on a broken result.

> **Red-team lesson baked in (do not skip):** a verification that is *already
> true because of an unrelated accident* certifies nothing — that is
> "looks-governed-but-isn't" one level up, inside the gate tests. The clearest
> example: the current RED baseline makes `sandbox_to_production` blocked *today*
> for the wrong reason (`test_gate.py:260`), so "the tool did not execute" is
> **already true** and cannot prove G1. Every verification below is written to
> **fail on the current broken behavior and pass only on the fix** — with an
> explicit *positive control* (the gate lets a benign case through) and a
> *negative control* (the pre-fix code would fail the same test). Prefer a
> deterministic **unit test** over an end-to-end run wherever the baseline could
> confound the result.

| # | Repair | Where | Verify (pass = ) — non-circular |
|---|---|---|---|
| G1 | Enforce `APPROVAL_REQUIRED` — **BOTH halves are unbuilt (pass-3):** (i) the live pre-hook `_pre_tool_hook` never *produces* the `APPROVAL_REQUIRED` verdict for these tools (it only DENY/MODIFY/ALLOWs from `cerberus_limits.yaml` rules), and (ii) `_step5_execute` never *enforces* it (handles only DENY/MODIFY, `:5213/5222`, then executes `:5254`). So G1 must add the verdict-production (a pre-hook rule that returns `APPROVAL_REQUIRED` for `never_autonomous`/protected-write tools) AND the enforcement branch (hold the step, surface to Master, execute only on approval). Plan gate `:4642-4651` too. **Async note (pass-3 correction):** the async worker's direct `module.execute` else-branch (`async_tasks.py:250-252`) is **not** a live bypass — item-13 routes async work through `run_deferred_through_graph`, which re-gates; the executor confirms that branch stays dead and does not rely on it. | `cerberus.py` `_pre_tool_hook`; `orchestrator.py:4642-4651`, `:5197-5223` | **Test the REAL loop, not a stub** (pass-2/3): drive `_step5_execute` end-to-end with a live pre-hook configured to return `APPROVAL_REQUIRED` for a benign no-op tool; assert (a) `module.execute` **not** called + `pending_approval` record exists; (b) positive control `ALLOW` → executed; (c) negative control — pre-fix loop executes. Green only through the real dispatch code with a real verdict, not a mocked one. |
| G2 | Fix the `path`-vs-`file_path` param bug — **it lives in THREE places (pass-3), not one:** `_maybe_snapshot` (`cerberus.py:1293-1294`), `_check_hard_limits` (`cerberus.py:1104-1105`), and the `protected_path_write` pre-hook rule — all read `params.get("path")` while `code_edit` sends `file_path` and `sandbox_to_production` sends `production_path`. Fix all three to read the correct key (or normalize the key upstream). | `cerberus.py:1104-1105`, `:1293-1294`, and `_pre_tool_hook` rule | A `code_edit` through the live pre-hook produces exactly one snapshot row for the target; assert reversibility-DB row +1 **and** stored bytes == pre-edit bytes. *Negative control:* pre-fix, +0 at all three sites (proves the bug was real and load-bearing). |
| G3 | Add `code_edit`, `sandbox_to_production`, `git_commit` to `cerberus_limits.yaml` `hooks.pre_tool` deny/approval rules with correct `applies_to` **and correct param key** (see G2 — the rule reads `path`), and extend `protected_path_write` paths to cover `modules/cerberus/`, `modules/omen/`, `modules/shadow/`, `config/`, `.env`. Also resolve the `git_commit` permission contradiction: `get_tools()` marks it `approval_required` (`omen.py:697`) but `cerberus_limits.yaml:227` lists it `autonomous` — yaml wins today; make both `never_autonomous`. | `config/cerberus_limits.yaml` + `_pre_tool_hook` | Pre-hook returns DENY/held for a `code_edit` AND a `sandbox_to_production` with a `modules/cerberus/` destination; assert not executed. *Negative control:* the same rule with the old `path` key does **not** fire (proving the key fix is load-bearing). |
| G4 | Extend `code_edit` `PROTECTED_PATHS` to include `modules/` (all of Shadow's own code — self-edits must route through the Part-3 pipeline, never ungated `code_edit`) | `omen.py:443` | `code_edit` on `modules/cerberus/cerberus.py` **and** on `modules/omen/omen.py` both return the "Refused: cannot edit protected path" error (`omen.py:1571-1575`); a benign `code_edit` on a `data/` scratch file still succeeds (positive control). |
| G5 | Add a destination `PROTECTED_PATHS` guard to `copy_to_production` (mirror `code_edit`) — this is also a **bypass-road closure** (Part 3 Stage 0), not just a rollback fix — and **fix the `dst.unlink()` data-loss rollback** to restore-from-snapshot, never delete an existing file | `sandbox.py:1073-1147` (`dst.unlink()` at `:1141/1144`) | Promotion to an existing protected path is refused; **the critical assertion:** an induced post-copy test failure on an existing target leaves the ORIGINAL bytes intact (file hash unchanged) and the file present — never missing. *Negative control (pin the branch — pass-2):* the `unlink` is reached **only** on the no-`reversibility_engine` or rollback-throws path, so run the negative control with `reversibility_engine=None` (the live Omen state, recon 0.4) — then pre-fix the file IS missing; do not run it with a working engine, where the file is restored and the bug is masked. |
| G6 | Make `emergency_shutdown` Trigger 2 actually reachable on code-write paths. **Pass-2 found it dead three ways:** (i) the method is `check_shutdown_triggers` (NOT `should_shutdown` — that name doesn't exist), (ii) it has **zero callers**, (iii) `_is_safe_operation` (`emergency_shutdown.py:153-166`) short-circuits to "safe" when `active_tool ∈ SAFE_TOOL_NAMES`, and that whitelist **includes `code_edit`, `git_commit`, `scaffold_module`** (`emergency_shutdown.py:47-54`). So the fix is three parts: remove code-write tools from `SAFE_TOOL_NAMES` (or make `_is_safe_operation` not short-circuit when `target_path` hits a `cerberus_protected_path`); wire a **caller** that invokes `check_shutdown_triggers` with `target_path`+`active_tool` on every write path; keep Trigger 2's path match | `emergency_shutdown.py:47-54,153-166,199-254` + the write handlers (`_code_edit`, `copy_to_production`) | **Three-sided:** (a) after the fix, a `code_edit`/copy toward `modules/cerberus/` reaches `check_shutdown_triggers` and fires — assert fired; (b) *negative control* — pre-fix `grep` shows **zero callers** of `check_shutdown_triggers`; (c) *negative control* — pre-fix, `code_edit ∈ SAFE_TOOL_NAMES` so `_is_safe_operation` returns True and Trigger 2 is skipped even if called. Green requires the fired signal AND both negative controls demonstrated pre-fix. |
| G7 | **Add `sandbox_to_production` to Cerberus `_WRITE_TOOLS`** (`cerberus.py:1277-1281`) so the pre-hook snapshots it too — today only `code_edit` is in the set (and even that is param-broken, see G2) | `cerberus.py:1277-1281` + `_maybe_snapshot` | A `sandbox_to_production` through the live pre-hook produces a snapshot row for the destination; *negative control:* pre-fix, no row (the most dangerous write was unsnapshotted). |

### 5.1 Gates & Autonomy Ledger — Fronts 1/2/4 (Part 3 has its own)

| Move | What goes wrong ungated | Gate | Earned-by |
|---|---|---|---|
| **1.2 `code_review` Apex escalation** (network to Claude API) | Sends code/content to an external API; cost; data egress | Apex's existing dry-run/keys gate + Cerberus `unapproved_external`; escalation only on threshold/`deep=True` | Apex configured with keys; escalation policy in config; Master accepts external-review egress once |
| **1.3/1.4 write of scratch test files** | Clutters/overwrites real code | Writes confined to a `data/` scratch dir; `_is_within_project` + assert not under `modules/`/`tests/` | Path asserted under `data/` before write |
| **2.x self-analysis** | (read-only) leaking a report into the repo or Grimoire with wrong trust level | Report written under gitignored `data/reports/`; if stored in Grimoire, trust level = "research context"/internal, never "training data" | Output path asserted gitignored; Grimoire trust level set |
| **4.1 diagnostics runner** | A "read-only" command that actually writes/starts a test | Exact-argv allow-list, empty until Master fills it; denied-flag set | Master-approved allow-list committed to config |
| **4.2 host-write proposal** | Omen executes a host change autonomously | Proposal-only tool with no execution branch; execution is a separate `never_autonomous`, Master-run tool | Master runs/approves each; scope widened only by explicit Master change to config |
| **`git_commit` (auto)** | Autonomous commit to Shadow's history; sweeps unrelated dirty files; contradicts "don't commit if tests fail" | Route through G1 (enforced approval) + a test-green precondition; never `git push` (hard) | G1 live; commit only after relevant suite green on the new path; push remains Master-manual `--no-ff` |
| **`model_pull`** | Downloads arbitrary model over network to host disk | `never_autonomous` + G1 enforcement + disk-space precondition | G1 live; Master approves the specific model+size |
| **TestGate `create_checkpoint` auto-commit** | Sweeps all dirty files into an auto-commit as a side effect | Scope the checkpoint to the files under change; or stash-based checkpoint; log the checkpoint hash to Master | Checkpoint limited to the change set, or Master accepts full-tree checkpoint semantics |

---

## Abort conditions (Fronts 1/2/4)

- **A1 — Baseline suite is RED.** Before any move that depends on a green
  baseline (1.4 verification, any TestGate path), run `pytest tests/ -x -q`.
  If it is not green, **STOP and flag**: gates that require a green baseline
  cannot be honestly verified, and TestGate will block every promotion for the
  wrong reason. Report the exact failing tests; do not "fix to green" by
  skipping/deleting (CLAUDE.md Fix Quality Rule). This is the single most likely
  early abort — CLAUDE.md itself records 17 failing + 2 errors.
- **A2 — Model path unavailable.** If neither local Gemma nor Apex is reachable,
  Front 1's review is `structural-fallback` only; mark Front 1 **BLOCKED** on
  model availability rather than shipping a stub relabeled as a review.
- **A3 — A "read-only" diagnostic mutates.** If any allow-listed command in 4.1
  is found to write, halt the diagnostics build and return to the allow-list.
- **A4 — Front 2 wants to write.** Front 2 is proposal-only. If any move in
  Front 2 would edit code, that is a scope violation → stop; that work belongs
  to Front 3's gated pipeline.
- **A5 — Plan-vs-reality divergence.** If recon's `file:line` anchors don't
  match the tree the executor sees, STOP and re-anchor before building. **Do not
  abort on line drift alone** — anchors are named by symbol as well as line
  (e.g. "`module.execute` in `_step5_execute`", "the `urlopen` in
  `_code_generate`"); confirm by the *symbol*, and only abort if the symbol/
  behavior itself is absent (the tree genuinely diverged), not merely because a
  line number moved. (This plan's own first draft mis-anchored `_code_generate`
  at `omen.py:2830` when it is at `:3176`; the red-team caught it — re-anchor,
  don't abort.)
- **A6 — TestGate auto-commit fires before its gate is built.** If any Front-1/2
  move would invoke `sandbox_to_production`/`TestGate.execute_with_gate` (which
  triggers the `git add -A` + commit checkpoint, `test_gate.py:134-141`) **before**
  the §5.1 checkpoint-scoping gate is built, STOP — an autonomous full-tree
  commit would fire mid-verification. Fronts 1/2/4 must not call the promotion
  path at all; if a move appears to, that is a scope error → halt.

## Verification runs (Fronts 1/2/4) — when, and what pass looks like

1. **Collection (before build):** the 0.8 `--collect-only` command. Pass = a
   total count, zero collection errors.
2. **Baseline (before build):** `pytest tests/ -x -q`. Pass = green (or the
   exact red set recorded and A1 invoked).
3. **Front 1 (after 1.2/1.3):** the 1.4 known-bad-code run. Pass = **4/4**
   planted defects found at the right line (including the semantic logic-inversion
   file (d) that structural analysis cannot catch), severity ≥ high, applyable
   `proposed_fix`, and **`driver ∈ {gemma-local, apex}` on every file — a
   `structural-fallback` result is a FAIL, not a pass**. `git status` unchanged
   across the run.
4. **Front 1 targeted tests:** run only the Omen test files touched
   (`test_omen.py`, `test_code_analyzer.py`, plus any new review test) —
   `pytest tests/test_omen.py tests/test_code_analyzer.py -q`. Pass = green.
   (CLAUDE.md: run only the files for the task, not the full suite.)
5. **Front 2 (after 2.x):** the 2.3 run against `_maybe_snapshot`; `git status`
   empty before and after (read-only proof). Pass = report produced, tree
   unchanged, param-mismatch finding present (or logged miss + Apex re-run).
6. **Front 4 (after 4.1):** allow-list runner executes `df -h`, refuses an
   off-list command. Pass = both behaviors observed; no host write.
7. **Front 5 gate repairs (G1–G6):** each row's "Verify" column, each of which
   fails on a broken result (e.g. G1 green only if the tool did NOT execute).

---

## Red-team record (Fronts 1/2/4/5)

A fresh attacker followed this plan blind and verified 15 load-bearing
`file:line` claims against the live tree (14 held exactly; 1 was wrong — see
below). Full report: `wargames/red-team/omen.md`.

**The recon error it caught (CRITICAL, and the most valuable finding):** the
first draft stated as settled fact that `_code_generate` is template-only with
no model call, anchored at `omen.py:2830`. It is actually at `omen.py:3176` and
makes a **live local-Gemma Ollama call** (`omen.py:3199,3242,3249`). My grep had
stopped at an early `return` guard. **Patch:** §0.2 corrected — code *generation*
is model-driven today; only code *review/analysis* is heuristic (the real Front-1
gap). Abort A5 was rewritten to re-anchor on drift rather than abort, since a
moved line number is not a diverged tree.

**The gate-verification error it caught (CRITICAL, structural):** G1's original
verify ("assert the tool did not execute") is **circular** — the tool already
doesn't execute today because the RED baseline blocks `sandbox_to_production`
(`test_gate.py:260`), so the test passes while `orchestrator.py:5211-5223` stays
untouched and the danger goes live the moment the baseline turns green. **Patch:**
G1's verify became a baseline-independent unit test with a positive control (ALLOW
→ executes) and a negative control (pre-fix code fails the test). The same
non-circular discipline was applied to G3 and G6, and a preamble was added to
§5.0 forbidding verifications that pass on the current broken behavior.

**Other landed breaks and their patches:** Front 5 never added
`sandbox_to_production` to Cerberus `_WRITE_TOOLS` (leaving the most dangerous
write unsnapshotted) → new repair **G7**; §1.4's pass could go green on a
`structural-fallback` stub firing off keyword-detectable planted bugs → §1.4 now
requires a real model driver **and** a fourth *semantic* bug (logic inversion)
that structural analysis cannot catch; Front 2's `git status` read-only proof
couldn't catch writes into gitignored `data/` or Grimoire → the proof is now
three-part (git + `data/` mtime-snapshot + Grimoire/Chroma row counts); §2.3's
escalation fork demanded a cross-file bug a file-scoped audit can't find → it now
targets two file-local bugs with concrete observations; the TestGate `git add -A`
auto-commit hazard → **Abort A6** plus a `git status` guard on Move 1.4.

**What held:** the plan's core enforcement diagnosis (the decorative
`APPROVAL_REQUIRED` chain, all `file:line`-verified) and the
`never_autonomous → APPROVAL_REQUIRED` routing trace — the attacker called these
"the spine, and they are sound." No move the plan *authors* was ungated.

### Pass 2 (confirmation) — patches held; one HIGH residual, no CRITICAL

A fresh attacker re-ran the patched Fronts plan blind. Verdict: **the four pass-1
fixes all survive** — §0.2 is now correct (re-verified `_code_generate`'s Ollama
call and that `code_review`/`CodeAnalyzer` have no model), G1/G3/G4/G6/G7 are
genuinely non-circular, §1.4's semantic bug (d) is un-fakeable by the structural
stub, and the three-part Front-2 proof catches `remember()`'s SQLite+Chroma
writes. Drift check clean (386 tests, 0 errors). Landed:
- **HIGH:** Move 2.1 named `code_analyze_self` as a read-only building block, but
  that tool **always writes Grimoire** (`omen.py:2637`, `remember(trust_level=
  0.9)`) — so the read-only proof correctly fires Abort A4 on move one. → Patched
  with a tool-choice directive: the audit uses write-free `code_analyze_file`/
  `code_analyze_dir` + `code_review`, never `code_analyze_self` (or builds Omen
  with `grimoire=None`).
- **MEDIUM:** G1's two named enforcement points missed the async worker
  (`async_tasks.py:250-252`, direct `module.execute` with no Cerberus when
  `_orchestrator is None`). → G1 now covers all three dispatch entries.
- **MEDIUM:** G5's negative control only reproduces on the no-snapshot/rollback-
  throws branch. → G5 verify pins the induced failure to `reversibility_engine=
  None` (the live state).
- **LOW ×2:** `has_docstrings` quote corrected to include `'''`; §1.4 needs an
  apply-and-recheck step compatible with the `git status`-unchanged guard.

The attacker's verdict: "the spine is sound and no move the plan authors is
ungated"; with the Move 2.1 directive added, the plan is DONE-able. Honest
status: Fronts patches from both passes are in; the pass-2 residual was HIGH (not
CRITICAL) and is closed.
