# Wargame Plan — Omen Part 3: Self-Repair & Self-Recreation (the crown, gated)

> **This is a wargame, not an execution.** The route below is for the Opus 4.8
> executor. Nothing here mutates state.
>
> **Split rationale (also in LEDGER):** Front 3 is a mission in itself. Its gates
> are the highest-stakes lines in the whole kit — a single ungated or
> unrecoverable write to Shadow's own code is a catastrophic, possibly
> irreversible failure, and the abliterated model has no refusal backstop. It
> gets its own plan and its own red-team so the self-modification pipeline is
> attacked in isolation, not buried under Fronts 1/2/4.
>
> **Read Part 1 §0 first.** Every recon fact this plan stands on is proven there
> with `file:line`. The load-bearing ones are restated inline.

---

## The honest premise (do not skip — it reshapes the whole pipeline)

Three recon findings from Part 1 §0.3–0.4 set the entire design. If the executor
does not internalize them, it will build a pipeline that *looks* gated and
isn't:

1. **The sandbox is not a sandbox.** `CodeSandbox.execute`
   (`sandbox.py:559-691`) is `subprocess.run([python, code_file], timeout,
   env=stripped, cwd=exec_dir)` (`sandbox.py:642`) plus a static AST/regex
   blocklist (`validate_code_safety`, `sandbox.py:796-918`) and an `RLIMIT_AS`
   memory wrapper. **No process namespace, no seccomp, no chroot, no network
   namespace.** The blocklist is trivially bypassable (`__import__`,
   `getattr(os,'sys'+'tem')`, `eval`/`exec`, `importlib`, computed non-literal
   paths — only *literal* absolute-path `open()`/`Path()` args are flagged,
   `sandbox.py:859-881`; a `SyntaxError` returns `safe=True`,
   `sandbox.py:817`). **Consequence:** the sandbox cannot be trusted as the
   containment boundary for code the abliterated model authored. The real
   backstops are the test gate, the snapshot, and Master's review — plan as if
   nothing downstream of code generation refuses a malicious or broken change.

2. **The advertised snapshot gate on promotion is dead code.**
   `_sandbox_to_production` reads `reversibility = self._config.get(
   "reversibility_engine")` (`omen.py:2856`), and **nothing wires
   `reversibility_engine` into Omen's config** (grep of `modules/shadow/` +
   `config/` returns zero). So in `copy_to_production`
   (`sandbox.py:1073-1147`), the `if reversibility_engine and dst.exists()`
   snapshot (`sandbox.py:1112`) **never runs**, and on a post-copy test failure
   against an existing file the rollback path is `else: dst.unlink()`
   (`sandbox.py:1144`) — **it DELETES the production file rather than restoring
   it.** The docstring "Goes through Cerberus approval via ReversibilityEngine
   snapshot" (`sandbox.py:1083-1084`) is false in the running system.

3. **The approval verdict is unenforced.** `sandbox_to_production` is
   `never_autonomous` (→ Cerberus returns `APPROVAL_REQUIRED`), but the
   orchestrator only enforces `DENY`; `APPROVAL_REQUIRED` falls through to
   execution (`orchestrator.py:5211-5223`, `:4642-4651`). The pre-hook
   (`cerberus.py` `_pre_tool_hook`) is rule-driven and lists no Omen write tool,
   so it returns `ALLOW`. **Today, the only thing that stops an autonomous
   `sandbox_to_production` is `TestGate` — and only because the baseline suite
   is currently RED (`test_gate.py:260`), which makes it refuse every promotion
   for the wrong reason.** Remove the red baseline and the gate opens.

**Therefore Part 3's first job is to replace three fake gates with real ones,
then build the capability on top.** Full capability, hard gates, both present.

### The fourth premise the red-team found (the wall beside the door)

A gated pipeline for `sandbox_to_production` is **worthless if a second,
ungated tool reaches the same production bytes.** It does. **`code_edit` is
classified `autonomous`** (`config/cerberus_limits.yaml:223`) and its only guard
is `Omen.PROTECTED_PATHS = {"config", ".git", ".env"}` (`omen.py:443`), which
does **not** include `modules/`. So an executor told "fix a bug in Omen's own
code" calls `code_edit(file_path="modules/omen/omen.py", …)` and reaches
`path.write_text()` (`omen.py:1606`) with **no snapshot, no test, no approval,
no checkpoint** — the entire pipeline below is *bypassed*, never entered.
`git_commit` is likewise `autonomous` (`cerberus_limits.yaml:227`, despite its
"requires approval" docstring at `omen.py:1280`) and defaults to `git add -A`,
so a bad edit can be auto-committed. **The pipeline guards a door; these tools
are the missing wall beside it.** Stage 0 closes them BEFORE any self-mod runs.

### The fifth premise the red-team found (pass 3) — the wall has no floor

**This is the most important finding in Part 3, and it is load-bearing for
whether the crown capability can run at all on the current host.** Two passes
closed two bypass roads (`code_edit`, `sandbox_to_production`) by guarding tool
*destinations*. Pass 3 proved that is not enough, because the real threat is not
a tool whose *handler* writes a path — it is a tool that **executes
model-authored code**, and that code can write anywhere the process can.

- `sandbox_execute` and `code_execute` run authored code via
  `CodeSandbox.execute` → `subprocess.run([python, code_file], cwd=exec_dir,
  env=safe_env)` (`sandbox.py:642-649`) with **no chroot, no namespace, no
  seccomp, same user, full host filesystem write access** (premise 1). The
  static validator only flags a **literal `ast.Constant` absolute path**
  (`sandbox.py:859-881`) and returns `safe=True` on a `SyntaxError`
  (`sandbox.py:817`). So a sandbox program that does
  `open("../../modules/omen/omen.py", "w")` (a **relative traversal** from
  `data/sandbox/<uuid>` — not absolute, never flagged) or a computed path
  overwrites Omen's or Cerberus's production source with **no snapshot, no test,
  no approval, no shutdown.** `code_execute` is `autonomous`
  (`cerberus_limits.yaml:217`); `sandbox_execute` is router-dispatchable.
- **No tool-destination guard can close this**, because the write does not happen
  in a tool handler — it happens inside opaque executed code. The closure
  principle's arms ("refuse a destination" / "be pipeline-only") are both framed
  around a handler's own write, so they structurally miss the executed-code road.
  The same is true of every test-runner the pipeline itself invokes
  (`pytest tests/` runs repo code that can write repo files).
