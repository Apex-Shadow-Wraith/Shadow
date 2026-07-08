# Red-Team Kill Report — Sentinel P1: Authenticated Approval Channel

**Target plan:** `wargames/plans/sentinel-p1-auth-approval.md`
**Posture:** READ-ONLY. Nothing changed. Every claim traced to file:line in the live tree.
**Verdict:** The plan's recon is unusually honest and mostly verifies. But it has one
**CRITICAL** structural hole (the credential never reaches the funnel by any specified
mechanism → the gate is un-openable OR opened through a planner-visible param) plus
several HIGH/MEDIUM gaps. The single worst break is described in §WORST.

---

## What verified (credit where due)

I opened every file the plan cites. These claims are **true**:

- Funnel: `shutil.move(str(source), str(dest))` at `security/core.py:571` inside
  `_quarantine_file`. ✅
- Sole reach: `elif tool_name in SECURITY_TOOLS: result = self._security.handle(...)` at
  `cerberus.py:504-508` → `SecuritySurface.handle` (`core.py:159-195`, dispatch map line
  179) → `_quarantine_file` (`core.py:543`). ✅
- `quarantine_file` is ungated today: it is in **none** of `approval_required_tools`
  (`cerberus_limits.yaml:183-189`), `never_autonomous` (`:194-204`), or `autonomous_tools`
  (`:207-263`). ✅ (S2 holds.)
- Verdict fall-through (S3): plan-gate at `orchestrator.py:4713-4722` logs
  `APPROVAL_REQUIRED` then sets `plan.cerberus_approved = True` unconditionally at 4722;
  pre-hook at `orchestrator.py:5296-5306` branches only on `DENY`/`MODIFY`,
  `APPROVAL_REQUIRED` falls through to `module.execute` at 5337. ✅
- `CREATOR_AUTH_TOKEN` loads into the live singleton (R1): I ran the check —
  `config.cerberus.creator_auth_token` → `True`. Loader at `creator_override.py:83-87`,
  raise at `:105-110`, compare at `:111`. ✅
- Telegram is outbound-only (S5): `telegram.py:46-110` has `send_message`/`send_alert`
  only; no `getUpdates` anywhere (grep clean). ✅
- Async routes through the graph (S9): `async_tasks.py:241-247`; direct bypass only when
  `self._orchestrator is None` at `:250-252`. ✅
- `emergency_shutdown.py:400` `shutil.move` is not a routed tool (internal archival). ✅ (R3 partial.)

So the plan is not fantasy. It fails on the parts below.

---

## BREAKS

### CRITICAL — the credential-delivery path to the funnel is never specified; the only
### plumbing that exists forces the credential through a planner-visible `params` dict.

- **Plan line (M4 Step B, plan:313-317):** *"In `SecuritySurface._quarantine_file`, BEFORE
  `shutil.move`, call `verify_approval(descriptor, credential)`. If it returns False (or no
  credential is present), return a failure ToolResult and do NOT move."*
- **Plan line (M5 step 3, plan:351-352):** *"call the funnel's release path (hand the
  credential + nonce to the pending action's execution), which flows into `verify_approval`."*
- **How it fails (one sentence):** The funnel is the synchronous
  `SecuritySurface.handle(tool_name, params)` (`core.py:159`) whose ONLY input is `params`,
  and `params` is the LLM-planned step dict (`orchestrator.py:5286` `params = step.get("params", {})`
  → `module.execute(tool_name, params)` at `:5337` → `cerberus.py:508` `self._security.handle(tool_name, params)`);
  there is **no "release path," no resume mechanism, and no pending-action re-dispatch anywhere
  in the tree** (grep for `resume`/`release_path`/re-dispatch on `async_tasks.py` + `orchestrator.py`
  returns only unrelated proactive-engine and Apex-escalation state), so either the credential
  must be injected into `params` (making it a planner-visible field — the exact thing the design
  forbids and M8 NEG(spoof) is supposed to catch) or there is no channel at all and the gate can
  never legitimately open.
- **Why this is the worst:** the plan's entire soundness argument is "the credential/nonce
  never traverse LLM-planned params." But the only wire that reaches `_quarantine_file` **is**
  the planned-params wire. The plan hand-waves a "release path" in M5 that has no counterpart
  in the code and no design in the plan. An executor building this blind has two choices, both
  bad: (a) thread `credential` through `params` (planner-visible → NEG-spoof-defeating by
  construction, and now the planner can *supply* a credential field), or (b) build an
  out-of-band resume queue the plan never scoped — a whole subsystem invented under time
  pressure, un-reviewed, the classic place a TOCTOU or a "trust this dict" shortcut lands.
