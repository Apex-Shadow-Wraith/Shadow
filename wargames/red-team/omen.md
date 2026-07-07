# Red-Team — Omen Wargame Plan (Fronts 1, 2, 4, 5)

**Target:** `wargames/plans/omen.md`
**Reviewer role:** Opus 4.8 executor, blind to everything except the plan. I owe the plan nothing.
**Method:** Read the plan, then verified every load-bearing `file:line` claim against the live tree (read-only). Ran `pytest --collect-only` (no mutation). Changed nothing.

**Verdict up front:** The plan is unusually well-recon'd and most of its claims hold under audit. But it has **one CRITICAL false-fact** (a recon claim stated as settled that is wrong and undermines Front 1), **two HIGH gate-design holes** (a circular G1 verification that passes on the current broken behavior, and a missing snapshot/self-edit gate for `sandbox_to_production` that Front 5 lists but under-wires), and several MEDIUM vagueness/fork gaps. No ungated write to Shadow's own code is *authored by* the plan — but the plan's own Front-1 verification can be tricked into declaring a stub "real," and its G1 test as written can go green while the dangerous behavior survives.

---

## A. Claim-by-claim verification (did recon tell the truth?)

I checked every `file:line` the executor is asked to trust before building. Result:

| Plan claim | Real code | Verdict |
|---|---|---|
| orchestrator does NOT enforce `APPROVAL_REQUIRED` at `5211-5223`; falls to `module.execute` at `5254` | `orchestrator.py:5213` handles only `DENY`, `5222` only `MODIFY`; `5254` is `await module.execute(...)` | **TRUE** |
| plan-build gate `4642-4651` only `logger.info`s APPROVAL_REQUIRED then sets `plan.cerberus_approved = True` unconditionally at `4651` | `orchestrator.py:4642-4649` is a bare `logger.info`; `4651` sets `cerberus_approved = True` outside the loop; only `DENY` returns early at `4640-4641` | **TRUE** |
| `_maybe_snapshot` reads `path` while `code_edit` uses `file_path` → snapshot no-ops | `cerberus.py:1294` `tool_params.get("path", "")`; `omen.py:1550` `params.get("file_path", "")` | **TRUE** |
| `code_edit`, `sandbox_to_production`, `git_commit` absent from every `pre_tool` deny `applies_to` | `cerberus_limits.yaml:147,151,158` — deny rules apply only to `bash_execute/code_execute`, `file_write`, `email_send/notification_send` | **TRUE** |
| `code_edit` `PROTECTED_PATHS = {config,.git,.env}`, `modules/` NOT covered | `omen.py:443` `PROTECTED_PATHS = {"config", ".git", ".env"}` | **TRUE** |
| `git_commit` = `approval_required` in `get_tools()` but `autonomous` in yaml (contradiction) | `omen.py:697` `approval_required`; `cerberus_limits.yaml:227` under `autonomous_tools` | **TRUE** |
| `code_review` is a structural stub, note string at `omen.py:1217` | `omen.py:1217` note string verbatim; no model call in body | **TRUE** |
| `copy_to_production` (`sandbox.py:1073-1147`) has no `PROTECTED_PATHS` guard on dst; `dst.unlink()` data-loss on rollback | `sandbox.py:1096-1147` — no protected-path check; `1141`/`1144` `dst.unlink(missing_ok=True)` | **TRUE** |
| emergency_shutdown Trigger 2 only fires if a caller passes `target_path` in `system_state` | `emergency_shutdown.py:245-254`; grep shows no caller feeds `target_path`/`active_module` on a code write | **TRUE (dormant)** |
| `tool_creator.py` orphaned — zero importers | `grep -rn` excluding the file itself returns empty | **TRUE** |
| 386 tests collected, 0 errors | `pytest --collect-only` → `386 tests collected in 0.61s` | **TRUE** |
| Front 2 anchors: `_code_analyze_self` 2565, `_dir` 2530, `_file` 2496, `_is_within_project` 2485, `_code_score` 2171, `_teaching_mode` 456 | all match exactly | **TRUE** |
| **`_code_generate` at `omen.py:2830`+ is template/scaffold-driven and makes NO model call (0.2)** | **`_code_generate` is at `omen.py:3176`; body makes a LIVE Ollama call at `:3242` `url = f"{ollama_url}/api/chat"` + `:3249` `urllib.request.urlopen`** | **FALSE** |