- **The only real containment for executed code is the OS, not Cerberus.**
  Executed code can be bounded from writing `modules/**`/`config/**`/`.env` only
  by running it under **OS-level isolation**: an unprivileged user with a
  **read-only bind-mount** of the repo, or a namespace/container/seccomp/
  `bwrap`/`firejail` jail with no write mount over the source tree. The current
  sandbox provides none of this.

**Consequence (honest terminus):** with the sandbox as it exists today, the
self-mod pipeline **cannot** be made "the only road" to a `modules/**` write —
`sandbox_execute`/`code_execute` are always a road, and the abliterated model has
no refusal backstop. Therefore **Part 3 is BLOCKED** (see Abort B9) until either
(a) code-execution tools run under real OS isolation that physically prevents
writes to the protected tree, or (b) `sandbox_execute`/`code_execute` are
themselves reclassified `never_autonomous` and gated — AND that isolation
substrate is an **architecture decision for Master/an Opus session, not a Claude
Code build** (CLAUDE.md: "Architecture decisions happen in Opus sessions"). The
plan below is complete and correct; it may not *run* until this floor exists.

- **RECON NEEDED (host — settle before Part 3 can leave BLOCKED):** what
  isolation can Citadel provide for code execution? Check for `bwrap`
  (`which bwrap`), `firejail` (`which firejail`), unprivileged user namespaces
  (`cat /proc/sys/kernel/unprivileged_userns_clone` / `sysctl
  kernel.apparmor_restrict_unprivileged_userns`), and whether a dedicated
  low-priv `shadow-sandbox` user with a read-only bind-mount of
  `~/dev/Shadow/modules` + `config` is acceptable to Master. Put the exact
  results to Master; do not invent the isolation mechanism.

---

## The gated pipeline (the capability, planned in full)

Omen proposes a change to Shadow's own code (bug fix / refactor / new capability
/ an improvement to Omen itself), and it travels this pipeline. Every stage is a
gate; no stage is skippable; each gate is *wired*, not merely named. **Stage 0 is
a precondition: the pipeline is the *only* road to a write to Shadow's own code.**

```
 [STAGE 0: close EVERY bypass road — enumerate all write-capable tools, gate each, else ABORT]
 PROPOSE → SNAPSHOT → SANDBOX-WRITE+TEST → RELEVANT-SUITE-GREEN(new path)
        → MASTER DIFF APPROVAL → PROMOTE(commit, no push) → [ROLLBACK on any failure + FAILURE-LOG]
```