- **Severity: CRITICAL.**

### HIGH — M4 Step A instructs edits to config lists that the pre-hook never reads; the
### plan mislabels which verdict path it is arming ("looks governed but isn't").

- **Plan line (M4 Step A, plan:299-310):** *"Add `quarantine_file` … to
  `approval_required_tools` … AND `never_autonomous` … Then fix BOTH handlers … Pre-hook
  (`orchestrator.py:5296-5305`): add an `APPROVAL_REQUIRED` branch…"*
- **How it fails (one sentence):** `_pre_tool_hook` (`cerberus.py:1224-1268`) is **purely
  pattern-based** — it iterates `hooks.pre_tool.deny`/`modify` rules and *never consults*
  `approval_required_tools` or `never_autonomous`; those lists are read only by `_safety_check`
  (`cerberus.py:1041-1042`) and `_check_permission_tier` (`:1187-1194`), which feed the
  **plan-gate**, not the pre-hook — so adding `quarantine_file` to those YAML lists produces an
  `APPROVAL_REQUIRED` verdict on the *plan-gate* path only, and the pre-hook branch the plan
  tells the executor to add would never fire from that config change (the pre-hook would need a
  brand-new deny rule, which the plan does not specify).
- **Consequence:** an executor following M4-A literally edits two YAML lists and patches the
  pre-hook to key off a verdict the pre-hook cannot produce for `quarantine_file`. The result
  compiles, tests that assert "verdict == APPROVAL_REQUIRED at the plan-gate" pass, and it
  *looks governed* — but the pre-hook leg is inert. This is exactly the Ledger's G3 row
  ("under-block, fall-through persists") landing silently.
- **Severity: HIGH.**

### HIGH — the plan-gate node in the live graph does not enforce the verdict the plan
### edits; M4-A's plan-gate leg is a no-op post-cutover.

- **Plan line (Ledger G3, plan:525) and M4-A (plan:304-307):** treats the plan-gate handler
  at `orchestrator.py:4713-4722` as a real stop once patched.
- **How it fails (one sentence):** Post-LangGraph-cutover the live driver is the parent graph,
  and `modules/shadow/graph/plan_node.py:47` states in its own docstring that
  **"APPROVAL_REQUIRED is a log-only Phase-1 stub … it does not set `cerberus_approved=False`;
  the plan still ends approved,"** and `cerberus_subgraph.py:37-44` states **"no parent graph
  yet wires the short-circuit edges"** — so the per-step Cerberus verdict computed inside
  `_step4_plan` is *observed but not acted on* by the graph, meaning even a correctly-patched
  `orchestrator.py:4713` branch may be bypassed by the compiled path that actually runs.
- **Consequence:** the plan pins its verdict fix to `_step4_plan`'s embedded loop
  (`orchestrator.py`), but the thing driving execution is the graph, whose plan-gate is a
  documented stub. M4-A could be fully implemented and the graph would still march a
  `quarantine_file` step to dispatch. (The plan's own thesis — "the gate cannot live only in
  the verdict" — is *more* true than the plan realizes; it just under-counts how many verdict
  layers are inert.)
- **Severity: HIGH.**

### HIGH — the poll loop is asserted un-drivable, but the plan's own credential-mint step
### routes through no boundary the plan verifies; the "planner can't drive it" claim is
### only tested against chat_id, not against the mint→funnel handoff.

- **Plan line (M5, plan:353-354):** *"This loop runs in Cerberus, not in planner-authored
  code … The planner has no Telegram send capability … and no read access to the poll loop's
  state."*
- **How it fails (one sentence):** The claim "planner can't drive the intake" is tested only
  by `test_poll_loop_binds_chat_id` / `test_chat_id_from_transport_not_text` (plan:359-371),
  which guard the *inbound* identity — but the *outbound* half (mint credential → deliver to
  the pending action) has no boundary test at all, and because there is no pending-action store
  wired to a resume path (see CRITICAL), the loop's minted credential has nowhere to go except
  back through a planner-touchable dispatch, so "un-drivable intake" is proven while
  "un-drivable *use* of the mint" is merely asserted.