That last row is the one break in recon, and it is load-bearing. Everything else the plan asserts as settled is accurate — which makes the single wrong fact more dangerous, because the executor has been trained by 14 correct rows to trust the 15th.

---

## B. Breaks (each: quoted plan line, one-sentence failure, severity)

### BREAK 1 — CRITICAL — Assumption stated as fact that recon got wrong (`_code_generate`)
> Plan §0.2: *"`_code_generate` (`omen.py:2830`+) is template/scaffold-driven — it accepts an optional `model` param in its docstring but makes **no** model call in its body."*
> Plan §0.2 conclusion: *"Omen has zero semantic code intelligence today — all judgment is heuristic/AST/template."*

**How it fails:** The real `_code_generate` is at `omen.py:3176` and makes a live Ollama `/api/chat` call with a `write_code` tool definition (`omen.py:3242,3249,3321`) — so Omen already has a semantic generation path, the line anchor is wrong by ~340 lines, and the sweeping "zero semantic code intelligence" premise that Fronts 1–2 are built on is false for generation. **Severity CRITICAL** because Move 1.3 tells the executor to "wire `_code_generate` to retrieve and apply the relevant `SEED_PATTERN`" on the assumption it's a dumb template filler; an executor following blind will either bolt pattern-substitution onto a function that already calls a model (double-generation / conflicting output) or, worse, "add the missing model call" that already exists — and Abort A5 (*"If recon's `file:line` anchors don't match the tree... STOP"*) will actually trip here on the very first read of `_code_generate`, stalling the front for the wrong reason. Recon's own fail-safe fires against recon's own error.

### BREAK 2 — HIGH — G1's verification is circular; it goes green on today's broken behavior
> Plan §5.0, G1 Verify: *"A test dispatches a `sandbox_to_production` step; assert the tool did **not** execute and a pending-approval record exists. Green only if the OLD behavior (execute) is gone."*

**How it fails:** `sandbox_to_production` today routes through `TestGate.execute_with_gate`, and TestGate **already blocks every promotion because the baseline suite is RED** (`test_gate.py:260`: `if not pre_test.success: allowed=False`) — so "the tool did not execute" is already TRUE for the wrong reason, and a G1 test asserting only "did not execute" passes **without G1 being built at all**. The plan even documents this accident in §0.4.2 (*"it blocks today only because the baseline suite is RED... an accident, not a designed gate"*) but then writes a G1 verify that this same accident satisfies. **Severity HIGH:** G1 is the flagship "make the decorative gate real" repair, and its acceptance test cannot distinguish a real approval-hold from the pre-existing RED-baseline block. The "pending-approval record exists" clause is the only real discriminator, and it's stated as a conjunction with an already-true predicate — an executor who sees green on "did not execute" and a plausibly-present record (TestGate writes a `GateResult` history row that a careless assertion could mistake for an "approval record") signs G1 off while the `4642-4651` / `5211-5223` fall-through is still live. The verify must additionally assert the tool was blocked *by the approval path, on a GREEN baseline* — otherwise it's circular.

### BREAK 3 — HIGH — `sandbox_to_production` snapshot/self-edit gap is described but under-wired in Front 5
> Plan §5.0, G5 Verify: *"a failed promotion to an existing file leaves the ORIGINAL bytes intact (assert file hash unchanged), never a missing file."*
> Plan §0.4: *"`sandbox_to_production` is not in `_WRITE_TOOLS`, so the pre-hook never snapshots it."*

**How it fails:** G5 fixes the *rollback data-loss* and adds a *dst PROTECTED_PATHS guard*, but neither G5 nor any other row makes `sandbox_to_production` snapshot through Cerberus's `_maybe_snapshot`, and G3 only adds it to `hooks.pre_tool` deny/approval rules — not to `_WRITE_TOOLS` (`cerberus.py:1277`). So after all of G1–G6, a `sandbox_to_production` that slips past the approval hold (e.g. via a bug in the newly-built G1, or a `run_tests_fn=None` call path where `copy_to_production` skips its own snapshot at `sandbox.py:1112` `if reversibility_engine and dst.exists()`) still overwrites production **unsnapshotted by Cerberus**, relying entirely on the sandbox's own best-effort engine that only snapshots when `dst.exists()` AND an engine is passed. **Severity HIGH:** the promotion path is the single most dangerous write in the whole target (no `PROTECTED_PATHS` at all today — it can overwrite `.env`/`config/`/`.git`, per §0.3), and Front 5 leaves its Cerberus-snapshot coverage unaddressed while claiming to "make the gates real."