### Stage 0 — Close the bypass roads (PRECONDITION / GATE 0; without it, do not run Part 3)
The pipeline must be the **only** way to write `modules/**`, `config/**`, or
`.env` (Shadow's own code/config). **Pass-1 found the `code_edit` road; pass-2
found the `sandbox_to_production` road. Do not close them one at a time — close
them by PRINCIPLE:**

> **The closure principle (pass-3 corrected — "can CAUSE a write," not "handler
> writes a path"):** enumerate **every tool in `Omen.get_tools()` that can cause a
> write to a protected path — directly OR transitively through code it executes.**
> Two classes, closed differently:
>
> **Class 1 — handler-writers** (`code_edit`, `sandbox_to_production` via
> `copy_to_production`, `git_commit`; verify `scaffold_module`/`scaffold_test`/
> `code_generate` — recon shows they return code as *content* and do **not**
> write disk): for each, one of two must hold — (a) it **refuses** a destination
> under `modules/**`/`config/**`/`.env` when invoked autonomously, **or** (b) it
> is reachable **only** as an internal step of this pipeline. A tool failing both
> is an open bypass road → **Abort B0.**
>
> **Class 2 — code-executors** (`sandbox_execute`, `code_execute`, `code_test`,
> and every test-runner the pipeline itself invokes): a destination guard does
> NOT close these — the write happens inside executed code, not the handler
> (premise 5). They are closed ONLY by (a) **OS-level isolation** that physically
> prevents executed code from writing the protected tree (unprivileged user +
> read-only bind-mount, or namespace/seccomp/`bwrap`), **or** (b) reclassifying
> them `never_autonomous` and gating them. **Until one of those exists, Part 3 is
> BLOCKED (Abort B9)** — no destination list can substitute.
>
> Verification #0 must probe BOTH classes, and probe Class 2 *actively* (run a
> sandbox program that attempts a traversal write and assert it is blocked), not
> merely check a handler's guard.

The specific closures required today, each mapping to a Front-5 §5.0 repair:
1. **`code_edit` cannot write `modules/**`/`config/**`/`.env` autonomously**
   (G4): extend `Omen.PROTECTED_PATHS` (`omen.py:443`) accordingly. (Pass-2
   confirmed G4's `.resolve().relative_to()` prefix check at `omen.py:1564-1575`
   resists `../`, absolute paths, symlinks, case-folding — it is robust once the
   prefix set is extended.)
2. **`sandbox_to_production` cannot write a protected destination** (G5, now a
   *bypass-road closure*, not merely a rollback fix): `copy_to_production`
   (`sandbox.py:1096-1147`) today validates only that the **source** is inside
   the sandbox — the **`production_path` destination has zero guard**, so
   `sandbox_to_production(production_path="modules/cerberus/cerberus.py")`
   overwrites (or, via `dst.unlink()` at `sandbox.py:1141/1144`, **deletes**)
   production Cerberus ungated. Add a destination `PROTECTED_PATHS` check mirror
   of `code_edit`, AND make the raw tool refuse to run outside the pipeline
   sequence (require a Stage-S checkpoint token in params, absent on a raw call).
3. **`git_commit` is gated** (G1 + §5.1): routed through the enforced approval
   hold and a test-green precondition; never `git add -A` blind — commits scoped
   to the approved change set. No autonomous commit of a self-edit.
4. **The pre-hook actually inspects these tools** (G2/G3): the `protected_path_
   write` rule's `applies_to` includes `code_edit` **and** `sandbox_to_production`
   and reads the **correct param key** (`file_path`/`production_path`, not
   `path`), with protected paths covering `modules/cerberus/`, `modules/omen/`,
   `modules/shadow/`, `config/`, `.env`.
5. **Emergency self-modification trigger is live on write paths** (G6 —
   pass-2 found it dead-on-arrival, see the corrected G6 in Part 1 §5.0): the
   method is `check_shutdown_triggers` (NOT `should_shutdown` — that name does
   not exist), it currently has **zero callers**, and it short-circuits via
   `_is_safe_operation` (`emergency_shutdown.py:153-166`) which returns "safe"
   whenever `active_tool ∈ SAFE_TOOL_NAMES` — a whitelist that **includes
   `code_edit`, `git_commit`, `scaffold_module`** (`emergency_shutdown.py:47-54`).
   So today a write straight at `modules/cerberus/` is whitelisted past Trigger 2
   even if the evaluator were called, which it never is. G6 must therefore (i)
   remove the code-write tools from `SAFE_TOOL_NAMES` (or make `_is_safe_operation`
   not short-circuit when `target_path` hits a `cerberus_protected_path`), AND
   (ii) wire an actual caller that invokes `check_shutdown_triggers` with
   `target_path`+`active_tool` populated on every write path.
- **Expected observation (each a G-repair verification from Part 1 §5.0, all
  green):** `code_edit` AND `sandbox_to_production` both refuse a destination
  under `modules/omen/`; a stubbed `git_commit`/promotion is held pending
  approval **in the real dispatch loop** (not a stub — see Verification #0); the
  pre-hook DENY/holds a `code_edit` and a `sandbox_to_production` toward
  `modules/cerberus/`; a write toward `modules/cerberus/` reaches
  `check_shutdown_triggers` and fires (proving the whitelist no longer
  short-circuits it and a caller exists).
- **ABORT B0 (hard):** if **any** enumerated write-capable tool is not closed by
  (a) or (b), **Part 3 does not run.** A gated pipeline beside any ungated write
  tool is security theatre — the executor would reach a production write to
  Shadow's own
  code without the pipeline. Stop and flag; build Stage 0 first.
- **Most likely failure:** the executor treats Stage 0 as optional setup and
  proceeds to Stage P on a tree where `code_edit` is still autonomous. Counter:
  Stage P's first action asserts the four Stage-0 conditions and refuses to
  produce a proposal until they hold.

### Stage P — Propose (ungated; Front 2 feeds this)
Omen produces a change proposal: `{target_file, git_blob_hash, diff,
rationale_summary, driver ∈ {gemma-local, apex}, risk_tier}`. The diff is
produced against a specific blob hash (Front 2 §2.1) so a stale proposal is
detectable. **No write yet. Stage P refuses to run unless the four Stage-0
conditions are verified true (re-checked here, not assumed).**
- **Expected observation:** a proposal object exists; `git status --porcelain`
  is empty (nothing written); the Stage-0 assertion block passed.
- **Failure:** the proposal is generated against an unsaved buffer, so the blob
  hash doesn't match `git hash-object <file>`. Counter: Stage S refuses to
  proceed if `git hash-object target_file` ≠ the proposal's `git_blob_hash`
  (staleness gate).
- **Ceiling honesty + the driver trigger (B-10 fix — mechanical, not a judgment
  call):** proposal *quality* is bounded by `driver`, and which driver is used is
  decided by a **rule, not the executor's gut**. `driver = "apex"` is **required**
  (not optional) when ANY of these is true; otherwise local Gemma is allowed:
  - `target_file` matches a **high-blast-radius path list** in config — seed it
    with `modules/shadow/orchestrator.py`, `modules/shadow/message_bus.py`,
    `modules/base.py` (defines `ToolResult`), `modules/cerberus/**`, anything
    matching `*gate*`/`*reversibil*`/`*shutdown*`, and Omen's own
    `modules/omen/omen.py`;
  - the diff **adds, removes, OR modifies in place** a `def `/`class `/`return`/
    `if`/`for`/`while`/`try` construct — pass-2 noted an added/removed-line check
    misses in-place inversions (`if allowed:` → `if not allowed:`, or a changed
    `return` expression). Detect via an **AST-level compare** of the two
    versions (compare the parsed condition/return nodes), not a textual line
    diff; any change to a boolean operator, comparison, or return expression on
    any file counts. When in doubt, escalate — the default for an ambiguous diff
    is Apex, not local Gemma;
  - the change is an Omen-modifies-Omen or Omen-modifies-Cerberus case.
  A blind executor editing the dispatch loop can no longer self-assess "this is
  boilerplate" — the path list and the AST-diff check decide. Master's review
  (Stage M) is the real backstop; the plan never implies Omen autonomously
  out-engineers its base model.
- **Expected observation:** the proposal's `driver` field equals what the rule
  dictates for its `target_file`+diff (assert: a proposal touching
  `orchestrator.py` has `driver == "apex"`; a comment-only change to a leaf file
  may have `driver == "gemma-local"`).

### Stage S — Snapshot first (GATE 1: no write without a proven way back)
Before any production byte changes, a verified rollback point must exist. The
current `reversibility_engine`-based path is dead (premise 2), so Stage S uses a
**belt-and-suspenders** checkpoint:
1. **Git checkpoint** (the real one today): a dedicated checkpoint that captures
   the exact pre-change tree state and is *restore-verified* — not just created.
   Prefer a `git stash create`/tag or a checkpoint commit whose hash is
   recorded. **Verify restorability** by confirming the checkpoint object
   exists (`git cat-file -e <hash>`) AND that a dry restore into a temp worktree
   reproduces the original blob hash. A checkpoint that was created but never
   proven restorable does **not** satisfy Gate 1.
2. **Per-file reversibility snapshot** (repair G2/G5 from Part 1 §5.0): wire an
   actual `ReversibilityEngine` into the promotion path and snapshot every
   target file (`reversibility.py:127` `_snapshot_file` does `shutil.copy2`).
   Note `_snapshot_file` raises on a missing file (`reversibility.py:133`), so
   **new files** get no per-file snapshot — for new files the git checkpoint is
   the sole rollback and the rollback action is "delete the new file," which is
   safe (it didn't exist before).
- **Expected observation:** Stage S emits `{checkpoint_hash, snapshot_ids[],
  restore_verified: true}`. `git cat-file -e <checkpoint_hash>` exits 0.
- **Most likely failure:** `create_checkpoint` (`test_gate.py:114-150`) does
  `git add -A` + commit and **sweeps unrelated dirty files** into the
  checkpoint. Cause: full-tree checkpoint semantics. Counter: either scope the
  checkpoint to `target_file` only, or record and surface to Master exactly
  which files the checkpoint swept (so a later rollback doesn't silently revert
  Master's unrelated work). If the tree is dirty with unrelated changes,
  **Trigger → abort and flag** (see Abort B1) rather than commit a mixed
  checkpoint.
- **Gate is real because:** Stage SW refuses to run unless
  `restore_verified == true`, **and** the dirty-tree check is wired *in code*
  before `create_checkpoint` runs — not left to the executor. Build item: add a
  `git status --porcelain` guard at the top of `execute_with_gate`
  (`test_gate.py`) that **raises/aborts** if the tree carries changes unrelated
  to `target_file`, so a mixed checkpoint can never be committed. (B-8 fix:
  today no code does this; the abort exists only on paper.)
- **Verify (B-8, non-circular):** with an unrelated dirty file present, Stage S
  **aborts** and creates **no** commit (`git rev-list --count HEAD` unchanged);
  with a clean tree it proceeds. *Negative control:* pre-fix, `create_checkpoint`
  commits the mixed tree (proves the guard was missing).

### Stage SW — Sandbox write + test (never write production here)
The change is written to a **sandbox file** and exercised in the sandbox, never
to the production path. Given premise 1 (thin sandbox), this stage's value is
*functional smoke-testing*, not *containment* — say so. The containment for the
promoted bytes is Stages T + M, not the sandbox.
- **Expected observation (B-9 fix — a real pass/fail predicate, not "returns an
  exit code"):** the sandbox file exists under `data/sandbox/<uuid>/`, AND
  **the change's own new/updated unit test executes green inside the sandbox**
  (`execute_with_test` exit_code `== 0` with the test's assertions actually run —
  distinguished from an import-resolution failure, which is `!= 0` for an
  *environment* reason and is NOT a pass), AND `sandbox_validate` returned no
  `block`-severity violation the proposal didn't declare. A run that merely
  "returns an exit code" (including a crash or a `SyntaxError`-treated-as-safe,
  `sandbox.py:817`) is **NOT** a pass. If the change has no exercising test,
  Stage SW cannot smoke-test it → treat as **inconclusive**, not pass, and lean
  entirely on Stage T (which then MUST include a test that covers the change, or
  Stage T aborts — see below).
- **Most likely failure:** the change imports a project module that the stripped
  sandbox env can't resolve, so it "fails" for an environment reason, not a code
  reason (false negative). Cause: `_build_safe_env`/`PYTHONPATH`
  (`sandbox.py:749`). Counter: for self-mod of a real module, smoke-test by
  importing under the project venv with `PYTHONPATH` set, and treat
  import-resolution failures distinctly from assertion failures (an env failure
  is inconclusive, not a code verdict).
- **Abort hook:** if `sandbox_validate` reports a `System access`/`Credential
  access` violation the proposal didn't declare, **Trigger → abort** — the model
  authored something it shouldn't (premise 1: no refusal backstop upstream).
  (Note premise 1: the validator is bypassable, so its *silence* is not proof of
  safety — this abort catches the honest case, and Stages T+M+Gate-5 catch the
  rest.)

### Stage T — Relevant test suite green on the NEW path (GATE 2)
The change is applied to the production file **inside the gate's controlled
window**, the **relevant** test suite runs against the *new* code, and it must
be green before promotion is even offered. "Green tests on a bypassed path
certify nothing" — so the suite must exercise the changed file.
- **The composition bug to avoid (recon):** `_sandbox_to_production`
  (`omen.py:2840-2904`) wraps `do_copy` in `test_gate.execute_with_gate`, and
  `do_copy` calls `copy_to_production(require_tests_pass=True,
  run_tests_fn=run_tests)`. So tests run *inside* `copy_to_production` (which
  rolls back / `unlink`s on failure) AND *around* it in `execute_with_gate`
  (which reverts via `git reset --hard`). `execute_with_gate` **ignores
  `change_fn`'s return value** (`test_gate.py:279`). Failure mode: inner tests
  fail → `copy_to_production` rolls back the file → outer post-tests then pass
  on the *restored old* code → `gate_result.allowed == True` → `_sandbox_to_
  production` sets `success = True` (`omen.py:2894`) and **reports a successful
  promotion that never happened.** Counter (build item): collapse to a *single*
  test authority. Recommended: disable `copy_to_production`'s internal
  `run_tests_fn` (pass `require_tests_pass=False`) and let `TestGate` be the one
  test+revert authority, OR have `execute_with_gate` honor `change_fn`'s return.
  Do not run both rollback layers.
- **Relevant vs. whole suite:** today both layers run `pytest tests/ -x -q`
  (whole suite; `omen.py:2861`, `test_gate.py:79`). For a self-mod, "relevant"
  means at minimum the changed module's tests **plus** `test_decision_loop.py`
  if `orchestrator.py` is touched (CLAUDE.md testing rule). Whole-suite is
  acceptable but slow; the gate must assert the changed file's own tests are in
  the run and green, not merely that *some* suite passed.
- **Coverage gate (B-5 fix — "green on the new path" is meaningless if the new
  path is untested):** before promotion is offered, assert the changed file has
  a corresponding test file AND that at least one collected test actually
  imports/exercises the changed symbol. Map `modules/omen/omen.py` →
  `tests/test_omen.py`, etc. **If the changed file has no test, or no collected
  test touches the changed function, ABORT (B-9-cov)** — a suite that passes
  while never executing the change certifies nothing (this is the plan's own
  "green tests guarding a bypassed path" failure). Do not promote an untested
  change; require the proposal to include a test, or hand to Master.
- **Expected observation:** `GateResult.allowed == true`, `post_test.passed >=
  baseline_passed`, `post_test.failed == 0 and errors == 0`
  (`test_gate.py:297-322`), the run's collected tests **include** the changed
  module's test file (assert by name), AND the coverage-gate above passed (a test
  exercising the changed symbol ran).
- **Most likely failure:** baseline already RED (premise 3;
  `test_gate.py:260-273` → `allowed=False, reverted=False`). Cause: pre-existing
  suite failures. Counter: **Abort A1 / B2** — a self-mod cannot be certified
  against a broken baseline; stop and flag, do not proceed.
- **Fork:** if `post_test.passed < baseline_passed` even with 0 failures
  (a test silently *disappeared* — e.g. the change deleted a test or broke
  collection), Trigger → treat as regression, revert, do not promote
  (`test_gate.py:303-308` already does this; assert it fires).

### Stage M — Master's diff approval (GATE 3: no self-mod commit without it)
The exact diff is presented to Master. Promotion to production **and** the commit
happen only on Master's explicit approval. **Never pushed** — Master's manual
`--no-ff` and push stand (CLAUDE.md, non-negotiable, predates this mission).
- This gate does not exist in code today (premise 3: `APPROVAL_REQUIRED` is
  unenforced). Part 1 §5.0 G1 is the build that makes it real: the orchestrator
  must **hold** the promoting step and surface the diff, executing only on
  approval.
- **Expected observation:** with G1 live, a self-mod promotion step reaches a
  `pending_approval` state carrying the diff; the production file is **unchanged**
  (`git hash-object target_file` == the pre-change blob) until Master approves;
  on approval, the change is applied and committed (no push); on rejection, the
  snapshot/checkpoint restores and nothing is committed.
- **Most likely failure:** the diff shown to Master is not the diff that gets
  promoted (a TOCTOU — the proposal changed between display and apply). Cause:
  no re-hash at apply time. Counter: at apply, re-verify `git hash-object
  target_file` still equals the proposal's pre-change blob AND the promoted
  content hash equals the approved content hash; mismatch → abort, do not apply.
- **Gate is real because:** the apply/commit branch is unreachable unless an
  approval record with the matching content hash exists.

### Stage PR — Promote + commit (no push, ever)
On approval: promote the sandbox/approved bytes to the production path, commit
with a descriptive message (no push). The commit is Master-approved, so it does
not violate "don't commit if tests fail" (Stage T is green) or "no push"
(promotion never pushes).
- **Expected observation:** `git log -1` shows the commit; `git status` clean;
  `git log @{u}..HEAD` shows the commit is **unpushed** (ahead of upstream).
- **Failure:** an accidental `git push` in any promotion code. Counter: the deny
  list in `.claude/settings.local.json` blocks `git push*` at the harness level;
  additionally assert no promotion code path invokes push (grep the promotion
  module for `push`). If found, that is an abort-and-flag, not a fix-in-place.

### Stage RB — Rollback on any failure + failure-log (GATE 4: proven recovery)
Any failure at SW/T/M/PR triggers restore from the Stage-S checkpoint/snapshot,
and the failure is written to the failure DB (`omen.py:1839` `_failure_log`,
`omen_failures` table) so Omen learns.
- **Expected observation:** after an induced failure, `git hash-object
  target_file` equals the pre-change blob (original bytes restored), `git status`
  clean, and `failure_search` (`omen.py:1929`) returns the new failure row.
- **Most likely failure (the data-loss one):** premise 2 — with no
  reversibility engine and an existing target, `copy_to_production`'s
  `dst.unlink()` (`sandbox.py:1144`) deletes the file, and if the git checkpoint
  wasn't taken/verified (Gate 1 skipped), the file is **gone**. Counter: Gate 1
  is mandatory and restore-verified before SW; and G5 (Part 1 §5.0) replaces
  `dst.unlink()` with restore-from-snapshot. **Assert:** an induced post-copy
  test failure on an existing file leaves the original bytes intact — never a
  missing file. This is the single most important assertion in Part 3.

---

## The hard case: Omen modifying Omen (extra gate)

When the change target is `modules/omen/*.py` (Omen editing its own code), the
running instance must not saw off the branch it sits on.

- **Why it's dangerous:** the running Python process holds `omen.py`'s bytecode
  in memory. Editing the file on disk does not change the running instance —
  **until** something reimports it or the process restarts, at which point a
  broken edit means Omen fails to load and the pipeline that would roll it back
  is *inside the thing that no longer loads*.
- **SETTLED in recon (red-team confirmed): Shadow does NOT hot-reload modules.**
  `grep -rn "importlib.reload\|reload(\|watchdog\|autoreload\|__import__"
  modules/shadow/` finds no hot-reload machinery. **Consequence:** a bad
  self-edit does not corrupt the *running* instance immediately — it bites on the
  **next process restart**, when a broken `omen.py` fails to import. This is a
  double-edged setting: (a) the running instance keeps working, so there is a
  window to recover; but (b) recovery depends entirely on the on-disk git
  checkpoint, because the running instance's own rollback code is what would
  fail to load next boot. The executor re-runs the grep to confirm no hot-reload
  was added; if it finds any, the immediate-corruption case applies and Gate 5
  becomes even more load-bearing. **Either way, Gate 5 below is MANDATORY, not
  optional** — because the no-hot-reload window is exactly when a silent
  corruption goes undetected until the worst time (a restart).
- **GATE 5 (Omen-modifying-Omen): MANDATORY validation by a SEPARATE run, not the
  instance being modified.** The changed Omen code is tested by spawning a
  **fresh subprocess/interpreter** that imports the *new* `omen.py` and runs the
  Omen test suite against it. The running instance must never certify its own
  replacement. Only if the separate run is green does Stage M offer the diff.
  **This gate does not exist in code today (it is a build item); until it is
  built, no self-mod of a loaded module (`modules/omen/**`, `modules/cerberus/**`,
  `modules/shadow/**`) may run — see Abort B8.**
  - **Expected observation:** a subprocess `python -c "import
    modules.omen.omen"` against the candidate file exits 0, and
    `pytest tests/test_omen.py -q` run in that subprocess is green — both
    observed from a process that is **not** the one being edited.
  - **Most likely failure:** the "separate" run imports the *installed* omen,
    not the candidate (PYTHONPATH points at the live tree). Cause: candidate not
    isolated. Counter: run the validation against a temp worktree/checkout that
    contains the candidate file, with `PYTHONPATH` rooted there; assert the
    imported module's `__file__` is the candidate path, not the live path.
  - **Fork:** if the separate run cannot even import the candidate
    (`SyntaxError`/`ImportError`), Trigger → hard stop, revert, failure-log; do
    not present to Master. A candidate that won't import is not a diff worth
    Master's time.
- **Restart safety:** if the change requires a process restart to take effect,
  the pipeline does **not** restart Omen autonomously — it flags Master that a
  restart is needed and stops. Autonomous self-restart after self-edit is out of
  default scope.

---

## Gates & Autonomy Ledger — Part 3 (the highest-stakes lines in the kit)

| Move | What goes wrong ungated | Gate (wired, not named) | Earned-by |
|---|---|---|---|
| **Stage 0 Class-1 — handler-write roads (`code_edit`, `sandbox_to_production`, `git_commit`)** | A gated pipeline beside an ungated tool that writes `modules/**` is theatre — the crown is walked around (found twice) | `code_edit` + `sandbox_to_production` destination guards to `modules/`/`config/`/`.env` (G4/G5); `git_commit` gated (G1); pre-hook inspects all with correct param key at all 3 sites (G2/G3); Trigger 2 live (G6). **ABORT B0 if any Class-1 road open** | Every Class-1 tool from `get_tools()` closed + verified; Stage P re-asserts before a proposal |
| **Stage 0 Class-2 — code-execution roads (`sandbox_execute`, `code_execute`, test-runners)** | Model-authored code (no refusal backstop) runs as same user with full FS write → writes `modules/**` via traversal, no tool-guard can stop it | **OS isolation** (unpriv user + read-only bind-mount of the source tree, or namespace/seccomp/`bwrap`) so executed code physically cannot write protected paths, OR reclassify these `never_autonomous` + gate. **ABORT B9 if neither exists** | The isolation substrate exists and the Class-2 active probe (traversal write) is BLOCKED; **this is a Master/Opus architecture decision, not a Claude Code build** |
| **Stage S snapshot** | A production write with no way back → irrecoverable corruption | Git checkpoint **restore-verified** + per-file reversibility snapshot; SW refuses unless `restore_verified==true`; dirty-tree guard wired in `execute_with_gate` before any commit | `git cat-file -e <hash>` passes AND a dry restore reproduces the original blob hash; clean-tree precondition enforced in code |
| **Stage SW sandbox write** | Model-authored code (no refusal backstop) executes with host privileges | Runs in `data/sandbox/`; `sandbox_validate` abort on undeclared System/Credential violation; **containment is NOT claimed** — T+M are the real gate | Validation run recorded; treated as smoke-test only |
| **Stage T promotion test** | Green tests guarding the OLD code certify a bypassed path | Single test authority (no double-rollback); assert changed module's tests are IN the run and green; regression = `passed < baseline` reverts | Collection shows the changed file's tests; `post_test.passed >= baseline_passed`, 0 failed/errors |
| **Stage M Master diff approval** | Omen self-modifies without Master in the loop | Orchestrator **holds** the step (G1); apply/commit branch unreachable without an approval record whose content hash matches the shown diff | G1 live; Master approved the exact diff; re-hash matches at apply |
| **Stage PR commit** | Autonomous commit / any push to a remote | Commit only post-approval, post-green; **push denied at harness level** + no push in promotion code | `git log @{u}..HEAD` shows commit unpushed; grep confirms no `push` in promotion path |
| **Stage RB rollback** | Failed promotion deletes an existing file (`dst.unlink()`) | G5: replace unlink with restore-from-snapshot; Gate-1 checkpoint mandatory | Induced-failure test: original bytes intact, never missing |
| **Omen-modifies-Omen (Gate 5)** | Running instance corrupts itself mid-edit; bad edit makes the rollback code unloadable | Validation by a **separate** interpreter against an isolated candidate; no autonomous self-restart | Separate-run import + `test_omen.py` green, verified `__file__` is the candidate; restart flagged to Master, not auto-done |
| **Writes to `modules/cerberus/` or `config/cerberus_limits.yaml`** | Omen disables its own safety governor | `code_edit` PROTECTED_PATHS extended (G4) + emergency-shutdown Trigger 2 wired (G6); such self-mods are **out of scope** for the autonomous pipeline — Master-only | G4/G6 live; a code write to those paths refuses AND raises emergency shutdown |
| **Apex escalation for hard proposals** | Code/content egress to Claude API; cost | Apex keys/dry-run gate + Cerberus external gate; escalation only by policy/`deep=True` | Apex configured; Master accepted external-review egress once |

---

## Abort conditions (Part 3)

- **B0 — Class-1 bypass road still open.** If any handler-write tool
  (`code_edit`, `sandbox_to_production`, `git_commit`, or any write tool the
  `get_tools()` enumeration surfaces) can still write `modules/**`/`config/**`/
  `.env` autonomously — G4/G5 destination guards not live, OR `git_commit`/promotion
  approval not enforced in the real loop (G1), OR the pre-hook doesn't inspect
  these with the correct param key at all three sites (G2/G3), OR Trigger 2 dead
  (G6) — **Part 3 does not run.** Found twice (`code_edit`, `sandbox_to_production`).
- **B9 — Class-2 code-execution road open (pass-3 CRITICAL; the floor under the
  wall).** If `sandbox_execute`/`code_execute` (or any code-executing tool) can
  run model-authored code that writes the protected tree — i.e. there is no OS
  isolation (unprivileged user + read-only bind-mount / namespace / seccomp /
  `bwrap`) AND the tools are not reclassified `never_autonomous`+gated — **Part 3
  is BLOCKED, not merely failed.** No destination guard closes this; the active
  traversal-write probe in Verification #0 must be BLOCKED first. The isolation
  substrate is an **architecture decision for Master/an Opus session** (CLAUDE.md).
  Until it exists, the pipeline is fully planned but MUST NOT run: the abliterated
  model authors the code, and nothing between it and the disk refuses.
- **B1 — Dirty tree at Stage S.** If `git status --porcelain` is non-empty with
  changes unrelated to the proposal, do **not** create a mixed checkpoint —
  stop and flag. The guard is wired in code (Stage SW verify), not left to
  judgment. A checkpoint that sweeps Master's unrelated work makes rollback
  ambiguous.
- **B2 — Red baseline.** `pytest tests/ -x -q` not green before Stage T → stop
  (premise 3). A self-mod cannot be certified against a broken baseline, and
  TestGate will block for the wrong reason.
- **B3 — Data-loss risk realized.** If at any point an existing target file
  would be removed without a verified checkpoint/snapshot, **hard stop** — this
  is the `dst.unlink()` path; never proceed through it.
- **B4 — Candidate won't import (self-mod).** Gate 5 separate-run
  `ImportError`/`SyntaxError` → hard stop, revert, failure-log; do not present
  to Master.
- **B5 — Approval/content-hash mismatch.** At Stage M apply, if the target's
  current hash ≠ the approved pre-change hash, or the content to promote ≠ the
  approved content → abort (TOCTOU); do not apply.
- **B6 — Any `git push` reachable in the promotion path.** Stop and flag; push
  is Master-manual, forever.
- **B7 — Cerberus-path self-mod.** A proposal targeting `modules/cerberus/` or
  `config/cerberus_limits.yaml` → out of autonomous scope; hand to Master.
- **B8 — Gate 5 (separate-run validation) not built.** Recon settled that Shadow
  does **not** hot-reload, so a bad self-edit bites on next restart — but Gate 5
  is what catches it *before* it reaches disk. Until the separate-run validation
  is built, do **not** run any self-mod of a loaded module
  (`modules/omen/**`, `modules/cerberus/**`, `modules/shadow/**`). (If a future
  grep shows hot-reload was added, the corruption becomes immediate and this
  abort is even more critical.)

## Verification runs (Part 3) — when, and what pass looks like

0. **Stage-0 bypass-road closure (before ANY self-mod, the gate on the whole
   front) — enumerate, don't spot-check:** first, **list every write-capable tool**
   from `Omen.get_tools()` (the closure principle) and assert each is closed;
   pass-2 proved a spot-check of "the four G-repairs" is under-inclusive because
   none of them inspected `sandbox_to_production`'s destination. The checks:
   - **G4** — `code_edit` refuses `modules/omen/omen.py` AND
     `modules/cerberus/cerberus.py` AND a `config/` path; a `data/` scratch write
     still succeeds (positive control).
   - **G5-as-closure** — `sandbox_to_production(production_path=
     "modules/cerberus/cerberus.py")` is **refused** (destination guard), and a
     raw call lacking a Stage-S checkpoint token is refused. *Negative control:*
     pre-fix, the same call overwrites/deletes the file (proves the road was
     open).
   - **G1 — against the REAL dispatch loop, not only a stub:** assert that
     `orchestrator._step5_execute` (`orchestrator.py:5197-5223`), when the
     pre-hook yields `APPROVAL_REQUIRED`, does **not** call `module.execute` and
     records a pending-approval — because pass-2 noted a unit test on a stub can
     pass while the live loop still executes. Positive control (ALLOW → executes)
     and negative control (pre-fix loop executes) both run **through the real
     loop**.
   - **G2/G3** — pre-hook denies/holds a `code_edit` **and** a
     `sandbox_to_production` toward `modules/cerberus/` with the correct param
     key; negative control with the old `path` key fails to fire.
   - **G6** — a write toward `modules/cerberus/` reaches `check_shutdown_triggers`
     and fires the emergency signal; *two negative controls:* pre-fix, (i)
     `grep` shows `check_shutdown_triggers` has **zero callers**, and (ii)
     `code_edit`/`git_commit` are in `SAFE_TOOL_NAMES` so `_is_safe_operation`
     short-circuits — assert both are removed/fixed.
   - **Class-2 ACTIVE probe (pass-3 CRITICAL — the one that greened while open):**
     submit to `sandbox_execute` (and `code_execute`) a program that attempts
     `open("../../modules/omen/omen.py","w")` — a **relative traversal**, so the
     static validator does not flag it — and assert the write is **blocked** (the
     file's hash is unchanged after the run). *Negative control:* on the current
     unisolated sandbox the write **succeeds** (proving the road is open). This
     check can pass ONLY under real OS isolation (or with the tools gated); a
     handler-guard check cannot make it green. If it cannot be made green, Part 3
     is **BLOCKED (Abort B9)**, not merely failed.
   **Pass = every Class-1 tool closed AND the Class-2 active probe blocked AND all
   G-checks green. If any Class-1 road is open → Abort B0; if the Class-2 probe
   cannot be blocked → Abort B9.** This is the single most important verification
   — three passes found three write roads (`code_edit`, `sandbox_to_production`,
   `sandbox_execute`); a hand-written named-tool checklist is exactly what let the
   third one through, so **enumerate from `get_tools()` and probe execution, do
   not trust this plan's list.**
1. **Gate-1 restorability (before SW, every run) — a REAL round-trip, not "HEAD
   exists":** pass-2 found that on a clean tree `create_checkpoint` skips the
   commit and returns `HEAD` (`test_gate.py:133-150`), so `git cat-file -e HEAD`
   and a "dry restore reproduces the blob" both pass **trivially without
   exercising recovery**. Instead: write a known change to `target_file`, take
   the checkpoint, mutate the file again, run the restore, and assert the file's
   bytes equal the **known pre-change** content (a full change→checkpoint→
   mutate→restore→compare cycle). Pass = the original bytes come back from an
   actual restore; a no-op "HEAD exists" is NOT a pass.
2. **Data-loss assertion (the critical one, in a scratch harness before any
   real self-mod):** induce a post-copy test failure on an existing target;
   assert the target's bytes are unchanged (hash equal) and the file still
   exists. Pass = original intact, never missing. **If this fails, Part 3 is not
   safe to run at all — stop the whole front.**
3. **Composition/false-success test:** induce inner-layer test failure; assert
   `_sandbox_to_production` reports `success=False` (not a phantom success).
   Pass = no false-positive promotion.
4. **Gate-3 hold test (after G1):** dispatch a self-mod promotion; assert the
   target file is unchanged and a `pending_approval` record with the diff
   exists; on simulated approval the change applies, on rejection it reverts.
   Pass = execute-only-after-approval, revert-on-reject.
5. **Gate-5 separate-run test (self-mod of `omen.py`):** validation subprocess
   imports the candidate (verified `__file__`), `pytest tests/test_omen.py -q`
   green in that subprocess. Pass = green from a non-editing process.
6. **Rollback + failure-log:** after an induced failure, original bytes
   restored, `git status` clean, `failure_search` returns the new row. Pass =
   all three.
7. **No-push proof (B-11 fix — don't rely on a tautology):** the primary proof
   is **structural, not state-based** — `grep -rn "push" ` over the promotion/
   TestGate modules returns no `git push` invocation, AND the harness deny-list
   (`.claude/settings.local.json`) blocks `git push*`. The `git log @{u}..HEAD`
   "ahead of upstream" check is only a secondary corroboration (it proves nothing
   pre-commit and can't distinguish never-pushed from pushed-then-reset). Pass =
   grep clean AND deny-list present; the log check is informational.

---

## Red-team record (Part 3)

A fresh attacker followed this plan blind and verified every load-bearing
`file:line` claim against the live tree (all held; two were worse than stated).
Full report: `wargames/red-team/omen-part3-selfmod.md`.

**The attack that landed (worst break, CRITICAL):** the plan gated the
`sandbox_to_production` pipeline but left `code_edit` — classified `autonomous`
(`cerberus_limits.yaml:223`), `PROTECTED_PATHS` omitting `modules/` — as an
open road to write `modules/omen/omen.py` or `modules/cerberus/cerberus.py` with
no snapshot, no test, no approval. The executor never has to *enter* the gated
pipeline; it can call `code_edit` instead. Compounded by `git_commit` being
autonomous with `git add -A` (B-4), the emergency self-mod trigger being dormant
(B-3, nothing feeds it `target_path`), and the pre-hook guard reading the wrong
param key (B-2). All three of the mission's red lines fall on one ungated call.

**The patch born from it:** added **Stage 0 — Close the bypass roads** as a hard
precondition (`code_edit` PROTECTED_PATHS extended to `modules/` via G4;
`git_commit` gated via G1; pre-hook param-key fixed via G2/G3; Trigger 2 wired
via G6), with **Abort B0** halting the entire front until all four are verified,
Stage P re-asserting them before producing a proposal, and **Verification #0**
gating the whole of Part 3 on their green. Also patched from the same pass:
the dirty-tree guard is now wired in code before `create_checkpoint` (B-8) with a
non-circular verify; Stage SW got a real pass/fail predicate instead of "returns
an exit code" (B-9); Stage T got a coverage gate so "green on the new path"
can't pass on an untested change (B-5); the Stage-P driver fork became a
mechanical path+AST-diff rule instead of a judgment call (B-10); the no-push
proof became structural (grep) rather than a pre-commit tautology (B-11); the
hot-reload RECON was settled (no hot-reload) and Gate 5 made explicitly mandatory
(B8 abort). The phantom-success (B-6) and delete-on-rollback (B-7) breaks were
already diagnosed in the draft; they are now bound to Verification #2/#3 as
must-pass-before-any-real-self-mod assertions.

**What held:** the harness-level `git push*` deny (Omen's tools can't reach a
push) and `TestGate`'s revert logic *when actually used on a green baseline*. The
attacker's point — that a sound gate is worthless if the perimeter around it has
a hole — is exactly what Stage 0 closes.

### Pass 2 (confirmation) — the patches did NOT fully hold; a second bypass road

A fresh attacker re-ran the patched plan blind. Verdict: **G4 genuinely closes
the `code_edit` road** (`.resolve().relative_to()` resists `../`, absolute,
symlink, case-fold), Gate 5's separate-run design is sound, and no-push holds —
**but Stage 0 was still whack-a-mole, not a principle.** Landed breaks:
- **CRITICAL (P2-1): a second bypass road.** `sandbox_to_production` →
  `copy_to_production` (`sandbox.py:1096-1147`) checks only that the *source* is
  in the sandbox; the **destination `production_path` has no guard**, so a raw
  autonomous call with `production_path="modules/cerberus/cerberus.py"`
  overwrites/deletes production Cerberus, never entering Stages S–M. Stage 0
  had closed `code_edit`, not this.
- **HIGH (P2-3):** `APPROVAL_REQUIRED` is genuinely unenforced in the live loop
  (`orchestrator.py:5197-5223`), so Stage-M's hold and the `git_commit` gate both
  depend on G1 — and a G1 *unit test on a stub* can pass while the live loop
  still executes.
- **HIGH (P2-3b):** G6's trigger is dead three ways — `check_shutdown_triggers`
  (I'd mis-named it `should_shutdown`) has **zero callers**, and
  `_is_safe_operation` short-circuits because `code_edit`/`git_commit` are in
  `SAFE_TOOL_NAMES` (`emergency_shutdown.py:47-54`).
- **HIGH (P2-2):** Verification #0 was under-inclusive — it checked its four
  G-repairs, none of which inspected `copy_to_production`'s destination, so it
  greened with P2-1 open.
- **MEDIUM (P2-4):** the driver AST rule missed in-place inversions
  (`if allowed:`→`if not allowed:`). **MEDIUM (P2-5):** Stage-S "restore-verified"
  was a tautology on a clean tree (`create_checkpoint` skips the commit and
  returns `HEAD`).

**The patch born from pass 2:** Stage 0 rewritten around a closure principle
(enumerate every write-capable tool), `sandbox_to_production` destination guard,
real-loop G1, three-part G6 fix, enumerated Verification #0, AST driver rule, and
a full round-trip Gate-1 restore.

### Pass 3 (confirmation) — a THIRD CRITICAL; the closure principle has no floor

The pass-2 patch was still not enough, and pass-3 found why in the deepest place:
- **CRITICAL (P3-1): `sandbox_execute`/`code_execute` are a third road, and it is
  a different *kind* of road.** They run model-authored code in a subprocess with
  full host FS write access (`sandbox.py:642-649`; no chroot/namespace/seccomp,
  same user). That child code writes `modules/omen/omen.py` via a **relative
  traversal** (`open("../../modules/omen/omen.py","w")`) which the static
  validator never flags (it flags only literal absolute paths, `sandbox.py:859-
  881`; returns `safe=True` on `SyntaxError`, `:817`). The closure principle
  enumerated tools whose *handler* writes a path and structurally missed a tool
  whose write is *transitive* through executed code. **No destination guard can
  close this — only OS isolation can.**
- **HIGH:** Verification #0 was still a hand-written named-tool checklist that
  never probed `sandbox_execute` (the meta-failure, recurring one tool over);
  **HIGH:** G1's `APPROVAL_REQUIRED` is unbuilt on *both* halves (the pre-hook
  never produces the verdict; the loop never enforces it); **MEDIUM:** the
  `path`-key bug has two more live sites (`_maybe_snapshot`, `_check_hard_limits`).
  Pass-3 also **corrected a pass-2 patch**: the async worker is NOT a bypass
  (`run_deferred_through_graph` re-gates it), so G1's async-worker branch is dead,
  not a hole.

**The patch born from pass 3 (structural, and it changes the mission's terminus):**
added the **fifth premise** (executed code is a transitive write road that
tool-guards cannot close), split the closure principle into **Class 1
(handler-writers → destination guard / pipeline-only)** and **Class 2
(code-executors → OS isolation or `never_autonomous`+gate)**, made Verification #0
**actively probe** the Class-2 traversal write, added **Abort B9**, and marked the
honest terminus: **Part 3 is BLOCKED** until code-execution runs under real OS
isolation (unprivileged user + read-only bind-mount of the source tree, or
namespace/seccomp/`bwrap`) — which is a **Master/Opus architecture decision, not a
Claude Code build** (CLAUDE.md). Also fixed: G1 both halves specified; three
`path`-key sites in G2; the `git_commit` get_tools-vs-yaml permission contradiction.

**Honest status: PATCHED → BLOCKED.** The plan is complete and correct; three
independent passes found three write roads, and the third proved that on the
current sandbox the self-mod pipeline *cannot* be made the only road to a
`modules/**` write. That is not a plan defect — it is the wargame doing its job:
surfacing that the crown capability requires an isolation substrate that does not
exist yet. DONE is not claimed and should not be until the Class-2 active probe is
BLOCKED under real isolation.

### Why I stopped at three passes (and did not loop to a fourth)
Each pass found a *structurally distinct* class of write road: pass-1 a
handler-destination gap (`code_edit`), pass-2 a second handler-destination gap
(`sandbox_to_production`), pass-3 a *transitive-execution* road (`sandbox_execute`)
that is a different kind and forces the OS-isolation conclusion. A fourth pass
against a plan whose honest verdict is already **BLOCKED on an architecture
decision** would attack a route the plan explicitly says must not run — it cannot
"pass." The correct next step is Master's isolation decision, after which the
Class-2 probe becomes runnable and a fresh red-team can attempt the
now-isolated pipeline. Chasing DONE with more passes here would be inflation, not
rigor.