- **Note:** S6/R4 is also under-settled — Cerberus is built with
  `module_configs.get("cerberus", {})` (`main.py:190`) and reads `config.get("telegram")` for
  emergency shutdown (`cerberus.py:159`), a key **not populated for Cerberus today**; the plan
  flags this as R4 but M5's abort conditions don't cover "token silently absent → loop starts,
  never receives, approvals hang forever" (fail-open-to-hang, not fail-closed).
- **Severity: HIGH.**

### MEDIUM — `_action_category` bypass in `_safety_check` is a planner-supplied param that
### short-circuits the approval check, and the plan never mentions it.

- **Live code:** `_safety_check` at `cerberus.py:1015-1022` — if
  `action_params.get("_action_category")` is a creator-authorized category,
  `is_category_authorized` (`creator_override.py:304-306`) returns True and the function
  returns `ALLOW` **before** the `approval_required_tools` check at `:1041`.
- **How it fails (one sentence):** `_action_category` is read straight from the planner's
  `action_params`, so once *any* category has been persistently authorized via
  `creator_authorize` (which does require the token — `creator_override.py:258`), a planner can
  attach that category label to a `quarantine_file` step and skip the approval verdict entirely
  — the plan's descriptor/HMAC design never covers this label channel because the plan only
  models the funnel leg, not the verdict leg's category escape hatch.
- **Why MEDIUM not HIGH:** the category must have been token-authorized once, so it is not a
  cold-start bypass; and if M4-B (funnel) were real it would still catch the move. But the plan
  claims "there is no 'the planner said this was approved' field anywhere" (plan:243) — that is
  **false**: `_action_category` is exactly such a field on the verdict path.
- **Severity: MEDIUM.**

### MEDIUM — R3 (second-funnel sweep) is under-scoped; the plan greps `modules/cerberus/`
### and `modules/omen/` only, missing the rest of the tree.

- **Plan line (R3, plan:183-188):** grep is
  `modules/cerberus/ modules/omen/` for `shutil.move|shutil.copy|os.remove|...`.
- **How it fails (one sentence):** A host-mutating primitive reachable from a routed tool in
  `modules/reaper/`, `modules/nova/`, `modules/grimoire/`, or the graph nodes (e.g.
  `task_chain.py:813` is a *separate* `module.execute` dispatch with **no pre-hook** at all)
  would be a second ungated funnel outside the two directories R3 inspects, so the abort
  condition "any planner-reachable host mutation NOT behind the funnel" (plan:186) can be
  answered "clear" while a hole sits one directory over.
- **Evidence the extra dispatch path is real:** `module.execute` is invoked with no pre-hook
  at `task_chain.py:813`, `async_tasks.py:252`, and every `modules/shadow/graph/*_node.py`
  (e.g. `cerberus_subgraph.py:104`). The plan's M4-B funnel gate *does* cover all of these for
  `quarantine_file` specifically — but R3's job is to prove no *other* host mutation exists, and
  its grep scope can't prove that.
- **Severity: MEDIUM.**

### MEDIUM — TOCTOU: the descriptor is computed at the funnel, but the credential is minted
### asynchronously by a human over Telegram; the plan's `not_after` TTL (120s) is smaller
### than a plausible human reply latency, and nothing re-pins the realpath at move time.

- **Plan line (M2, plan:239 + plan:255-256):** `not_after = utcnow + SHORT_TTL # e.g. 120s`;
  "resolve once, gate on the resolved path, move the resolved path."
- **How it fails (one sentence):** Between descriptor-mint (funnel entry) and credential
  arrival (Master reads the Telegram alert, types "approve <id>"), a real human takes longer
  than 120s often enough that either the TTL is raised (widening the swap window) or approvals
  routinely expire (fail-to-hang), and because there is no resume path (CRITICAL) the "move the
  resolved path" guarantee is untested against the case where the action is re-submitted fresh
  after approval — a re-submission recomputes `realpath` at a *new* time, re-opening the TOCTOU
  the plan claims to have closed.
- **Severity: MEDIUM** (contingent on how the un-specified resume is built).

### LOW — verification V0/M8 NEG(spoof) can report the file "stayed put" for the wrong
### reason (`source.exists()` guard, not the gate).

