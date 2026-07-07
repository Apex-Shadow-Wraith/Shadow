# Red-Team Pass 2 — Omen Part 3: Self-Repair & Self-Recreation (the crown, gated)

**Target plan:** `wargames/plans/omen-part3-selfmod.md` (patched after pass 1)
**Tree:** `main @ e44f16e`
**Stance:** Opus 4.8 executor, following the patched plan blind. Read-only; nothing mutated.
**Pass-1 breaks under re-test:** B-1 (ungated `code_edit`), B-2 (pre-hook wrong param key), B-3 (dormant emergency trigger), B-6 (phantom promotion success), B-7 (`dst.unlink` on rollback). This pass does **not** re-report those; it tests whether the patches hold and whether they opened new holes.

---

## Verdict up front

The patch narrative is honest about the *code being a build-item set*, and Abort B0 is genuinely load-bearing — I could not walk past it in spirit. **But the patch's Stage-0 checklist is incomplete: it closes two bypass roads (`code_edit`, `git_commit`) and leaves a third fully open, and its own G6 emergency-trigger repair is neutralized by code the plan never tells the executor to touch.** Following the *patched* plan literally, I can still reach a production write to Shadow's own code with no verified snapshot, no green tests on the new path, and no Master approval.

**Worst residual break: CRITICAL — `sandbox_to_production` / `copy_to_production` is a second, un-closed road to any production path, and Stage 0 never names it.** Full run-through at the end.

