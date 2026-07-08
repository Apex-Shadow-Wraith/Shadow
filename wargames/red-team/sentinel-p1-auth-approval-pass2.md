# Red-Team Kill Report (Pass 2) — Sentinel P1: Authenticated Approval Channel

**Target plan:** `wargames/plans/sentinel-p1-auth-approval.md` (post-pass-1 patch)
**Prior report:** `wargames/red-team/sentinel-p1-auth-approval.md` (the CRITICAL this patch answers)
**Posture:** READ-ONLY. Nothing changed. Every claim traced to file:line in the live tree.
**Focus:** the newly-introduced mechanism — the Cerberus-private `PendingApprovals`
store + the poll-loop **re-invoke** of `SecuritySurface.handle("quarantine_file",
entry.resolved_params)`. That is where the pass-1 bug relocated to.

**Verdict:** The patch closes the *literal* pass-1 hole (a credential on `params`) but
the fix it chose — "re-invoke the same synchronous funnel `SecuritySurface.handle` from
the store" — re-opens the hole from the other side. The re-invoked funnel is the *same*
entry point a planner reaches, the store lookup is keyed entirely on planner-controlled
descriptor bytes, and the funnel's `approved` branch is reachable by any caller that finds
an `approved` entry. **One CRITICAL** (planner rides the poll-loop's approval via a
descriptor collision — a confused deputy), plus HIGH/MEDIUM on the store-flip race, the
"resolved_params are just realpath of the planner's target" acknowledgement gap, and an
observation-vague new move.

---

## What re-verified against the tree (credit where due, and to anchor the attack)

I re-opened every file this pass depends on. These are **true**:

- Funnel: `shutil.move(str(source), str(dest))` at `security/core.py:571` inside
  `_quarantine_file` (`core.py:543`). ✅