- **Plan line (M8 NEG-spoof, plan:438-442):** *"Planner sets params={"file_path": tmpfile,
  "source": "approved"} … Assert the tmpfile is still at its original path … Today this test
  is RED."*
- **How it fails (one sentence):** `_quarantine_file` already returns failure without moving if
  `not source.exists()` (`core.py:559-563`), so a NEG(spoof) test that points at a
  non-existent/misspelled path asserts "file not moved" and passes for a reason unrelated to
  the gate — the executor must use a **real existing tmpfile** or V0 is vacuous in the opposite
  direction (the plan warns about vacuous-green at plan:459 but not about this vacuous-red
  variant).
- **Severity: LOW** (test-hygiene, catchable if the executor is careful).

---

## Abort condition that should exist and doesn't

The plan's abort list (plan:468-484) covers the second funnel, the un-private poll loop, the
unloaded token, vacuous NEG-spoof, the M7 hole, and a leaked nonce. **It has no abort for the
credential-delivery gap** — i.e. "if there is no out-of-band channel to hand a Cerberus-minted
credential to the synchronous funnel without routing it through planner-visible `params`, STOP."
That is the one failure that silently forces the executor into either a planner-visible
credential field or an un-reviewed resume subsystem. It is the highest-value missing abort.

---

## WORST break — concrete run-through

**The single worst break is the CRITICAL above: no specified path delivers the credential to
the funnel, and the only existing path is planner-visible `params`.** Concrete run-through an
executor lands blind:

1. Executor builds M1/M2/M3 exactly as written: `PendingApprovals` store, descriptor computed
   in `_quarantine_file`, `verify_approval(descriptor, credential)` called before
   `shutil.move` (`core.py:571`). Good so far.
2. Executor reaches M4-B and must answer: *where does `credential` come from inside
   `_quarantine_file`?* The function's only input is `params` (`core.py:543`,
   `handle(tool_name, params)` at `:159`, dispatched from `cerberus.py:508` with the LLM-planned
   `params` from `orchestrator.py:5286`).
3. There is no resume queue, no pending-action re-dispatch, no "release path" in the tree
   (verified: grep for resume/release on `async_tasks.py` + `orchestrator.py` finds nothing of
   the sort). The plan's M5 step 3 "hand the credential to the pending action's execution" has
   no code counterpart to hand it *to*.
4. Under time pressure the executor takes the path of least resistance: read `credential =
   params.get("_approval_credential")` inside the funnel. This compiles. `test_funnel_blocks_
   without_credential` (plan:319-322) passes (no field → no move). `POS` passes (test injects
   the field). All six M8 assertions can be made green.
5. **But now the credential is a planner-writable param.** The moment the poll loop (M5) mints
   a real credential and the executor must get it *into* that param for the real flow, the field
   is on the same LLM-planned dict a compromised/confused planner controls — and worse, a
   planner that can *observe* one valid `(descriptor, credential)` pair (from any log, any
   echoed ToolResult, any M6 message that accidentally includes it) can replay it into a
   `quarantine_file` step's `params` and move a file **without any Telegram round-trip at all.**
   The HMAC binds the credential to the descriptor, but the descriptor is computed from
   `params` the planner supplied — so the planner controls both halves of the bound pair for
   any target it names.

The gate *looks* closed (green tests, HMAC, nonce, TTL) and is *actually* opened by a field on
the planner's own dict. That is the "looks governed but isn't" failure at maximum severity,
and it flows directly from the plan never specifying the one wire that matters.

---

## Honest assessment

I attacked hardest at **the credential→funnel handoff** and it broke cleanly: the plan proves
the *inbound* identity boundary (chat_id from transport) and the *store* privacy, but never
builds or specifies the wire that carries a minted credential from the Cerberus poll thread
into the synchronous `handle(params)` funnel — and the only wire that physically reaches that
funnel today is the planner-controlled `params` dict. Everything else the plan claims about the
funnel, the token load, the outbound-only Telegram, and the verdict fall-through **verified
true against the tree.** The design's instinct ("gate at the funnel, not the verdict") is
correct and its recon is refreshingly non-phantom — but the funnel gate it specifies has no
legitimate key-delivery mechanism, so as written it is either un-openable or opened through the
exact channel it swore off. Patch owner: define the out-of-band credential-delivery path (a
Cerberus-private resume queue keyed by the opaque approval-id, credential never on `params`)
and add the missing abort for its absence, then re-run.