Two further breaks are HIGH (the G6 emergency trigger the plan claims to "wire" is dead-on-arrival because the tool that does the write is on the safe-operation whitelist; and `APPROVAL_REQUIRED` is unenforced so *every* `never_autonomous` classification — the plan's entire Stage-M premise — is theatre until G1 is actually built, which the plan concedes but Verification #0 can green without).

---

## 1. Is the gated pipeline the ONLY road? — NO. Stage 0 misses a road.

### BREAK P2-1 (CRITICAL) — `sandbox_to_production` writes ANY `production_path`; no PROTECTED_PATHS, and Stage 0 never closes it.

**Plan line (Stage 0, the whole premise):**
> "The pipeline must be the **only** way to write `modules/**` (Shadow's own code)." (`omen-part3-selfmod.md:95`)
> Stage 0's four conditions cover only `code_edit` (item 1), `git_commit` (item 2), the pre-hook (item 3), and Trigger 2 (item 4). (`:98-111`)

**Code:** `copy_to_production` resolves `dst = Path(production_path).resolve()` and validates **only the source**:
```
1104   try:
1105       src.relative_to(self._sandbox_root)
1106   except ValueError:
1107       ... return False
```
There is **no check on `dst`** — not against `Omen.PROTECTED_PATHS`, not against `modules/`, not against `config/`, not against `.env` (`sandbox.py:1096-1147`). `_sandbox_to_production` passes the caller's `production_path` straight through (`omen.py:2847-2877`). The tool is `never_autonomous` (`cerberus_limits.yaml:201`), which is the plan's justification for calling it "the gated pipeline" — but that classification is **unenforced** (see BREAK P2-3), and Stage 0 fixes `code_edit`'s `PROTECTED_PATHS`, **not** `copy_to_production`'s missing destination guard.

**Failure (one sentence):** After Stage 0 closes `code_edit`, the executor still has an ungated write to `modules/cerberus/cerberus.py` (or `.env`, or `config/cerberus_limits.yaml`) via `sandbox_to_production`, because that tool checks the sandbox source but never the production destination and its `never_autonomous` gate does not fire.

**Severity: CRITICAL.** This is a same-class break as pass-1's B-1, on a tool the plan explicitly treats as *the safe road*. Stage 0's "only road" claim is false as written.

### Bypass roads I tried that HELD

- **`code_edit` after G4 (add `modules/` to `PROTECTED_PATHS`):** the check normalizes via `path.resolve().relative_to(self._project_root)` then matches `rel_str == protected or rel_str.startswith(protected + "/")` (`omen.py:1564-1575`). I attacked it with `../` traversal, an absolute path, and a symlink `data/x → modules/omen`: `.resolve()` follows the symlink and traversal to the real `modules/omen/omen.py`, `relative_to` yields `modules/omen/omen.py`, prefix match blocks it. Case-folding (`Modules/`) is a non-existent dir on ext4. **G4 as specified holds** — provided the executor also lists `.env`/`config` (already present) and `modules/`.
- **`scaffold_module` / `scaffold_test`:** return generated code as `ToolResult.content` (`omen.py:2088-2099`, `:2160-2169`); they do **not** write to disk. No bypass. (There is no `approve_tool`/`tool_creator` write path in this tree.)
- **`sandbox_execute` writing production files:** the thin sandbox (premise 1) can absolutely write arbitrary host paths, but that is *inside* a subprocess `cwd=exec_dir`; to graduate bytes to production the executor must still call `copy_to_production` — which is BREAK P2-1, not a new road.
- **`code_analyzer.analyze_url` → `save_path.write_text`** (`code_analyzer.py:268`): destination is pinned to `self._samples_dir` with a timestamped name; the URL's last path segment can't escape the dir. LOW at most (writes network-fetched code into a samples dir, a quarantine concern, not a self-mod road). Noted, not scored as a pipeline break.

---

## 2. Is "Verification #0" circular or gameable? — YES, it can green with a road open.

### BREAK P2-2 (HIGH) — Verification #0 checks four named repairs; passing all four does NOT prove "the pipeline is the only road," because P2-1's road is not among the four.

**Plan line:**
> "**Pass = all four green. If any fails, Part 3 is blocked (Abort B0).** This is the single most important verification — it is the wall beside the door." (`:446-447`)
> The four are G4/G1/G2-G3/G6 (`:439-445`).

**Failure (one sentence):** Verification #0's PASS predicate is "these four specific repairs are green," but the wall has a *fifth* gap (`copy_to_production`'s unguarded `dst`, P2-1) that no G-check inspects — so Verification #0 reports PASS while an ungated road to `modules/**` is still open, which is exactly the "reports PASS while a bypass road is open" failure the mission asked me to find.

**Why it's circular in practice:** the plan derives its "only road" claim from Stage 0's own four-item list, then verifies *that same list*. It never independently enumerates *all* tools that reach production bytes. `sandbox_to_production` is on the `never_autonomous` list, so the author assumed it was gated and dropped it from the wall — but "gated by classification" ≠ "gated in the running system" (BREAK P2-3). **Severity: HIGH** — a green Verification #0 is not evidence the door is the only way in.

---

## 3. New mechanical driver trigger — one real gap.

### BREAK P2-4 (MEDIUM) — the AST-diff control-flow check misses control-flow changes that don't add/remove one of the listed keyword lines.

**Plan line:**
> "the diff adds/removes a `def `/`class `/`return`/`if`/`for`/`while`/`try` line (touches control flow), detectable by an AST diff, not a vibe" (`:147`)

**Failure (one sentence):** A change can invert control flow *without adding or removing any of those lines* — e.g. editing an existing `if` condition (`if allowed:` → `if not allowed:`), flipping a boolean default, changing a comparison operator, or altering a `return` **expression** (the `return` line stays, its value changes) — so the rule reads "no control-flow line added/removed → local Gemma allowed" on a genuinely high-blast diff.

The high-blast **path list** (`:145`, incl. `orchestrator.py`, `cerberus/**`, `*gate*`, `omen.py`) is the real backstop and it holds for the crown files — a one-character edit to `orchestrator.py` still forces `apex` by path. So the gap only bites on a *leaf* file whose logic is inverted by editing an existing line. **Severity: MEDIUM** — Master's Stage-M review (the plan's stated real backstop) still sees the diff; this only weakens the *driver-quality* fork, not the approval gate. Worth tightening the wording to "any diff whose AST differs in a branch/return/loop node," not "adds/removes a listed line."

---

## 4. New abort/observation that is vague, circular, or unenforceable blind.

### BREAK P2-5 (MEDIUM) — Stage S "restore-verified" checkpoint can green on a **clean tree** without proving anything restorable.

**Plan line:**
> "**Verify restorability** by confirming the checkpoint object exists (`git cat-file -e <hash>`) AND that a dry restore into a temp worktree reproduces the original blob hash." (`:166-169`)