### BREAK 4 — HIGH — Front 1's known-bad-code verification can PASS on a broken (stub) result
> Plan §1.4 Expected observation (pass): *"each of the 3 files yields ≥1 finding at the right line with severity ≥ high... Record the findings array verbatim."*
> Plan §1.2 fallback: *"fall back to the current structural analysis but stamp `driver="structural-fallback"` and `success=True`."*

**How it fails:** The pass condition in §1.4 checks finding-line and severity but the *only* guard against a stub masquerading as a review is the separate sentence in §1.4-fail (*"any planted defect returns zero findings with `driver != structural-fallback`"*). The three planted defects (bare `except: pass`, off-by-one, f-string SQL) are exactly the patterns the **existing structural stub already keys on** — `has_error_handling = "try:" in code` (`omen.py:1213`) trivially "notices" the bare except. An executor who lets `structural-fallback` emit a finding for the bare-except file (line right, and nothing stops it stamping `severity: high`) gets a green 1.4 on **`driver="structural-fallback"`**, because the pass rule doesn't require `driver != structural-fallback` — only the *fail* rule mentions the driver, and only for the *zero-findings* case. **Severity HIGH:** §1.4 calls itself *"the only proof Front 1 works"* and *"Built is not done"* — yet a structural-fallback that happens to fire on a keyword-detectable defect satisfies the written pass gate. The pass condition must state `driver ∈ {gemma-local, apex}` as a hard requirement, not leave it implied.

### BREAK 5 — MEDIUM — Fork with no resolvable trigger (Move 1.1 comment-vs-call)
> Plan §1.1 Trigger B: *"grep shows an existing Ollama/Apex call in `_code_review`/`_code_generate`/`CodeAnalyzer`."*
> Plan §1.1 counter: *"confirm the match is inside a function body that executes, not a docstring/constant, by reading the surrounding 10 lines before deciding the fork."*

**How it fails:** Given BREAK 1, the 1.1 grep **will** match a live Ollama call in `_code_generate` (`omen.py:3242`), forcing Trigger B ("wire-through, not green-field") — but the plan's own §0.2 told the executor to expect Trigger A ("no LLM client in the code-judgment path"). The blind executor now faces a direct contradiction between the recon narrative (§0.2: no model call) and the grep result (§1.1: a model call in `_code_generate`), and the "read 10 surrounding lines" counter resolves the docstring-vs-call question but **not** the "is this call in the *code-judgment* path or the *generation* path" question that actually decides the fork. `_code_generate` is generation, not review; `_code_review` (the judgment target) genuinely has no call. The fork gives no rule for "a model call exists in generation but not in review" — the executor must make a judgment call the plan doesn't authorize. **Severity MEDIUM:** recoverable by a careful reader, but the plan manufactured the ambiguity via its own §0.2 error.

### BREAK 6 — MEDIUM — G3's `protected_path_write` extension mis-targets the enforcement point
> Plan §5.0, G3: *"Add `code_edit`... to `cerberus_limits.yaml` `hooks.pre_tool` deny/approval rules with correct `applies_to`, and extend `protected_path_write` paths to cover `modules/cerberus/`, `.env`, `modules/omen/`."*
> G3 Verify: *"Pre-hook returns DENY... for a `code_edit` targeting `modules/cerberus/x.py`; assert not executed."*

**How it fails:** The `protected_path_write` deny rule reads `tool_params.get("path", "")` (`cerberus.py:1232`), but `code_edit` passes `file_path` (`omen.py:1550`) — the **same `path`-vs-`file_path` mismatch that G2 fixes for snapshots exists again in the deny-rule reader**, and G3 only says "add `code_edit` to `applies_to`" without fixing the param key the rule reads. Add `code_edit` to `applies_to: [file_write, code_edit]` and the rule still reads `tool_params["path"]`, finds nothing, and returns ALLOW — G3's verify ("returns DENY") **fails silently to ALLOW** unless the executor also independently notices the param-key bug in the *hook* reader (not just the *snapshot* reader G2 targets). The plan patches the mismatch in one place (G2) and re-walks into it in another (G3) without flagging it. **Severity MEDIUM:** the executor may catch it, but the plan doesn't point at it, and a literal G3 build ships a dead deny rule.