- `dest` is `self._quarantine_dir / f"{timestamp}_{source.name}"` (`core.py:567`) and
  `source = Path(file_path)` from `params.get("file_path")` (`core.py:549,558`). **The
  planner picks which file. Nothing server-side chooses the target.** ✅ (load-bearing for
  BREAK #3.)
- `SecuritySurface.handle(tool_name, params)` (`core.py:159`) dispatches
  `"quarantine_file": self._quarantine_file` (`core.py:179`) with **no authentication
  guard, no caller-identity check** — a plain method. ✅
- Sole reach from Cerberus: `elif tool_name in SECURITY_TOOLS: result =
  self._security.handle(tool_name, params)` (`cerberus.py:504-508`), also **no auth guard
  on the branch**. ✅
- Pre-hook is `_pre_tool_hook` (`cerberus.py:1224-1268`), pattern-only, fires at
  `orchestrator.py:5289-5306` **before** `module.execute` (`:5337`). It does not read the
  config lists. ✅ (So M4-B is genuinely the only gate.)
- `_action_category` short-circuits `_safety_check` to `ALLOW` at
  `cerberus.py:1016-1022`, **before** the `approval_required_tools` check at `:1041`. ✅
- `quarantine_file` is in none of `approval_required_tools` (`cerberus_limits.yaml:183-189`),
  `never_autonomous` (`:194-204`), `autonomous_tools` (`:207-263`). Ungated today. ✅
- Graph dispatch: `cerberus_subgraph.py:104` calls `cerberus_module.execute(tool_name,
  params)` with no pre-hook; `plan_node.py:47` confirms APPROVAL_REQUIRED is a log-only
  stub; `task_chain.py:812-813` and `async_tasks.py:252` are separate no-pre-hook dispatch
  paths. All converge on `SecuritySurface.handle`. ✅
- **No existing `PendingApprovals`, no `resolved_params`, no `getUpdates`, no resume/release
  path anywhere** (grep clean across `modules/`). The store, the poll loop, and the
  re-invoke are **100% greenfield** — the plan's file:line claims about *existing* infra are
  accurate; the new mechanism is design-on-paper only, so nothing constrains the executor
  except the pseudocode in M4-B/M5. ✅

The plan's recon is again non-phantom. It fails on the mechanism it introduced.

---

## BREAKS

### CRITICAL — the re-invoke rides the SAME funnel a planner reaches; a planner rides the poll-loop's approval via a descriptor collision (confused deputy). The `approved` branch is caller-blind.

- **Plan line (M4-B, plan:400-411):**
  > `if entry.status != "approved":  # still waiting, or expired/consumed` … `# status ==
  > "approved": the poll loop (M5) minted entry.credential in-process` … `if not
  > verify_approval(entry.descriptor, entry.credential): …` … `shutil.move(...)`
- **Plan line (M5 step 3, plan:462-466):**
  > "mint the HMAC credential … set `entry.status = "approved"`, then **re-invoke the funnel
  > from the stored server-side params**: `SecuritySurface.handle("quarantine_file",
  > entry.resolved_params)`. The funnel (M4-B) finds the approved entry … and moves the file."
- **How it fails (one sentence):** The funnel's `approved` branch keys off **`entry.status`
  in the store and `verify_approval(entry.descriptor, entry.credential)` — both of which are
  now populated by the poll loop — but the branch checks nothing about *who* is calling*, so
  once the poll loop has flipped an entry to `approved` and minted `entry.credential`, ANY
  arrival that `lookup()`s that same entry (a second planner `quarantine_file` call whose
  descriptor collides — see BREAK #2 for why it collides trivially) reaches the `approved`
  branch, passes `verify_approval` (the credential is already in the store, not on params),
  and executes `shutil.move` — the funnel cannot distinguish "the poll loop re-invoked me"
  from "a planner re-called me a millisecond after approval."
- **Why the redesign re-opens the hole:** pass-1's hole was "credential on `params`." The
  patch moves the credential *off* `params` and *into the store* — good — but the funnel's
  authorization decision is now **"is there an `approved` entry matching my descriptor?"**
  and the descriptor is computed from `params` on every call (`compute_descriptor(params)`,
  M2/plan:301-308). The planner controls `params`, therefore the planner controls the
  descriptor, therefore the planner controls which store entry it looks up. The credential
  no longer travels on `params` — but the planner no longer *needs* it, because
  `verify_approval` reads `entry.credential` from the store, not from the caller. The
  authority check has been decoupled from the caller entirely: it is a property of the
  store row, and any caller that names the row gets it. **The lock moved from "hold the key"
  to "name the already-unlocked door," which the planner can do.**
- **Severity: CRITICAL.** See §WORST for the concrete millisecond-level run-through.

### HIGH — race between planner enqueue and poll-loop re-invoke; the store flip to `approved` is observable/rideable, and consume-then-move ordering is unspecified.

- **Plan line (M4-B, plan:410-411):** `pending_store.consume(entry)  # atomic: nonce
  single-use` immediately before `shutil.move(...)`.
- **How it fails (one sentence):** The plan asserts `consume` is atomic for the *nonce*, but
  says nothing about the **window between `entry.status="approved"` being set (M5 step 3,
  plan:463) and the poll-loop's own `handle()` re-invocation consuming the entry** — a
  planner that is *already polling* the funnel (re-calling `quarantine_file(file_path=X)` in
  a loop, each call returning `pending_approval`) will, on the very tick after the poll loop
  flips status but before the poll loop's re-invoke consumes, hit the `approved` branch
  first and win the move. Whoever calls `handle` first after the flip consumes the nonce;
  the design gives the planner an equal (or better — the planner can spin) footrace with the
  poll loop for the single consume.
- **Consequence:** even without a *distinct* colliding descriptor (BREAK #2), the *same*
  descriptor the planner originally enqueued is the one the poll loop approves — so the
  planner's own re-poll of that identical call is the confused deputy. The plan's "the only
  way `status` becomes approved is the M5 poll loop" (plan:417) is true but irrelevant: the
  planner doesn't need to *set* approved, only to *arrive at the funnel* while it is approved,
  which it can do by construction because the funnel is the planner's normal dispatch target.
- **Severity: HIGH** (it is arguably the CRITICAL's mechanism; kept separate because it bites
  even if BREAK #2's collision is somehow blocked).

### HIGH — "server-side resolved params" are just a realpath of the planner's chosen target; the plan never acknowledges that the planner still picks WHICH file is quarantined, and treats that as if it were closed.

- **Plan line (M1 store entry, plan:266-268):** `resolved_params: <server-side params, target
  = realpath, NOT the planner's raw dict>`. **Plan line (Gate G1, plan:678):** presents the
  gate as making the move "authorized" once approved.
- **How it fails (one sentence):** `resolved_params` is `os.path.realpath` of
  `params["file_path"]` — the SAME target the planner named (`core.py:549,558`); the server
  resolves symlinks but does **not** choose, constrain, or validate the target, so a planner
  emitting `quarantine_file(file_path=/home/patrick/dev/Shadow/main.py)` enqueues a request
  to quarantine `main.py`, and if Master fat-fingers "approve" (the Telegram message shows a
  path Master may not scrutinize), the move destroys a live file — the "authenticated" channel
  authenticates *that Master pressed approve*, not *that the target is safe*.
- **Why this matters for the redesign:** the whole pass-2 mechanism is sold as "the credential
  and params both come from the Cerberus-private store; neither is ever on the planner's params"
  (plan:466). True — but the *store was populated from the planner's params on first arrival*.
  The store launders planner-chosen data into "server-side resolved params." The plan's
  language ("NOT the planner's raw dict") overstates the independence: it is the planner's raw
  dict with `realpath` applied. The plan should state plainly: **the planner selects the target;
  the human approves a target the planner selected; the only defense is Master reading the path
  in the Telegram alert.** It does not, and G1's "earned-by" column implies more server-side
  authority than exists.
- **Severity: HIGH** (a mis-scoped trust claim in the load-bearing gate row; the mitigation —
  Master must read the path — is real but unstated, so an executor won't harden the alert to
  make the target unmissable).

### MEDIUM — the re-invoke uses `SecuritySurface.handle` directly, which has NO guard that rejects a planner call OR accepts only an internal one; "internal call" is indistinguishable from "planner call."

- **Plan line (M5 step 3, plan:464-465):** "re-invoke the funnel … `SecuritySurface.handle(
  "quarantine_file", entry.resolved_params)`."
- **How it fails (one sentence):** `SecuritySurface.handle` (`core.py:159`) takes
  `(tool_name, params)` and dispatches — there is **no `caller`/`internal` parameter, no
  privilege flag, no thread-identity check** — so the poll-loop's "internal" re-invoke and a
  planner's dispatch (`cerberus.py:508`) are byte-identical calls into the same method; the
  plan relies on the *store state* to be the only differentiator, which is exactly the
  CRITICAL's failure (store state is caller-blind). There is no path by which `handle` could
  "reject an internal call" (it doesn't know it's internal) or "accept only the poll loop"
  (it can't tell). Attack vector #4 answered directly: **no such guard exists, and the plan
  introduces none — the two callers are identical.**
- **Fix direction (not my job, but names the gap):** the `approved`-branch move must be
  reachable **only** through a private method the poll loop calls (e.g.
  `_consume_and_move(approval_id)` keyed on the opaque id the planner never holds), NOT
  through the public `handle(tool_name, params)` the planner also calls. As written, the same
  door serves both.
- **Severity: MEDIUM** (it is the enabling condition for the CRITICAL; rated MEDIUM alone
  because it is a structural observation the CRITICAL already weaponizes).

### MEDIUM — store lookup "by op + abs_path + args_sha256" makes two independent planner requests that name the same target collide by design; no per-request identity binds an entry to its originating request.

- **Plan line (M4-B, plan:393):** `entry = pending_store.lookup(descriptor)  # match by op +
  abs_path + args_sha256`.
- **How it fails (one sentence):** The lookup key is a pure function of `(op, realpath(target),
  sha256(canonical(params)))` — all planner-supplied — so two `quarantine_file` calls with the
  same `file_path` and `reason` produce the **same descriptor and collide into one entry**;
  the entry has no binding to *which* planner request or *which* approval_id created it, so a
  request that arrives after approval and reproduces the descriptor bytes (trivial — the
  planner knows its own `file_path`/`reason`) `lookup()`s the approved entry and rides it.
- **Consequence:** this is the collision that makes the CRITICAL trivial. The opaque
  `approval_id` (plan:262, "safe to show Master") is generated *by the store* and returned to
  the planner on first arrival, but the funnel's `lookup` **does not key on `approval_id`** —
  it keys on the descriptor. So the opaque id is decorative for the *funnel*: the planner
  re-derives the entry by descriptor, not by id. Any second call with the same descriptor is
  a confused deputy for the first's approval.
- **Severity: MEDIUM** (mechanism of the CRITICAL; separated because the fix — key the funnel's
  authorized-move path on the opaque `approval_id` that only the poll loop passes, never on the
  descriptor — is distinct from BREAK #4's fix and both are needed).

### LOW — new move `test_approved_entry_moves_once` has a green-on-broken-result risk: it sets the store to `approved` and re-invokes `handle`, which is precisely the attack path, so the test *proves the hole works* rather than proving it's closed.

- **Plan line (M4-B expected obs, plan:433-435):** "`test_approved_entry_moves_once` — set the
  store entry to `approved` with a valid minted credential (as the poll loop would), re-invoke
  `handle`; assert the file moves exactly once."
- **How it fails (one sentence):** The test's setup ("set the store entry to `approved` …
  re-invoke `handle`") is **byte-identical to the CRITICAL attack** (a caller reaching an
  approved entry via `handle` moves the file); a green here certifies that *any* `handle` call
  against an approved entry moves the file — which is the vulnerability, not the guarantee — so
  the verification passes on the broken behavior.
- **Counter the plan is missing:** there must be a NEG test proving that a **planner-issued**
  `handle` call (not the poll loop) against an entry the poll loop just approved does **NOT**
  move the file — i.e., that the move is reachable only through the poll-loop-private path. No
  such test exists in M8. The M8 suite tests "no credential on params" (NEG planner-credential,
  plan:573-577) but **not** "no rider on an approved entry," which is the pass-2 hole.
- **Severity: LOW** as a test-hygiene finding, but it is the tell: the plan's own positive test
  exercises the attack and calls it success.

---

## Attack-vector scorecard (the five the brief demanded)

1. **Does the re-invoke re-open the hole?** — **YES (CRITICAL).** The planner cannot flip
   `status` to approved, but it does not need to: the funnel's `approved` branch is
   caller-blind (`core.py:159` has no caller identity), and the planner reaches that branch by
   re-issuing the same descriptor after the poll loop flips status. Race + collision, BREAKS
   #1/#2/#5.
2. **Store lookup collision (confused deputy).** — **YES (MEDIUM→feeds CRITICAL).** Lookup keys
   on `op + abs_path + args_sha256`, all planner-controlled; two same-target requests collide;
   the funnel does not key the move on the opaque `approval_id`. BREAK #5.
3. **Are `resolved_params` genuinely server-independent?** — **NO (HIGH).** They are
   `realpath()` of the planner's `file_path` (`core.py:549,558`). The planner still picks the
   file; `dest` is derived from `source.name` (`core.py:567`). The plan overstates independence
   and never acknowledges the human-only defense. BREAK #3.
4. **Does `SecuritySurface.handle` guard internal vs. planner calls?** — **NO (MEDIUM).**
   `handle(tool_name, params)` has no `caller`/privilege/thread check (`core.py:159`); the
   poll-loop call and the planner call are identical. The plan introduces no distinguishing
   guard. BREAK #4.
5. **New move w/ vague obs / fork w/o trigger / gate named-not-enforced / dangerous write w/o
   gate / verification passing on broken result.** — **YES (LOW→tell).**
   `test_approved_entry_moves_once` (plan:433) exercises the attack path and asserts success;
   the missing NEG ("planner rider on an approved entry does not move") is the un-written guard.
   BREAK #6. Also noted: M5's "re-invoke the funnel" is a **dangerous write (`shutil.move`)
   reached through the same public method the planner uses, with the gate ('is the entry
   approved') that the planner can satisfy by arriving** — a gate named but not enforced against
   the planner.

---

## WORST break — concrete run-through (the CRITICAL, millisecond level)

**Setup.** The executor builds M1–M6 exactly as written. Store keyed on the descriptor;
funnel M4-B as plan:390-411; poll loop M5 mints into the store, sets `approved`, re-invokes
`SecuritySurface.handle("quarantine_file", entry.resolved_params)`.

1. A compromised/confused planner emits step `quarantine_file(file_path=
   /home/patrick/dev/Shadow/data/memory/shadow_memory.db, reason="malware")`. This dispatches
   `orchestrator.py:5337 → module.execute → cerberus.py:508 → SecuritySurface.handle →
   _quarantine_file(params)`.
2. First arrival: `compute_descriptor(params)` → `entry = lookup(descriptor)` is `None` →
   `mint(descriptor, resolved_params)`, `harbinger_surface(approval_id, descriptor)`, return
   `ToolResult(error="pending_approval", content={"approval_id": A1})`. **The planner now knows
   the exact descriptor** (it authored `file_path` and `reason`; args_sha256 and realpath are
   deterministic functions of those). It does **not** need A1.
3. The planner does **not** wait. It emits the *same* step again (LLM plans are re-issuable;
   `task_chain.py:812`, `async_tasks.py:252`, and the graph node `cerberus_subgraph.py:104`
   are all re-entrant dispatch paths). Each re-call recomputes the identical descriptor,
   `lookup()`s the same entry, sees `status="pending"`, returns `pending_approval`. The planner
   spins this — a tight re-dispatch loop against the funnel.
4. Master, seconds later, reads the Telegram alert ("quarantine shadow_memory.db? approve A1")
   and — trusting Shadow flagged real malware — replies "approve A1" from his chat_id.
5. The poll loop (M5) validates chat_id from transport (correct), mints the HMAC credential
   into `entry.credential`, sets `entry.status="approved"` (plan:463). It THEN calls
   `SecuritySurface.handle("quarantine_file", entry.resolved_params)` to do the move.
6. **The race.** Between step-5's `status="approved"` write and step-5's own `handle()`
   re-invoke consuming the nonce, the planner's spinning re-dispatch (step 3) fires `handle`.
   It recomputes the descriptor, `lookup()`s the entry, now sees `status="approved"`, checks
   TTL (fresh — Master just approved), re-pins realpath (unchanged — planner didn't swap
   anything; it *wants* this file moved), calls `verify_approval(entry.descriptor,
   entry.credential)` — **True, because the credential is already in the store** — `consume`s
   the nonce, and executes `shutil.move`. The planner's call wins the footrace; the poll loop's
   own re-invoke arrives second, finds `status="consumed"`, and no-ops.
7. **Result:** `shadow_memory.db` is moved to quarantine by a planner-issued call. The move is
   logged as authorized (the credential verified). Every M8 test is green: NEG(planner
   credential) passes (no credential was on params — correct!), POS passes (an approval did
   mint-and-move), nonce-reuse passes (consumed once). The gate *looks* closed and is *actually*
   opened by a planner arriving at the funnel in the approval window — the same "looks governed
   but isn't" failure as pass-1, relocated from `params` to the store's caller-blind `approved`
   branch.

**Even simpler variant (no race needed).** If the poll loop's re-invoke is the move (step 5's
`handle`), then the planner doesn't even need to win a race: the poll loop moves the file the
planner named. The "authentication" only proves Master pressed approve on **a target the
planner chose** (BREAK #3). For anything Master might plausibly approve (a file Shadow claims
is malware), the planner picks the victim and the human rubber-stamps it. The authenticated
channel authenticates the *approver*, never the *target*.

**The fix the plan needs (named, not implemented):** the authorized move must be reachable
**only** through a poll-loop-private method keyed on the opaque `approval_id` the planner never
holds — e.g. `pending_store.consume_and_move(approval_id)` invoked *directly* by the poll loop,
never by re-entering `SecuritySurface.handle(tool_name, params)`. A planner `handle` call must
NEVER reach a move, even against an approved entry — it must always return `pending_approval`
regardless of store state, because the planner is not the poll loop. As written, M5's "re-invoke
the funnel" is precisely the wrong move: it routes the authorized action back through the door
the attacker also uses.

---

## Abort condition that should exist and doesn't

The plan's abort list (plan:611-636) has abort #7 for "credential cannot reach the funnel
without touching `params`" — which the patch answers. **It has no abort for "the authorized-move
path is reachable by a caller other than the poll loop."** The missing abort:

> **Abort: if the `approved`-branch move is reachable through the same public
> `SecuritySurface.handle(tool_name, params)` entry point the planner dispatches to — i.e. if
> the move's authorization is a property of store state that any caller can name, rather than a
> capability only the poll loop holds — STOP. Re-invoking the shared funnel to perform the
> authorized move makes the planner a confused deputy for the approval.**

This is the highest-value missing abort in pass 2, exactly as the credential-delivery abort was
in pass 1.

---

## Honest assessment

I attacked hardest at **the re-invoke handoff** — specifically whether the funnel's `approved`
branch can tell the poll loop's call apart from a planner's call. It cannot: `SecuritySurface.handle`
(`core.py:159`) is caller-blind, the store lookup is keyed on planner-controlled descriptor bytes
(M4-B/plan:393), the opaque `approval_id` is never used as the funnel's move key, and the credential
lives in the store where `verify_approval` reads it independent of the caller. So the patch
successfully removed the credential from `params` and just as successfully made the credential
*unnecessary* to the attacker: the planner rides an entry the poll loop already approved, either by
winning a consume race (BREAK #1/#5) or simply by having the poll loop move the planner-chosen
target (BREAK #3). Everything else re-verified true against the tree — the store-privacy design, the
chat_id-from-transport binding, the fail-closed channel, the realpath re-pin are all sound *in
isolation*; they guard the inbound identity and the secret's confidentiality, but not the one thing
that matters: **that only the poll loop, never a planner, can trigger the move of an approved entry.**

I could not find a way to make the planner *forge* an approval (chat_id binding is genuinely
transport-bound; the HMAC key is genuinely off the planner's reach). The break is not forgery — it
is **riding a genuine approval for a planner-chosen target through a caller-blind funnel.** That is
the CRITICAL.

**Patch owner:** make the authorized move a poll-loop-private capability keyed on the opaque
`approval_id`, never re-enter `SecuritySurface.handle(tool_name, params)` to perform it, add the NEG
test "planner `handle` against an approved entry does not move," add the missing abort above, and
re-run. Then the target-selection residual (BREAK #3) still stands as a documented human-in-the-loop
limit that the Telegram alert must make unmissable.