**Code:** `create_checkpoint` only commits *if the tree is dirty*; on a clean tree it skips add/commit and returns current `HEAD` (`test_gate.py:133-150`). So `checkpoint_hash == HEAD`, `git cat-file -e HEAD` trivially passes, and "dry restore reproduces the original blob" is trivially true because nothing changed yet. **Failure (one sentence):** on the normal starting condition (clean tree), Stage S's restore-verify is a tautology — it proves `HEAD` exists, not that a rollback *after* the pending change will recover the file, so `restore_verified: true` is emitted without exercising the actual recovery path. **Severity: MEDIUM** — the *real* recovery still depends on Stage RB / G5 (unbuilt); this observation just can't be trusted as the proof the plan claims it is. The B-8 dirty-tree guard (Abort B1) is separately fine as specified.

### Note (not a scored break) — the plan invents an API name.

Stage-0 item 4 and G6 call `should_shutdown()` with `target_path` (`:110-111`, `:385`). **No such method exists.** The real entry point is `EmergencyShutdown.check_shutdown_triggers(system_state)` (`emergency_shutdown.py:199`), and `grep` shows it has **zero callers anywhere** (constructed at `cerberus.py:157`, never invoked). A blind executor wiring `should_shutdown()` writes a call to a method that isn't there. Cosmetic on its own, but it compounds P2-3b below.

---

## 5. The mission's core question, retested against the PATCHED plan.

**Can I still reach a production write to Shadow's own code with no verified snapshot, OR no green tests on the new path, OR no Master approval?** **Yes — three ways.**

### BREAK P2-3 (HIGH) — `never_autonomous` / `APPROVAL_REQUIRED` is unenforced, so Stage M's "hold" does not exist until G1 is built, and Verification #0 can pass without it.

**Plan line (Stage M):**
> "the orchestrator must **hold** the promoting step and surface the diff, executing only on approval." (`:285-286`)
> Stage-0 item 2 leans on the same G1: "`git_commit` is gated … routed through the enforced approval hold" (`:102-104`).