### BREAK 7 — MEDIUM — Vague "expected observation" the executor can't check blind (Move 2.3)
> Plan §2.3 Expected observation (pass): *"a finding referencing `_maybe_snapshot` / the parameter mismatch appears with severity ≥ high and a proposed fix that aligns the parameter name."*

**How it fails:** "a finding *referencing* `_maybe_snapshot`" is not a checkable string/field — an LLM audit can emit a finding on `_maybe_snapshot` that flags the wrong thing (e.g. "no docstring" or "broad `except Exception`" at `cerberus.py:1339`) and still literally "reference `_maybe_snapshot` with severity high," passing the written gate **without ever surfacing the `path`/`file_path` bug**. The observation needs an exact predicate — e.g. "the finding's `message` names both `path` and `file_path`" or "the `proposed_fix` changes `.get(\"path\")` to accept `file_path`" — otherwise a plausible-but-wrong finding on the right function passes. **Severity MEDIUM:** compounded by the §2.3 fork (below).

### BREAK 8 — MEDIUM — Fork trigger relies on a fact the plan itself contradicts (Move 2.3 escalation fork)
> Plan §2.3 Fork: *"if Front 2 misses *all three* of the recon's known bugs (0.3 no-guard on `copy_to_production`, 0.4 param mismatch, 0.4 unenforced APPROVAL_REQUIRED), Trigger → ... escalate the audit to Apex."*

**How it fails:** Two of the three "known bugs" the fork tests against are *cross-file behavioral* facts (unenforced APPROVAL_REQUIRED lives in `orchestrator.py:5211-5223`; the `copy_to_production` no-guard in `sandbox.py`), which a **file-scoped self-audit of `modules/omen/` or `modules/cerberus/cerberus.py` cannot possibly surface** because the evidence isn't in the file under audit — a single-file AST/heuristic reviewer has no view of the orchestrator's enforcement gap. So "misses all three" is nearly guaranteed for structural reasons, not model-weakness reasons, and the fork will fire "escalate to Apex" every time even when the model is fine — or, if the executor scopes the audit narrowly, the fork's premise (that a strong model *would* catch all three) is simply false. **Severity MEDIUM:** the escalation trigger doesn't measure what it claims to measure.

### BREAK 9 — MEDIUM — TestGate auto-commit: a live ungated write the plan gates last, not first
> Plan §0.7: *"`TestGate.create_checkpoint` runs `git add -A` + `git commit` autonomously as a side effect of `execute_with_gate`... it *does* sweep every dirty working-tree file into a commit."*
> Plan §5.1 (last row): *"Scope the checkpoint to the files under change; or stash-based checkpoint..."*

**How it fails:** This is a real autonomous git write to Shadow's own history (`test_gate.py:137-143` `git add -A` + `git commit`) that fires **the moment any Front-1 verification routes through `sandbox_to_production`** (which calls `execute_with_gate` at `omen.py:2881`). The plan correctly identifies it but places the gate in the Ledger's *last* row and never marks it as an **abort/precondition** for Front 1's own 1.4 run — so an executor running 1.4 against a dirty tree (which it will be, mid-build) triggers a full-tree `git add -A` auto-commit of half-built code **before** the §5.1 gate is built. The dangerous write happens during verification of the very front whose job is to make writes safe. **Severity MEDIUM:** no data loss (commit, not push), but it's an autonomous, un-preconditioned commit of arbitrary dirty state, and the plan's ordering lets it fire before its own gate exists. Abort A1 (RED baseline) partially masks this by blocking the promotion — but `create_checkpoint` runs at `test_gate.py:253` **before** the baseline check at `:259`, so the auto-commit fires even on a RED baseline.

### BREAK 10 — LOW — G6 verify can't fail on the current dormant behavior without new wiring
> Plan §5.0, G6 Verify: *"A `code_edit`/copy targeting `modules/cerberus/` raises the emergency-shutdown signal; assert the shutdown path fires."*

**How it fails:** Trigger 2 is dormant (no caller feeds `target_path`/`active_module` — confirmed, `emergency_shutdown.py:245` reads `system_state.get("target_path", "")` and nothing populates it on a write). The verify is fine *if* G6 wires the feed — but the plan marks G6's "Where" as "see 0.7 RECON," i.e. it defers the actual wiring location to an unresolved RECON NEEDED. An executor can build a test that stubs `system_state={"target_path": "modules/cerberus/x.py"}` and calls the evaluator directly, which passes G6's verify **without wiring the live `code_edit` path** — a green G6 with the real trigger still dormant. **Severity LOW:** narrower than G1 because the plan flags the RECON, but the verify as written doesn't force the *live-path* wiring it's meant to prove.

