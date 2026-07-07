# Red-Team Pass 2 — Omen Fronts 1/2/4/5 (`wargames/plans/omen.md`)

**Role:** second-pass attacker. Played the Opus 4.8 executor following the *patched*
plan blind. Verified every load-bearing `file:line` against the live tree (read-only:
grep / Read / `pytest --collect-only`). Mutated nothing. Did not read any sentinel file.

**Bottom line:** the pass-1 patches **hold** on the four claims they set out to fix
(§0.2 recon, G1/G3/G6 de-circularization, §1.4 hardening, Front-2 three-part proof).
The spine is sound. **But the patches left one real hole and the Front-2 build has an
internal contradiction that a faithful executor will hit on move one.** No CRITICAL.
**One HIGH** (worst residual, named below) and three MEDIUM/LOW.

---

## 1. Is the corrected §0.2 now right? — VERDICT: YES, with one cosmetic misquote

Re-verified every §0.2 anchor:

- **`_code_generate` IS model-driven — CONFIRMED.** `omen.py:3176` defines it;
  `model = params.get("model", self._config.get("code_model", "gemma4:26b"))`
  (`omen.py:3199`); `url = f"{ollama_url}/api/chat"` (`omen.py:3242`);
  `with urllib.request.urlopen(req, timeout=60) as resp:` (`omen.py:3249`).
  Live local-Gemma call. The plan's correction is accurate.
- **`_code_review` is a structural stub with no model — CONFIRMED.** `omen.py:1179-1225`;
  `"note": "Full code review requires LLM (Phase 2+). Structural analysis only."`
  at `omen.py:1217`. No `urlopen`/model call in the body.
- **`CodeAnalyzer` has no model in the judgment path — CONFIRMED.** Only `import requests`
  (`code_analyzer.py:22`) and `resp = requests.get(url, timeout=30)` (`code_analyzer.py:247`),
  used solely to *fetch* a URL. The `"strategy": ["shadow","apex","reaper"]` at
  `code_analyzer.py:975` is a static dict value inside `_suggest_modules_for_pattern`,
  not a call. Plan's claim is exact.

**One new wrong claim introduced (LOW, cosmetic):** §0.2 line 43 and §1.4 line 326
describe the stub as computing `has_docstrings = '"""' in code`. The live code is
`"has_docstrings": '"""' in code or "'''" in code` (`omen.py:1211`) — it also matches
single-quote docstrings. This does **not** weaken the §1.4 (d) argument (see §3), but
the quoted expression is incomplete. Severity LOW — it is a quote, not a gate.

---

## 2. Are G1/G3/G6 now genuinely non-circular? — VERDICT: YES for G1/G3/G6; one repair (G5) has a conditional negative control

For each G-repair I asked: does "Verify" FAIL on the current broken behavior and PASS
only on the fix?

- **G1 — HOLDS, non-circular.** The de-circularized verify stubs the pre-hook to return
  `APPROVAL_REQUIRED` for a benign no-op tool (not one the RED baseline blocks), asserts
  the handler was NOT invoked + a `pending_approval` record exists, with a positive
  control (ALLOW → invoked) and a negative control (pre-fix code fails). I confirmed the
  live pre-hook path handles **only** DENY (`orchestrator.py:5213`) and MODIFY
  (`orchestrator.py:5222`); `APPROVAL_REQUIRED` falls through to `module.execute` at
  `orchestrator.py:5254`. The plan-gate has the same hole: `APPROVAL_REQUIRED` is only
  `logger.info`'d (`orchestrator.py:4642-4649`) then `plan.cerberus_approved = True`
  unconditionally (`orchestrator.py:4651`). I also confirmed `_pre_tool_hook`
  (`cerberus.py:1204-1273`) **never** returns `APPROVAL_REQUIRED` — so the stub is the
  only way to inject it, and the verify genuinely exercises the *new* branch. There is no
  `pending_approval` mechanism anywhere in the tree today (grep: zero hits) — so the test
  is testing the fix, not an accident. **Non-circular. Confirmed.**
- **G2 — HOLDS.** `_maybe_snapshot` reads `tool_params.get("path", "")` (`cerberus.py:1294`)
  while `code_edit` sends `file_path` (`omen.py:1550`). Negative control (pre-fix row
  count +0) is real and load-bearing.
- **G3 — HOLDS, non-circular.** `protected_path_write` in `cerberus_limits.yaml`
  (`applies_to: ["file_write"]`, line 151; reads `path` at `cerberus.py:1232`) does not
  cover `code_edit`/`sandbox_to_production`. The negative control (old `path` key does not
  fire on a `file_path` call) proves the key fix is load-bearing, not cosmetic. Confirmed.