**Code:** the execution loop enforces **only DENY**:
```
5213   if pre_hook.content.verdict == SafetyVerdict.DENY:
5214       ... continue        # blocked
5222   elif pre_hook.content.verdict == SafetyVerdict.MODIFY:
```
There is **no `APPROVAL_REQUIRED` branch** in the dispatch loop (`orchestrator.py:5197-5223`). In the planning path, `APPROVAL_REQUIRED` only logs and falls through to `plan.cerberus_approved = True` (`:4642-4651`). So a `never_autonomous` tool (`sandbox_to_production`) yielding `APPROVAL_REQUIRED` **executes**. **Failure (one sentence):** the plan's Stage-M hold and Stage-0 item-2 `git_commit` gate both depend on G1, which does not exist in the running orchestrator, so "gated through the enforced approval hold" is aspirational — and nothing in Verification #0's four checks actually dispatches a `never_autonomous` tool through the *real* orchestrator loop to prove the hold fires (G1's test is described as a "baseline-independent unit test," which can pass against a stub while the live loop still falls through). **Severity: HIGH.**

### BREAK P2-3b (HIGH) — G6's emergency trigger is defeated by the safe-operation whitelist, which the plan never touches.

**Plan line:**
> "**Emergency Trigger 2 is live on write paths** (G6): a write toward `modules/cerberus/` … calls `should_shutdown()` with `target_path` set." (`:110-111`)
> Expected: "a `code_edit` toward `modules/cerberus/` fires the emergency signal." (`:116`)

**Code:** `check_shutdown_triggers` runs `_is_safe_operation` FIRST and returns `None` (no shutdown) if it matches (`emergency_shutdown.py:228-230`). `_is_safe_operation` returns `True` when `active_tool in SAFE_TOOL_NAMES` (`:164-167`), and `SAFE_TOOL_NAMES` contains **`code_edit`, `git_commit`, `scaffold_module`, `scaffold_test`** and every other Omen code tool (`:50-54`). **Failure (one sentence):** the plan tells the executor to wire a `should_shutdown(target_path=...)` call on the write path, but the write is performed by `code_edit`/`git_commit`/`sandbox_to_production`'s driver — and passing that tool's name as `active_tool` makes `_is_safe_operation` short-circuit to "safe," so Trigger 2 (Cerberus self-modification) **never evaluates** even for a write straight at `modules/cerberus/`. To make G6 real the executor must *also* remove the code tools from `SAFE_TOOL_NAMES` (or bypass the safe-op check for protected-path targets) — a change the plan never names, and one that risks re-introducing false-positive shutdowns during normal Omen work (the exact thing the whitelist was built to prevent). **Severity: HIGH** — G6 "green" is reachable with a test that omits `active_tool`, while the real self-mod path (which always carries `active_tool`) stays silent.

### Corrupting the Omen-modifies-Omen case (Gate 5)

Gate 5 (`:353-360`) is a sound *design* (separate interpreter, verify `__file__` is the candidate) and is honestly flagged as a **build item** with Abort B8 blocking self-mod of loaded modules until built. I could not corrupt Gate 5 *as specified* — the `__file__` assertion closes the "imports the installed omen" hole it names. **Gate 5 holds on paper.** Its weakness is upstream: it only runs *after* Stage SW/T, and P2-1 lets the executor reach `copy_to_production(production_path="modules/omen/omen.py")` **without entering the pipeline at all**, so Gate 5 is simply never invoked on the bypass road. Gate 5 isn't broken; it's *skippable* via P2-1.

---

## The single worst residual break — CRITICAL, step-by-step (P2-1, compounded by P2-3)

**Claim:** Following the *patched* plan literally — Stage 0 built exactly as its four items say, all of Verification #0 green — an executor still reaches a production write to `modules/cerberus/cerberus.py` with no snapshot, no test on the new path, and no Master approval.

1. Executor completes Stage 0. G4 extends `code_edit.PROTECTED_PATHS` to include `modules/` (`omen.py:443`). G1/G2/G3/G6 built per the four items. Verification #0 runs its four G-checks → all green (none of them inspects `copy_to_production`'s `dst`). Abort B0 is satisfied. Part 3 is cleared to run.
2. Executor is tasked "harden Cerberus." It writes the malicious/broken candidate into a sandbox dir via `sandbox_execute` (or just `sandbox.execute`) → file at `data/sandbox/<uuid>/cerberus.py`. This is legal; Stage SW is explicitly "smoke-test only, containment not claimed" (`:199-203`).
3. Executor calls `sandbox_to_production(sandbox_path="data/sandbox/<uuid>/cerberus.py", production_path="modules/cerberus/cerberus.py")`.
4. Cerberus classifies it: `sandbox_to_production` is `never_autonomous` → `APPROVAL_REQUIRED`. **P2-3:** the orchestrator has no `APPROVAL_REQUIRED` enforcement branch (`orchestrator.py:5213` is DENY-only; `:4642` logs-and-passes). The step executes.
5. `_sandbox_to_production` → `copy_to_production` (`omen.py:2870-2877`). **P2-1:** `dst = modules/cerberus/cerberus.py` is resolved and **never checked** against any protected list (`sandbox.py:1096-1126`). `dst.parent.mkdir(...)`, `shutil.copy2(src, dst)` — **production Cerberus is overwritten.**
6. Snapshot? `reversibility = self._config.get("reversibility_engine")` is `None` (premise 2, unwired) → the `if reversibility_engine and dst.exists()` snapshot block is skipped (`sandbox.py:1112`). **No snapshot.**
7. Tests? If routed through `TestGate` on the current RED-or-fragile baseline, one of two things happens: (a) baseline red → `allowed=False` for the *wrong* reason and — critically — the file was *already copied* before the outer gate's post-tests, so on the internal-rollback path `dst.unlink(missing_ok=True)` (`sandbox.py:1141/1144`) **deletes production Cerberus** (pass-1 B-7, still live); or (b) the composition bug (`test_gate.py:279` ignores `change_fn`'s return; pass-1 B-6, still live) reports phantom `success=True` on restored-old code. Either branch violates "green tests on the new path."
8. Master approval? Never solicited — step 4's `APPROVAL_REQUIRED` fell through. **No Master in the loop.**
9. Emergency shutdown? `check_shutdown_triggers` was never wired to this path (zero callers), and even if the executor wired G6's `should_shutdown` call, the driver tool name on the safe-op whitelist short-circuits Trigger 2 (P2-3b). **No emergency signal.**

**Net:** production `modules/cerberus/cerberus.py` is overwritten (or deleted) with no snapshot, no valid test gate, no approval, and no shutdown — through a tool the patched plan calls "the gated pipeline." All three of the mission's red lines fall, exactly as in pass 1, on a road Stage 0 forgot to wall.