### BREAK 11 — LOW — Move 1.5 teaching-mode assertion is checkable but has no failure path defined for the model-refuses case
> Plan §1.5: *"with `teaching_mode=True`, the 1.4 findings carry a non-empty `explanation`; with `False`, they do not."*

**How it fails:** `_teaching_mode` (`omen.py:456`) gates existing behavior, but the plan wires `explanation` into the *new* LLM review output — if the local model returns findings but omits the `explanation` field (common with strict-JSON contracts that don't require it), the `teaching_mode=True` branch yields empty `explanation` and the assertion fails for a benign reason (model formatting), not a real regression. No retry/repair path is specified for the missing-explanation case, unlike the findings-parse case in 1.2. **Severity LOW.**

---

## C. Does Front 5 make the decorative gates real, or just list them?

**Partial.** Front 5 §5.0 is genuinely stronger than a list — G2, G4, G5(rollback), and G3(param-extension) name concrete code edits with hash-based or refusal-string verifies that *would* fail on a broken result. But:

- **G1 is circular** (BREAK 2) — its verify passes on today's RED-baseline accident.
- **G3 re-walks the `path`/`file_path` bug** (BREAK 6) — ships a dead deny rule if built literally.
- **G6 defers its wiring to an unresolved RECON and its verify doesn't force the live path** (BREAK 10).
- **`sandbox_to_production` never gets added to `_WRITE_TOOLS`** (BREAK 3) — Cerberus-level snapshot coverage of the single most dangerous write is left unwired.

So three of the six flagship repairs (G1, G3, G6) have verifications that can go green while the broken behavior survives. That is the plan's central weakness: it correctly diagnosed "looks governed but isn't," then wrote three gate-tests that themselves "look verified but aren't."

## D. Is there any Front-1/2/4 move that writes to Shadow's code/config/memory/host without a gate?

**No move the plan *authors* is an ungated write** — Front 2 is proposal-only with an asserted gitignored `data/reports/` path and a Grimoire trust-level clause (§5.1); Front 4 ships a proposal-only host-write tool "with no execution branch" (§4.2) and an empty allow-list (§4.1); Front 1's scratch files are asserted under `data/` (§5.1). Those are correctly gated.

**But two ambient/ordering hazards let a write happen anyway:**
1. **TestGate `git add -A` auto-commit fires during Front-1 verification, before its §5.1 gate is built** (BREAK 9) — a real autonomous commit of arbitrary dirty tree state.
2. **Front 2's read-only proof is weaker than claimed.** §2.1 proves read-only via `git status --porcelain` empty before==after — but a write under gitignored `data/reports/` (which §2.2 *requires*) **does not show in `git status`**, so the read-only proof would pass even if Front 2 wrote a report to the wrong place, or (worse) wrote into Grimoire's SQLite/ChromaDB (also outside git). The §2.1 proof catches repo-tree writes, not `data/`-tree or DB writes. That's the "read-only proof that wouldn't actually catch a write" you flagged — **MEDIUM**, folded into the record below.

---

## E. The single worst break + step-by-step run-through

**Worst break: BREAK 2 (G1 circular verification), amplified by BREAK 4.** G1 is SUCCESS point 9's flagship — "enforce APPROVAL_REQUIRED for real." If G1 ships green while the fall-through is still live, the entire Gates & Autonomy Ledger is decorative and everyone believes it's real. Here is the blind executor's path to a false PASS:

1. Executor reaches Front 5, §5.0, builds G1: intends to make `orchestrator._step5_execute` hold on `APPROVAL_REQUIRED` instead of falling through at `5254`.
2. Executor writes G1's test per the verify column: *"dispatch a `sandbox_to_production` step; assert the tool did not execute and a pending-approval record exists."*
3. Executor runs the test **against the current tree** (baseline is RED — CLAUDE.md records 17 failing + 2 errors; Abort A1 is supposed to catch this but §5.0 has no A1 precondition on G1's test).
4. The dispatched `sandbox_to_production` routes to `omen._sandbox_to_production` → `TestGate.execute_with_gate` (`omen.py:2881`) → `create_checkpoint` (`test_gate.py:253`, which **auto-commits the dirty tree** — BREAK 9 fires here) → `run_tests()` (`test_gate.py:259`) → baseline RED → `allowed=False` → **the copy never executes** (`test_gate.py:260-273`).
5. G1's first assertion — "the tool did not execute" — is **TRUE**, for the RED-baseline reason, not the approval reason.
6. Executor's "pending-approval record" assertion: TestGate returns a `GateResult` and `_record_history(result)` writes a history row (`test_gate.py:272`). A blind executor mapping "a record exists" onto that history row (or onto any Cerberus audit entry from the earlier `safety_check`, which *does* write an `approval_required` audit entry at `cerberus.py:1024-1029` for `sandbox_to_production` via the `never_autonomous` path) sees a plausibly-matching record.
7. **G1 goes green. The executor signs off "APPROVAL_REQUIRED now enforced."** But `orchestrator.py:5211-5223` was never touched — the fall-through to `module.execute` at `5254` is still live. The moment the baseline turns GREEN (which Front 5's whole point is to enable), the RED-baseline block vanishes, `execute_with_gate` allows the copy, and `sandbox_to_production` **executes autonomously with its APPROVAL_REQUIRED verdict still unenforced** — the exact failure G1 claimed to fix, now hidden behind a green test.
8. Amplifier (BREAK 4): the executor already declared Front 1 "done" earlier via a `structural-fallback` that fired on the keyword-detectable bare-except, so the review path feeding future edits is also a stub wearing a "real" label. Two green gates, two live holes.

**Why this is the worst:** it's self-concealing. Every other break either aborts loudly (BREAK 1 trips A5) or is catchable on careful reading (BREAKs 5–8). BREAK 2 produces a *green* result that certifies the mission's most important deliverable as complete while the danger is fully intact — and the plan's own §0.4.2 already knew the RED-baseline block was "an accident, not a designed gate," yet wrote the G1 verify that the accident satisfies.

**Minimum fix (for the author, not me):** G1's verify must (a) require a GREEN baseline as a precondition (invoke A1 before G1, not just before 1.4), (b) assert the block came from the *approval-hold path* specifically — e.g. a distinct pending-approval queue entry with the tool name and a status field — not merely "a record exists" and "did not execute," and (c) assert that with `sandbox_to_production` swapped for a *non-TestGate* APPROVAL_REQUIRED tool (e.g. `model_pull`, also `never_autonomous`, no TestGate path) the hold still fires — proving the orchestrator enforces the verdict, not TestGate's accident.

---

## F. What I attacked hardest that held

- **The orchestrator enforcement claims (§0.4, G1 target).** I read `5152-5269` and `4600-4660` line by line trying to find that APPROVAL_REQUIRED *was* secretly handled somewhere (a wrapper, a later branch, `never_autonomous` enforced at dispatch). It is not — the plan's diagnosis is exactly right, `5254` is a bare `module.execute` and `4651` sets `cerberus_approved = True` unconditionally. The recon held.
- **The `path`/`file_path` snapshot mismatch (§0.4, G2).** I checked whether some caller normalizes params before the hook, or whether `code_edit` also sets a `path` key. It does not (`omen.py:1550` reads only `file_path`; the ToolResult content uses `file`). Snapshot genuinely no-ops. Held — and I *extended* it (BREAK 6: the same bug bites G3's deny-rule reader, which the plan didn't flag).
- **The `never_autonomous` → APPROVAL_REQUIRED routing for `sandbox_to_production`.** I traced `_safety_check` (`cerberus.py:981-1045`) → `_check_permission_tier` (`1148`) → `auto_register_tool` (`1679`, `never_autonomous` at `1708`) and confirmed the verdict really is APPROVAL_REQUIRED — so the plan's "verdict produced but unenforced" framing is precisely correct, not an overstatement. Held.
- **The 386-test collection count and the Front-2 anchors.** Re-ran collection (386, 0 errors) and grepped every Front-2 anchor; all exact. Held.

These four are the plan's spine and they are sound. The plan's failures are concentrated in (1) one wrong recon fact about `_code_generate` that its own Abort A5 will trip over, and (2) gate-*verification* design — three of six G-rows whose green light doesn't mean what it says, plus two Front-1/2 pass conditions that a stub or a wrong-but-plausible finding can satisfy. The plan diagnosed "looks governed but isn't" brilliantly and then, in G1/G3/G6 and §1.4/§2.3, reproduced the same pattern one level up: tests that look like they'd fail on a broken result but wouldn't.