- **G4 — HOLDS.** `PROTECTED_PATHS = {"config", ".git", ".env"}` (`omen.py:443`), no
  `modules/`. Refusal at `omen.py:1571-1575`. Positive control (benign `data/` edit
  succeeds) + broken behavior (modules/ edit succeeds today) = non-circular.
- **G6 — HOLDS, non-circular.** Trigger 2 reads `system_state["target_path"]`
  (`emergency_shutdown.py:245`) and matches `cerberus_protected_paths` (`:248-254`). The
  two-sided verify (fired signal after wiring AND grep-empty pre-fix) is genuinely
  two-sided; the "dormant, not merely untested" negative control is verifiable.
- **G7 — HOLDS.** `sandbox_to_production` is NOT in `_WRITE_TOOLS` (`cerberus.py:1277-1281`
  lists `file_write, file_delete, code_edit, config_update, config_write, db_write,
  db_delete, db_update, email_send, notification_send, webhook_send` — no
  `sandbox_to_production`). Negative control (pre-fix: no snapshot row) is real.

**The one soft spot — G5 negative control is conditional (MEDIUM).**
G5's negative control reads: "*pre-fix, the file is missing after the same induced
failure.*" But `copy_to_production` (`sandbox.py:1073-1147`) only reaches
`dst.unlink(missing_ok=True)` in **two** branches: (i) rollback-via-snapshot *raised an
exception* (`sandbox.py:1141`), or (ii) **no snapshot was taken** (`sandbox.py:1144`,
reached only when `reversibility_engine` is falsy or `dst` didn't pre-exist). When a
snapshot exists AND `reversibility_engine.rollback()` succeeds (`sandbox.py:1136`), the
original bytes are **restored, not missing** — so the negative control's "file is missing"
outcome does **not** occur on that path. An executor who wires a working
`reversibility_engine` (the realistic case) and induces a test failure will see the file
*restored* pre-fix, and the G5 negative control will not reproduce as written — it could
be mis-read as "the bug isn't real." The data-loss is real but only on the
no-snapshot / rollback-throws paths; the verify must pin the induced failure to one of
those two branches or it can silently pass pre-fix. **Severity MEDIUM** — G5 can appear
to fail its own negative control on a benign (snapshot-present) setup, muddying the proof.

---

## 3. §1.4 — can the 4-file test go green on a broken/absent model path? — VERDICT: NO. The guard holds.

Traced the fallback contract against the live stub. The current `_code_review`
(`omen.py:1207-1218`) produces **file-level booleans and counts only**
(`line_count, has_docstrings, has_type_hints, has_error_handling, imports_count,
function_count, class_count, note`) — **zero per-line findings**. Under the plan's new
findings-array contract (Move 1.2), a literal `structural-fallback` therefore emits an
**empty findings array** and flags *none* of (a)-(d). So:

- A structural-fallback run fails §1.4 on **all four** files (not just d) — a safe FAIL,
  not a false green. The `driver ∈ {gemma-local, apex}` pass condition (§1.4 clause 2) is
  the real guard and it holds independently.
- **Is (d) un-catchable by the stub? YES.** Bug (d) — `if balance > 0: raise
  InsufficientFunds` inside a function with a docstring and a `try/except` — sets
  `has_docstrings=True` and `has_error_handling=True` (`omen.py:1211,1213`), i.e. the stub
  reports it *cleaner* than a naive file. The stub has no semantic path and no line-level
  output; it **cannot** coincidentally flag (d). The §1.4 (d) design is sound.
- **The only way the stub could "fake" (a)-(c)** is if the Move-1.2 executor *builds*
  keyword heuristics into the fallback. The plan doesn't ask for that, and even if it did,
  clause 2 (`driver != structural-fallback`) would still FAIL such a run. Closed.

**Residual nit (LOW):** §1.4 requires each proposed_fix, "applied, removes the defect,"
but gives no mechanism to *apply-and-recheck* under the read-only constraint (Move 1.4
asserts `git status` unchanged). Verifying "the fix removes the defect" implies editing a
scratch file and re-running review — fine under `data/`, but the plan never states the
apply step runs in the `data/` scratch dir. Minor ambiguity, not a hole.

---

## 4. Front 2 three-part proof — does it catch every write channel? — VERDICT: the proof CATCHES the write, but the plan hands the executor a tool that trips its own abort. **HIGH.**

The three-part read-only proof (git porcelain + `data/` mtime-snapshot + Grimoire/Chroma
row counts) is well-constructed: `remember()` (`grimoire.py:675`) writes **both** SQLite
and ChromaDB, so part (c) checking both counts is correctly aimed. **The proof itself does
not miss the write.** The break is one level up:

- **Move 2.1 (plan line 373-374) names `code_analyze_self`, `code_analyze_dir`,
  `code_analyze_file` as the Front-2 building blocks** and says "Front 2 composes these
  with the upgraded `code_review` over a file list," with the expected observation being
  "running the Front-2 audit **over `modules/omen/`**."
- **`_code_analyze_self` unconditionally writes a Grimoire row.** `omen.py:2632-2648`:
  `grimoire.remember(content=json.dumps(analysis...), source="self_analysis", ...,
  trust_level=0.9, ..., check_duplicates=False)`. Every call adds a SQLite row **and** a
  Chroma vector (`grimoire.py:675`). The tool's own docstring (`omen.py:2568`) says "The
  full per-file analysis is **stored in Grimoire** for later retrieval."
- **The contradiction:** Move 2.1 asserts "Front 2 does **not** call `remember()` — assert
  row counts equal before and after," and the natural way to satisfy the expected
  observation ("audit over `modules/omen/`") is `code_analyze_self` — which is the *one*
  Front-2 tool that DOES call `remember()`. A faithful executor building Move 2.1 as
  written reaches for `code_analyze_self`, runs the three-part proof, sees Grimoire +1 and
  a Chroma +1, and hits **Abort A4** on the very first Front-2 run — with **no guidance**
  in the plan that this is expected, that `code_analyze_self` must be avoided, or that a
  `grimoire=None` config is required to neuter it. The plan lists the offending tool as a
  building block and simultaneously writes a proof that aborts on it.
- **Trust-level angle (secondary):** even the §5.1 Front-2 gate row demands Grimoire trust
  "research context/internal, never training data." `code_analyze_self` writes
  `trust_level=0.9` (`omen.py:2642`) — high trust, not "research context." So if the
  executor *does* let it write, it violates the §5.1 trust gate too.

**Other write channels in the Front-2 tool set — checked, and the proof would catch them:**
- `code_analyzer.store_learnings` → `remember(trust_level=0.3)` (`code_analyzer.py:400`).
  Not auto-called by `analyze_file`/`analyze_directory` (it's a separate method), so a
  file-scoped audit doesn't reach it — but if it did, part (c) catches it.
- `code_analyzer.analyze_url` → `save_path.write_text(source)` into
  `data/research/code_samples/` (`code_analyzer.py:267-268`, `_samples_dir` default
  `data/research/code_samples` per `omen.py:463`). This writes **under `data/`**, so part
  (b) (the `data/` mtime-snapshot) catches it — but note it is NOT the single intended
  `data/reports/self_analysis/<ts>.json` file, so part (b) would flag it as an unexpected
  delta → A4. Only reachable if the audit fetches a URL (Front 2 audits local files, so
  unlikely), but worth recording as a `data/`-write channel distinct from the report.

**Net for point 4:** the proof is *sound* (it catches every write channel I found). The
**HIGH** is that the plan's own Move 2.1 tool selection (`code_analyze_self`) guarantees
the proof fires A4 on move one, and the plan gives the executor no way through — it is a
**trigger-less contradiction**: build the audit as specified → abort immediately, with no
branch telling the executor to swap the tool, pass `grimoire=None`, or treat the write as
expected. A plan should not name a mutating tool as a read-only building block.

---

## 5. NEW vague observations / trigger-less forks / unenforced gates / missing aborts the patches introduced

- **(HIGH — the worst residual, see §4)** Move 2.1 lists `code_analyze_self` as a Front-2
  building block while `code_analyze_self` (`omen.py:2637`) always calls
  `grimoire.remember()`. Trigger-less contradiction: faithful build → instant A4 with no
  documented path forward. **This is the single worst residual break.**

- **(MEDIUM) G1 is scoped to two enforcement points and misses the async direct-execute
  fallback.** G1 names `orchestrator.py:4642-4651` and `:5211-5223`. But the async worker
  has a second execution path: when its `_orchestrator` is `None` it calls
  `module.execute(tool_name, params)` **directly, with no pre-hook and no Cerberus**
  (`async_tasks.py:250-252`). The comment at `async_tasks.py:51-52` claims "a deferred task
  cannot bypass Cerberus," but that only holds when the orchestrator is wired
  (`async_tasks.py:241`, `run_deferred_through_graph`). A task submitted through the async
  queue (`orchestrator.py:5229`) whose worker was built without an orchestrator ref
  executes ungated — G1's fix in the two named points would not cover it. Pre-existing
  condition, **not introduced by the patches**, but G1's "Verify" (a unit test on the
  step-5 path) would report PASS while this fallback stays ungated. Flagging as a
  G1-completeness gap the patch did not close.

- **(MEDIUM) G5 negative control is conditional** — see §2. On a snapshot-present setup
  with a working rollback, the pre-fix file is restored, not missing, so the negative
  control "file is missing" does not reproduce. The verify must pin the induced failure to
  the no-snapshot or rollback-throws branch (`sandbox.py:1141` / `:1144`) or it can pass
  pre-fix and understate the bug.

- **(LOW) §0.2/§1.4 misquote** `has_docstrings` (omits the `or "'''" in code` clause,
  `omen.py:1211`). Cosmetic; does not affect the (d) argument.

- **(LOW) §1.4 "proposed_fix, applied, removes the defect"** has no stated apply-and-recheck
  step compatible with the `git status`-unchanged guard. Implied to run in the `data/`
  scratch dir but not spelled out.

**Drift check (clean):** `pytest --collect-only` over the 9 Omen files returns **386 tests,
0 collection errors** — matches recon §0.8 exactly. No anchor drift found; every
`file:line` in §0.2, §0.3, §0.4, and G1-G7 verified to the line.

---

## Single worst residual break — run-through

**Front 2, Move 2.1, first run. Severity HIGH.**

1. Executor reads Move 2.1: "running the Front-2 audit **over `modules/omen/`** returns a
   findings report." The composed tools are `code_analyze_self` / `code_analyze_dir` /
   `code_analyze_file` (plan line 373-374). "Audit over `modules/omen/`... know your own
   code" maps most directly to `code_analyze_self` (`omen.py:2565`).
2. Executor snapshots the three-part baseline (git porcelain, `data/` mtime, Grimoire +
   Chroma counts), runs `code_analyze_self`.
3. `code_analyze_self` reaches `omen.py:2632-2648` and calls
   `grimoire.remember(source="self_analysis", trust_level=0.9, check_duplicates=False)`.
   That writes one SQLite row and one Chroma vector (`grimoire.py:675`).
4. Post-run, part (c) shows Grimoire row count +1 and Chroma collection +1. Per Move 2.1:
   "*Any other delta = Front 2 wrote where it must not; Trigger → Abort A4.*"
5. Executor aborts A4 ("Front 2 is proposal-only, it must not mutate memory") on the very
   first Front-2 action. The plan offers **no** branch: it does not say to avoid
   `code_analyze_self`, to construct Omen with `grimoire=None`, or that this write is
   expected. Front 2 is dead on arrival as written.

**Why it matters:** the pass-1 fix correctly *added* the Grimoire/Chroma count to the
proof — that part is good. What the patch did **not** do is reconcile the newly-sharpened
proof with the plan's own tool list. The proof now catches a write that the plan's own
Move 2.1 building block *makes by design*, and the plan never routes around it. The fix
closed the detection gap and opened a build-vs-proof contradiction.

---

## Verdict for the author

The four things the pass-1 patch set out to fix all **hold** under attack: §0.2 recon is
now correct, G1/G3/G6 (and G4/G7) are genuinely non-circular with working positive+negative
controls, §1.4's `driver`-gate makes the semantic bug (d) un-fakeable by the stub, and the
three-part Front-2 proof catches every write channel I could find. I attacked the §1.4
semantic-bug bypass and the G1 circularity hardest — both held cleanly.

**I could not land a CRITICAL.** I did land **one HIGH** (Front-2 Move 2.1 names a
mutating tool, `code_analyze_self` → `grimoire.remember` at `omen.py:2637`, as a read-only
building block, so a faithful build aborts A4 on move one with no documented path forward)
plus MEDIUM issues on G1-async-fallback completeness and G5's conditional negative control.

If the author (a) adds a one-line directive to Move 2.1 that `code_analyze_self` must not
be used for the read-only audit, or must be run with `grimoire=None` / the write suppressed,
and (b) pins G5's induced failure to the no-snapshot/rollback-throws branch, and (c) notes
the async direct-execute fallback (`async_tasks.py:250-252`) as a G1 out-of-scope caveat —
the plan is DONE. The spine is sound; these are seams, not structural failures.