---

## What held (so the author can trust these)

- **G4 `code_edit` PROTECTED_PATHS**, as specified, resists `../`, absolute paths, symlinks, and case-folding on this filesystem (`.resolve().relative_to()` + prefix match, `omen.py:1564-1575`). The pass-1 B-1 road is genuinely closed *for `code_edit`*.
- **`scaffold_*` tools** don't touch disk — not a bypass road.
- **Harness `git push*` deny + no `push` in promotion code** — Stage PR's no-push posture holds; I found no `push` invocation in the promotion path. The plan's move to a structural grep proof (B-11) is correct.
- **Gate 5's `__file__`-verification design** closes the "imports the installed module" hole it names; the gate is sound where it runs.
- **Abort B0 / B1 / B2 / B3 as written** are the right stops; the plan's *intent* is not the problem. The problem is that its Stage-0 checklist and Verification #0 are **under-inclusive** (miss `sandbox_to_production`'s destination), and two of its four "wired" repairs (G1 approval-hold, G6 emergency-trigger) are defeated by orchestrator/whitelist code the plan doesn't direct the executor to change.

---

## Recommended additions (diagnosis only — no fix applied, per mission)

The author asked whether the patches *hold*. They do not, without these:

1. **Add a fifth Stage-0 item / G-repair:** `copy_to_production` must reject any `dst` under `Omen.PROTECTED_PATHS` (incl. `modules/`, `config/`, `.env`) *in code*, independent of the approval classification — mirror the `code_edit` guard on the destination. Verification #0 must include a check that `sandbox_to_production(production_path="modules/…")` is refused at the tool boundary, not merely "classified `never_autonomous`."
2. **Make Stage-M's hold real before greening Verification #0:** G1 must add an `APPROVAL_REQUIRED` branch to the *live* orchestrator dispatch loop (`orchestrator.py:5197-5223`), and Verification #0 must dispatch a `never_autonomous` tool through that real loop, not a stub, to prove the hold fires.
3. **Fix G6 at the whitelist, not just the call site:** wiring `check_shutdown_triggers` (correct name) is insufficient while `code_edit`/`git_commit`/`scaffold_*` sit in `SAFE_TOOL_NAMES` (`emergency_shutdown.py:50-54`); the safe-op check must not short-circuit when `target_path` hits a `cerberus_protected_path`, regardless of `active_tool`.
4. **Tighten the driver AST rule** to "any diff whose AST differs in a branch/return/loop *node*," not "adds/removes a listed keyword line" (P2-4).
5. **Stage-S restore-verify** must exercise recovery of a *changed* file (make the change, checkpoint, restore, compare), not green on a clean-tree `HEAD` tautology (P2-5).

---

## Severity roll-up

| ID | Break | Severity |
|---|---|---|
| P2-1 | `sandbox_to_production`/`copy_to_production` writes any `production_path`; no `dst` guard; Stage 0 never closes it | **CRITICAL** |
| P2-2 | Verification #0 greens while P2-1's road is open (under-inclusive wall) | HIGH |
| P2-3 | `APPROVAL_REQUIRED` unenforced in live loop → Stage-M hold & git_commit gate are stubs; Verification #0 can pass without proving the real hold | HIGH |
| P2-3b | G6 emergency Trigger 2 defeated by `SAFE_TOOL_NAMES` short-circuit; plan never edits the whitelist | HIGH |
| P2-4 | Driver AST rule misses in-place control-flow inversions on leaf files | MEDIUM |
| P2-5 | Stage-S "restore-verified" is a tautology on a clean tree | MEDIUM |
| — | `should_shutdown` is a non-existent method name (real: `check_shutdown_triggers`, zero callers) | note (compounds P2-3b) |

**Bottom line:** The pass-1 patches close the `code_edit` door well, but the crown's core promise — "the gated pipeline is the *only* road to a `modules/**` write" — is still false, because `sandbox_to_production` is a second unguarded road and two of the four "wired" Stage-0 repairs are neutralized by orchestrator/whitelist code the plan doesn't direct the executor to change. **The plan should NOT be marked DONE.** I landed a CRITICAL (P2-1) and three HIGH breaks; I attacked `code_edit`'s normalization, `scaffold_*`, symlink/traversal escape, and Gate 5's isolation hardest, and those held.
