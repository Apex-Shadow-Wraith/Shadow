# Battle Plan — Sentinel P1: Authenticated Approval Channel

**Mission:** Build the authenticated approval channel that makes gated host actions
(quarantine, and later firewall-apply / install) openable by genuine Master authority
only. Resolves the two architecture residuals the prior Sentinel wargame booked as
BLOCKED-on-Master/Opus:
- **AR-P1-1** — no authenticated approval channel (approval authority was un-bindable).
- **AR-P1-2** — secret-reachability boundary (nothing mechanically stops a tool from
  reading `.env`; "nothing tool-calls .env" was a promise, not a mechanism).

**Fork chosen (from the spec):** local-token authority made sound by an *enforced*
unreachability boundary — not an off-box key. `verify_approval()` is built as a swap
seam so the off-box Ed25519 upgrade is a one-function repoint, never a rewrite.

**Executor:** Opus 4.8, max effort, on its own turn. This document is the route.
Read it top to bottom before touching a file.

---

## Patch log — red-team pass 1 (`wargames/red-team/sentinel-p1-auth-approval.md`)

A fresh attacker traced every claim to the tree. Its recon confirmed the plan is not
fantasy (funnel, token-load, verdict fall-through, outbound-only Telegram all verified).
It landed one **CRITICAL** and several HIGH/MEDIUM breaks. All are patched below:

- **CRITICAL — credential-delivery wire was never specified.** The funnel is the
  synchronous `SecuritySurface.handle(tool_name, params)` whose only input is the
  LLM-planned `params`. The original M5 "release path" had no code counterpart, forcing a
  blind executor to either put the credential on `params` (planner-visible — defeats the
  whole design and enables replay) or invent an un-reviewed resume subsystem. **Fix: the
  funnel itself enqueues-and-defers on first (planner) arrival; the move is re-invoked by
  the Cerberus poll loop from a Cerberus-private pending-action store; the credential is
  minted and consumed entirely in-process and NEVER travels on `params`.** Rewritten in
  M1, M4, M5; new abort #7.
- **HIGH — the pre-hook cannot read the config lists (M4-A was inert).** `_pre_tool_hook`
  ([cerberus.py:1224-1268](../../modules/cerberus/cerberus.py#L1224)) is pattern-only; it
  never consults `approval_required_tools`/`never_autonomous` (those feed the *plan-gate*,
  not the pre-hook). **Fix: M4 makes the funnel the SOLE load-bearing gate; the verdict-path
  edits are demoted to optional advisory surfacing and corrected.**
- **HIGH — the graph plan-gate is a documented stub.**
  [plan_node.py:47-48](../../modules/shadow/graph/plan_node.py#L47) ("APPROVAL_REQUIRED is a
  log-only Phase-1 stub … the plan still ends approved") and
  [cerberus_subgraph.py:37-44](../../modules/shadow/graph/cerberus_subgraph.py#L37) ("no
  parent graph yet wires the short-circuit edges"). **Fix: same as above — the funnel, below
  the dispatch fork, is the gate; no verdict layer is relied upon.**
- **MEDIUM — `_action_category` is a planner-supplied "approved" field.**
  [cerberus.py:1015-1022](../../modules/cerberus/cerberus.py#L1015) returns ALLOW on a
  planner-supplied `_action_category` before the approval check. **Fix: corrected the false
  claim in M2; the funnel ignores all verdict labels; added `test_action_category_does_not_move`.**
- **MEDIUM — R3 second-funnel grep was under-scoped** (only `cerberus/`+`omen/`). **Fix:
  widened to the whole `modules/` tree + graph nodes; named `task_chain.py:813`.**
- **MEDIUM — TOCTOU/TTL.** 120s TTL < human reply latency; no realpath re-pin at move time.
  **Fix: TTL raised and the funnel re-pins realpath at move time (M2/M4-B); a target swapped
  during the wait is detected and denied.**
- **LOW — NEG(spoof) vacuous-red risk** via the `source.exists()` guard. **Fix: M8 mandates
  a real existing tmpfile.**

### Red-team pass 2 (`sentinel-p1-auth-approval-pass2.md`)

Pass 2 attacked the pass-1 fix and landed a second **CRITICAL**: the fix relocated the hole rather
than closing it. The patched design had the poll loop re-invoke `SecuritySurface.handle` to perform
the move, and the funnel's authorization was "does an `approved` store entry matching my descriptor
exist?" — but `handle` is caller-blind and the descriptor is computed from planner-controlled
`params`, so a planner re-issuing the same call could ride a genuine approval (a confused deputy via
descriptor collision + a consume race). **Fix: the planner-reachable funnel (`_quarantine_file` via
`handle`) NEVER moves a file — it only enqueues; the move is a separate poll-loop-private capability
`_execute_approved(approval_id)`, keyed on the opaque id, not routable, not descriptor-keyed.**
Rewritten in M4 (Step B1/B2), M5 step 3, M1 (approval_id-keyed store); new abort #9; new tests
`test_handle_never_moves`, `test_execute_approved_not_routable`, `test_planner_cannot_ride_approved_entry`,
`test_approval_id_binds_target`. Pass 2 also surfaced (HIGH) that the planner still *selects* the
target — the channel binds and authenticates the target via `approval_id` but does not vouch it is
safe; the only defense is Master reading the absolute path in the alert, so M6's alert must show it
unmissably (residual R6).

### Red-team pass 3 (`sentinel-p1-auth-approval-pass3.md`)

Pass 3 **could not break the approval mechanism** — it attacked `_execute_approved`'s unreachability
(hardcoded dict dispatch, no `getattr`; MCP servers are hardcoded routes; `tool_creator` writes to
disk without in-process exec; `scaffold_test`'s dynamic import is shape-locked and can't name the
mover), the approval-id binding, the chat_id transport binding, and nonce/credential confidentiality
— all held. **The B1/B2 two-method design has converged.** But pass 3 landed a **new CRITICAL of
SCOPE, not mechanism**, and a HIGH on alert-text control:

- **CRITICAL (scope) — the recon claim "quarantine_file is the only live host-mutating op" is FALSE**,
  and it trips this plan's own abort #1. Verified in the tree: **`code_edit`** is an Omen tool in
  `autonomous_tools` ([cerberus_limits.yaml:223](../../config/cerberus_limits.yaml#L223)) that does
  `path.write_text` on an arbitrary target ([omen.py:1606](../../modules/omen/omen.py#L1606)), guarded
  only by `PROTECTED_PATHS = {"config", ".git", ".env"}` ([omen.py:443](../../modules/omen/omen.py#L443))
  — so `modules/`, `main.py`, `data/`, **and the gate's own source `modules/cerberus/security/core.py`**
  are writable, unauthenticated, never touching `SecuritySurface.handle`. **`sandbox_to_production`**
  ([omen.py:2840](../../modules/omen/omen.py#L2840)) does `shutil.copy2`/`unlink` to a planner-chosen
  path ([sandbox.py:1126,1141,1144](../../modules/omen/sandbox.py#L1126)); it is in the approval lists
  but those verdicts are discarded (S3). A full sweep finds ~10 host-write sites across omen/sandbox/
  nova/grimoire. **Fix: corrected the scope claim (§0); added the SCOPE BOUNDARY section; fired abort
  #1 as an explicit finding; strengthened R3 into a mandatory build-time enumeration with an abort;
  and scoped full host-write safety to a named prerequisite/parallel mission.** This mission builds
  the approval CHANNEL and gates its funnel correctly — it does NOT by itself make Shadow's host-write
  surface safe.
- **HIGH — alert-text controllability.** R6 hardened path *visibility*, but the planner controls the
  `reason` free-text ([core.py:550](../../modules/cerberus/security/core.py#L550)) rendered on a
  `parse_mode:"HTML"` channel with no `html.escape` and no flood control, and can post competing
  `notification_send` messages (its `never_autonomous` verdict is inert per S3) — so Master can be
  steered to approve the wrong `approval_id`. **Fix: M6 hardened — escape planner text, isolate it
  from the server-computed authorization line, address competing-message flooding.**

---

## 0. Enforcement point — the spec's line is a PHANTOM; the real funnel is elsewhere

> Spec: "Enforcement point: the single dangerous-action funnel at `cerberus.py:488`
> (re-confirm the line against the working tree at build — carried from the red-team
> report, phantom-count doctrine applies)."

**Re-confirmed against the working tree — `cerberus.py:488` is NOT a funnel.** Line 488
is `tool_name=tool_name,` inside the `creator_authorize` branch's `return ToolResult(...)`
([cerberus.py:488](../../modules/cerberus/cerberus.py#L488)). It moves nothing, executes
no host action. The phantom-count doctrine the spec invoked is exactly right: **do not
build the gate at line 488.**

**The real single dangerous-action funnel today is:**
- The live host mutation is `shutil.move(str(source), str(dest))` at
  [security/core.py:571](../../modules/cerberus/security/core.py#L571), inside
  `SecuritySurface._quarantine_file`.
- It is reached through exactly one caller:
  `elif tool_name in SECURITY_TOOLS: result = self._security.handle(tool_name, params)`
  at [cerberus.py:504-508](../../modules/cerberus/cerberus.py#L504), which dispatches to
  `SecuritySurface.handle` → `_quarantine_file` → the `shutil.move`.
- `SECURITY_TOOLS` is a frozenset of 24 names
  ([security/core.py:57-83](../../modules/cerberus/security/core.py#L57)); of those,
  **`quarantine_file` is the only one whose body mutates the host** (it moves a file).
  All others are read/analyze/propose (`firewall_generate` returns rule text; it does
  **not** apply it).

**Consequence for the plan:** the gate is installed at the funnel that the live
dangerous op actually traverses — `SecuritySurface.handle` for `quarantine_file`
(security/core.py) — **and** at the orchestrator's two verdict handlers (defense in
depth, see M4). Building it at `cerberus.py:488` would gate a return-statement and leave
the `shutil.move` wide open. This is the "looks governed but isn't" trap, pre-empted.

### The descriptor `op` enum vs. reality (plan against the code, not the spec)

The spec's descriptor lists `op ∈ {quarantine | av_scan | firewall_apply |
software_install | move}`. Recon settles which of these are live host-mutating ops
**today**:

| Spec op | Live host-mutating body today? | Evidence |
|---|---|---|
| `quarantine_file` / `move` | **YES** — `shutil.move` | [security/core.py:571](../../modules/cerberus/security/core.py#L571) |
| `software_install` | **NO live body found** — a config *name* only | in `approval_required_tools` + `never_autonomous` ([cerberus_limits.yaml:188,199](../../config/cerberus_limits.yaml#L188)); no handler in `SecuritySurface.handle` map ([core.py:168-193](../../modules/cerberus/security/core.py#L168)) and no `_install`/`subprocess` host-install body in `modules/cerberus/`. RECON NEEDED R2. |
| `firewall_apply` | **NO — does not exist** | firewall tools are `firewall_analyze/evaluate/compare/explain_rule/generate`, all analysis/propose, all in `autonomous_tools` ([cerberus_limits.yaml:246-250](../../config/cerberus_limits.yaml#L246)). No `firewall_apply` anywhere. |
| `av_scan` | **NO — does not exist** | `threat_scan`/`vulnerability_scan` are read-only; no ClamAV integration in tree. |

**So behind the `SecuritySurface.handle` funnel, the gate protects exactly one live op today:
`quarantine_file`.** The seam is built generically (descriptor + `verify_approval`) so
`firewall_apply`, `software_install`, `av_scan` snap in behind the *same* gate the day their
host-mutating bodies are built — but the plan does not pretend those bodies exist. M2's descriptor
`op` enum is seeded with `quarantine_file` and marked extensible.

**⚠ CORRECTION (red-team pass 3): `quarantine_file` is NOT the only planner-routable host mutation
in the tree — only the only one behind THIS funnel.** `code_edit` (autonomous, arbitrary
`write_text`, [omen.py:1606](../../modules/omen/omen.py#L1606)) and `sandbox_to_production`
([omen.py:2840](../../modules/omen/omen.py#L2840)) mutate arbitrary planner-chosen paths without ever
touching `SecuritySurface.handle`. This mission gates its funnel; it does not gate theirs. See the
SCOPE BOUNDARY section immediately below — this is load-bearing for what "done" means here.

---

## ⚠ SCOPE BOUNDARY & CRITICAL RESIDUAL — the approval channel is one funnel; host-write safety is more (pass-3)

**What this mission delivers:** an authenticated approval channel that makes the `SecuritySurface.handle`
funnel safe — `quarantine_file` today, plus the descriptor-enum ops when built. The mechanism
(M1–M8) is sound and pass-3-converged.

**What this mission does NOT deliver, and must not be read as delivering:** safety of Shadow's
*entire* host-write surface. Verified planner-routable host mutations that bypass this funnel entirely:
- **`code_edit`** — `autonomous` ([cerberus_limits.yaml:223](../../config/cerberus_limits.yaml#L223)),
  arbitrary `path.write_text` ([omen.py:1606](../../modules/omen/omen.py#L1606)), guarded only by
  `PROTECTED_PATHS = {"config",".git",".env"}` ([omen.py:443](../../modules/omen/omen.py#L443)) —
  `modules/`, `main.py`, `data/`, and **the gate's own source** are writable, unauthenticated. An
  attacker who wants a file destroyed or backdoored simply does not call `quarantine_file`.
- **`sandbox_to_production`** — `shutil.copy2`/`unlink` to a planner-chosen path
  ([sandbox.py:1126,1141,1144](../../modules/omen/sandbox.py#L1126)); in the approval lists, but those
  verdicts are discarded (S3).
- A full sweep finds ~10 host-write sites across `omen/`, `sandbox/`, `nova/`, `grimoire/`.

**This trips the plan's own abort #1** ("any planner-reachable host mutation NOT behind the funnel is
an abort-and-flag"). The honest consequence:
1. **This mission is scoped to the approval channel + its funnel.** It is buildable and correct within
   that scope.
2. **Full host-write safety is a SEPARATE, named mission** — route every host-write tool (`code_edit`,
   `sandbox_to_production`, and the full R3 enumeration) through the same descriptor + `verify_approval`
   seam, OR gate each independently. This overlaps the existing Omen self-mod wargame
   (`wargames/plans/omen-part3-selfmod.md`) — cross-reference it; do not duplicate or contradict it.
   The most dangerous single item is `code_edit`'s ability to edit the approval gate's own source, so
   that tool ranks first in the follow-on mission.
3. **Abliteration-gate correction:** "approval channel canary-green" must NOT be read as "host-write
   surface safe." The Heretic run's host-write precondition is the WHOLE surface gated (this funnel +
   `code_edit` + `sandbox_to_production` + the R3 set), not this funnel alone. G6 and the abliteration
   row are updated accordingly.

---

## 1. Recon findings — settled state (every claim file:line-anchored)

**S1 — The funnel and its single caller.** `shutil.move` at
[security/core.py:571](../../modules/cerberus/security/core.py#L571); sole reach via
[cerberus.py:504-508](../../modules/cerberus/cerberus.py#L504). Confirmed no second
caller of `_quarantine_file` (`grep -rn "_quarantine_file\|_security.handle" modules/`
returns only the dispatch site + the def).

**S2 — `quarantine_file` is UNGATED on the live path today (the must-fail-today control
is real).** `quarantine_file` is **not** in `approval_required_tools`
([cerberus_limits.yaml:183-189](../../config/cerberus_limits.yaml#L183)), **not** in
`never_autonomous` ([:194-204](../../config/cerberus_limits.yaml#L194)), and **not** in
`autonomous_tools` ([:207-263](../../config/cerberus_limits.yaml#L207)). The pre-hook
`_pre_tool_hook` runs only `hooks.pre_tool.deny` pattern rules
([cerberus.py:1224-1245](../../modules/cerberus/cerberus.py#L1224)); none match
`quarantine_file`, so it returns ALLOW and the `shutil.move` executes. **A planner that
emits `quarantine_file(file_path=X)` moves the file today, unauthenticated.** This is
what NEG(spoof) must prove closed.

**S3 — The two verdict handlers ignore `APPROVAL_REQUIRED`.**
- Pre-hook handler branches on `DENY` and `MODIFY` only; `APPROVAL_REQUIRED` falls
  through to `module.execute`
  ([orchestrator.py:5296-5305](../../modules/shadow/orchestrator.py#L5296), execute at
  [:5334](../../modules/shadow/orchestrator.py#L5334)).
- Plan-gate handler *logs* `APPROVAL_REQUIRED` and proceeds — the code comment literally
  says "Phase 1: print to console for approval / Phase 2+: Telegram approval workflow"
  ([orchestrator.py:4713-4722](../../modules/shadow/orchestrator.py#L4713)).
  `plan.cerberus_approved = True` is set unconditionally after
  ([:4722](../../modules/shadow/orchestrator.py#L4722)).

So even *listing* `quarantine_file` as approval-required would not stop it — the verdict
is computed then discarded. This is why the gate cannot live only in the verdict; it must
live at the funnel (M4 step B).

**S4 — `CREATOR_AUTH_TOKEN` is now SET.** `.env` at repo root contains a non-empty
`CREATOR_AUTH_TOKEN` (verified by presence+non-empty check, key names only — value never
read). This **resolves the prior wargame's BLOCKED item** ("token unset → verify raises").
`CreatorOverride._auth_token` loads it from the singleton
([creator_override.py:83-87](../../modules/cerberus/creator_override.py#L83)).
`verify_hardware_auth` raises `RuntimeError` iff the token is falsy
([:105-110](../../modules/cerberus/creator_override.py#L105)); with it set, returns
`token == self._auth_token` ([:111](../../modules/cerberus/creator_override.py#L111)).
**RECON NEEDED R1** confirms it actually loads into the live singleton (present-in-`.env`
≠ loaded-into-process).

**S5 — Telegram is OUTBOUND ONLY. The inbound poll loop does not exist — it must be
built.** `TelegramDelivery` has `send_message`/`send_alert` that POST to `sendMessage`
([harbinger/telegram.py:46-110](../../modules/harbinger/telegram.py#L46)). There is **no
`getUpdates`, no polling loop, no inbound-reply handler** anywhere
(`grep -rn "getUpdates\|poll\|get_updates" modules/` returns nothing in the Telegram
path). The spec's Component 3 ("the polling loop that receives the reply runs in
Cerberus") describes a component that **is not in the codebase** — M5 builds it. The
spec's own warning applies: "the regression that guts this design is the poll loop
quietly moving into something the planner can drive."

**S6 — Telegram creds live in Harbinger settings, not Cerberus.** `_shadow_config.harbinger`
carries `telegram_bot_token` / `telegram_chat_id`
([harbinger.py:81-92](../../modules/harbinger/harbinger.py#L81)), both SET in `.env`.
Cerberus is constructed with `module_configs.get("cerberus", {})`
([main.py:190](../../main.py#L190)) and reads `config.get("telegram")` for emergency
shutdown ([cerberus.py:159](../../modules/cerberus/cerberus.py#L159)) — **that key is not
populated for Cerberus today.** M5 must wire the bot token + chat_id into the Cerberus
poll-loop component (or have it read the singleton directly). RECON NEEDED R4.

**S7 — `source` is not authoritatively bound at request ingress.** `process_input(self,
user_input, source: str = "user")` ([orchestrator.py:1190](../../modules/shadow/orchestrator.py#L1190))
is a defaulted arg; `main.py` calls it without a source. This was the prior CRITICAL. **The
spec's design does not fix request-source binding and does not need to** — approval identity
is bound at the *approval* channel (the Telegram `chat_id` on the inbound reply), which never
traverses LLM-planned params. This is the architectural move that unblocks AR-P1-1.

**S8 — The nonce-leak surface the prior HIGH found.** `decision_queue_read` returns raw
item dicts with no redaction and is an autonomous tool
([harbinger.py:580-602,214-218](../../modules/harbinger/harbinger.py#L580)); `_decision_queue_resolve`
returns the whole item ([:648-653](../../modules/harbinger/harbinger.py#L648)). **The spec's
Component 1 avoids this entirely** by minting the nonce into a Cerberus-process pending-approval
store the planner never sees — NOT onto a decision_queue item. M1 must guarantee that store is
never serialized by any routed/autonomous tool (verified in M8 NEG-leak).

**S9 — Async path routes through the graph plan-gate (Item-13 intact).** The async worker
calls `run_deferred_through_graph(task.description, source="autonomous")`
([async_tasks.py:241-247](../../modules/shadow/async_tasks.py#L241)); the direct
`module.execute` bypass fires only when `self._orchestrator is None`
([:250](../../modules/shadow/async_tasks.py#L250)). So both sync and async reach the
funnel — but the funnel-level gate (M4 step B) covers both regardless, because it sits
below the dispatch fork.

**S10 — Registry enumerator exists.** `ModuleRegistry.list_tools()`
([base.py:432-453](../../modules/base.py#L432)) enumerates every ONLINE module's
`get_tools()`. `get_module_for_tool` ([base.py:425-430](../../modules/base.py#L425))
maps tool→module. M7's "derive path-taking tools from the live registry, not a hand-list"
is buildable on this.

---

## 2. RECON NEEDED — settle these AT BUILD before the dependent move (exact checks)

- **R1 — Does `CREATOR_AUTH_TOKEN` actually load into the live singleton?** Present in
  `.env` ≠ loaded. **Check:** in the venv,
  `python -c "from shadow.config import config; print(bool(config.cerberus.creator_auth_token))"`
  → must print `True`. If `False`, the `.env` key isn't wired to `cerberus.creator_auth_token`
  (name mismatch / wrong section) — **fix the config wiring, do NOT hardcode a token.**
  Gates M3, M8-POS.
- **R2 — Is `software_install` a live host-mutating tool or a config-only name?** **Check:**
  `grep -rn "software_install" modules/ | grep -v limits` and inspect any handler. If there
  is no handler with a real install body, the descriptor `op` enum ships with `quarantine_file`
  only and `software_install`/`firewall_apply`/`av_scan` are documented as
  "seam-ready, no live body." Gates M2's enum.
- **R3 — MANDATORY host-write enumeration (pass-3 made this load-bearing, not a spot-check).** The
  executor MUST run, before building, a whole-tree sweep and reconcile it against the KNOWN set:
  `grep -rn "shutil.move\|shutil.copy\|shutil.copy2\|shutil.rmtree\|os.remove\|os.rename\|os.unlink\|\.unlink(\|\.rename(\|\.write_text\|\.write_bytes\|open([^)]*[\"'][wa]" modules/`
  across ALL modules AND `modules/shadow/graph/*_node.py`. For each hit, determine whether it is
  reachable from a **routed tool** (in some module's `get_tools()`), and if so, whether it passes
  through `SecuritySurface.handle`. **KNOWN ungated host-writes outside the funnel (pass-3 verified):
  `code_edit` ([omen.py:1606](../../modules/omen/omen.py#L1606)), `sandbox_to_production`
  ([sandbox.py:1126](../../modules/omen/sandbox.py#L1126)).** These are documented in the SCOPE
  BOUNDARY section and are OUT of this mission's funnel — do not silently "cover" them here.
  **Abort trigger:** if the sweep finds a routed host-write NOT in the known set and NOT behind the
  funnel, **stop and flag** (abort #1) and add it to the SCOPE BOUNDARY / follow-on mission — do not
  proceed as if the funnel covers it. Extra dispatch paths with NO pre-hook that the sweep must
  account for: `module.execute` at [task_chain.py:813](../../modules/shadow/task_chain.py#L813),
  [async_tasks.py:250](../../modules/shadow/async_tasks.py#L250), and each graph `*_node.py`.
  `emergency_shutdown.py:400`'s `shutil.move` is confirmed NOT routed (internal archival).
- **R4 — How does the Cerberus poll loop get the bot token + chat_id?** **Check:** confirm
  `_shadow_config.harbinger.telegram_bot_token` / `.telegram_chat_id` are the canonical source
  and decide the wire: either main.py passes them into the Cerberus config dict, or the poll-loop
  component reads the singleton. Gates M5. Do NOT duplicate the secret into a new config key.
- **R5 — Confirm the funnel line at build.** `grep -n "shutil.move" modules/cerberus/security/core.py`
  → expect one hit (currently line 571). If the line moved, re-anchor M4 step B to the live line.
  Phantom-count doctrine: never trust the carried number.
- **R6 — DOCUMENTED RESIDUAL (not a bug; a human-in-the-loop limit).** The planner selects which
  file is proposed for quarantine; the channel binds+authenticates the target to the approval via
  `approval_id` but does not vouch the target is safe. The defense is Master reading the absolute
  path in the M6 alert and declining a malicious target. **No code closes this — it is the designed
  trust boundary.** The plan hardens the alert (M6) so the target is unmissable; a future tier could
  add a server-side allowlist/denylist of quarantine-eligible paths (e.g. never Shadow's own
  code/DB), but that is out of scope here and booked as a follow-on, not a blocker.

---

## 3. The build — move by move

Ordering rationale: the **secret boundary (M7) and the funnel gate (M4-B) are built and
proven-closed BEFORE the approval channel that opens them (M5/M6)**. Security before
autonomy is the column: the lock is proven to hold shut before the key is minted.

### M1 — Cerberus-process pending-ACTION store (planner-invisible) — the credential-delivery fix

The red-team CRITICAL: the funnel's only input is the planner's `params`, so a credential
"delivered" to it would be planner-visible. **The store therefore holds the full pending
ACTION, not just a descriptor, and the poll loop re-invokes the action from the store — the
credential never rides `params`.**

**Build:** a `PendingApprovals` store owned by the Cerberus process (in-memory dict, backed by
a Cerberus-private file `data/cerberus_pending_approvals.json`, mode 0600, under no served
directory). Keyed by an **opaque public `approval_id`** (random, safe to show Master). Each
entry holds:
```
{
  approval_id:   <opaque public handle, surfaced to Master>,
  op:            "quarantine_file",
  resolved_params: <server-side params, target = realpath, NOT the planner's raw dict>,
  descriptor:    <M2 descriptor: op, absolute_target_path, args_sha256, nonce, not_after>,
  status:        "pending" | "approved" | "consumed",
  credential:    <HMAC minted by the poll loop on approval; None while pending>,
}
```
The store is **keyed and looked up by the opaque `approval_id`** — never by the descriptor
(pass-2 MEDIUM: descriptor-keyed lookup lets two planner calls collide into one approved entry).
`get(approval_id)` is the only lookup the mover uses. The `nonce` and `credential` live ONLY here.
Minting, approving, and consuming happen only inside Cerberus methods; **no `get_tools()` entry
returns store contents**, nothing is ever placed on a `decision_queue` item (S8's leak surface —
avoided by construction), and the `pending_approval` ToolResult returned to the planner carries
**only the opaque `approval_id`** — never the nonce, the credential, the descriptor's hash, or the
token. Each planner `handle` call mints a FRESH `approval_id` (optional display-dedupe among
`pending` entries only, never across `approved`/`consumed` — see M4 Step B1).

**Expected observation:** `grep -rn "class PendingApprovals" modules/cerberus/` finds the
store; `grep -rn "PendingApprovals\|_pending_approvals" modules/` shows it referenced ONLY
inside `modules/cerberus/` (never in `harbinger.py`, `orchestrator.py`, or any `get_tools()`
schema). Unit test `test_pending_store_not_in_any_tool_schema` iterates
`registry.list_tools()` and asserts no tool schema exposes a `nonce`/`credential`/`descriptor`
field; `test_pending_result_is_opaque` asserts the planner-facing ToolResult contains only
`approval_id` + a human message.

**Most likely failure:** the executor persists the store under a path some tool can read
(`data/research/quarantine/` or a decision-queue file). **Cause:** reusing a served directory.
**Counter:** store under the Cerberus-private path above and add it to the M7 secrets-glob deny
so even a path-taking tool aimed at it is denied. `test_store_path_denied_by_boundary` asserts
a path-taking tool aimed at `data/cerberus_pending_approvals.json` is DENIED by M7.

**Fork:** if recon finds an existing pending-store abstraction in Cerberus (reversibility /
creator_override), **trigger:** reuse it ONLY if it is not serialized by any routed tool AND it
can hold the resolved-params + credential slot; otherwise build fresh. Confirm with the M8
NEG-leak test either way.

### M2 — Canonical action descriptor computed at the funnel from ACTUAL params

**Build:** in `SecuritySurface._quarantine_file` (before the `shutil.move`), compute:
```
descriptor = {
  "op":                   "quarantine_file",            # enum, seeded w/ the one live op
  "absolute_target_path": os.path.realpath(source),     # symlink-resolved
  "args_sha256":          sha256(canonical(params)),    # canonicalized arg tuple
  "nonce":                token_urlsafe(32),             # Cerberus-minted, M1 store
  "not_after":            utcnow + SHORT_TTL,            # 10 min (see realpath re-pin below)
}
```
The descriptor is computed from the **realpath of the actual param**, never from any label
the planner supplied. (Correction from red-team pass 1: the tree DOES contain a
planner-supplied "approved" field — `_action_category` at
[cerberus.py:1015-1022](../../modules/cerberus/cerberus.py#L1015) short-circuits the *verdict*
to ALLOW. The funnel gate M4-B ignores it entirely: the funnel keys off the private store's
`status`, never off any verdict label or planner field. `test_action_category_does_not_move`
in M8 proves a planner-supplied `_action_category` does not move the file.)

**Realpath re-pin at move time (TOCTOU fix).** Because approval arrives asynchronously (a human
over Telegram, seconds-to-minutes later), the funnel re-resolves `os.path.realpath` at the
moment of the move and asserts it still equals `descriptor["absolute_target_path"]`. If the
target was swapped (symlink re-pointed, file replaced) during the wait, the paths differ and the
move is DENIED. `not_after` (TTL) is set to a human-appropriate window (**10 minutes**, not
120s) because staleness is now bounded by the realpath re-pin, not by a short TTL that would just
make honest approvals expire.

**Expected observation:** unit test `test_descriptor_uses_realpath` — pass a symlink
`data/link → /etc/hosts`; assert `descriptor["absolute_target_path"] == "/etc/hosts"`, not
the symlink path. `test_descriptor_nonce_server_minted` — assert the nonce is absent from
input params and present in the M1 store after computation.

**Most likely failure:** `realpath` resolved on a non-existent path returns the path
unchanged, letting a TOCTOU swap point elsewhere. **Cause:** `_quarantine_file` already
checks `source.exists()` ([core.py:559](../../modules/cerberus/security/core.py#L559)) but
realpath must be taken and then the SAME resolved path used for both the gate check and the
move (no re-resolution between check and move). **Counter:** resolve once, gate on the
resolved path, move the resolved path; assert `moved_path == descriptor.absolute_target_path`
in `test_no_toctou_between_gate_and_move`.

**Fork:** if `op` needs to cover a second live host-mutating tool discovered in R2/R3,
**trigger:** add that op to the enum and route its funnel through the same descriptor+verify
seam; do not create a parallel gate.

### M3 — `verify_approval(descriptor, credential) -> bool` (the swap seam)

**Build:** a single function (in a new `modules/cerberus/approval.py`) that the funnel calls.
Today's body:
```
def verify_approval(descriptor, credential) -> bool:
    # 1. nonce is pending, unexpired, unconsumed (M1 store lookup)
    # 2. credential is a valid HMAC-SHA256 over canonical(descriptor),
    #    key = CREATOR_AUTH_TOKEN (from singleton, never returned/logged/prompted)
    # 3. on success ONLY: atomically mark nonce consumed
    # returns True iff all hold
```
`hmac.compare_digest` for the MAC check (constant-time). The key is read from the singleton
at call time, never stored on `self` in a way a `__repr__`/`model_dump` would surface, never
interpolated into any string that reaches model context or a log line.

**Expected observation:** `test_verify_approval_valid` (valid MAC + pending nonce → True);
`test_verify_approval_wrong_key` (MAC with wrong key → False); `test_verify_approval_marks_consumed`
(after a True, the same nonce → False). `grep -rn "CREATOR_AUTH_TOKEN\|creator_auth_token"
modules/cerberus/approval.py` shows the key is read, never written to a log/return.

**Most likely failure:** the executor logs the descriptor+credential at DEBUG, leaking the
MAC or enabling replay reconstruction. **Cause:** reflexive "log everything" from CLAUDE.md.
**Counter:** log the *decision* (`approval_granted=True/False`, nonce prefix only), never the
credential or the key; `test_no_credential_in_logs` captures logs during a verify and asserts
neither the token nor the full credential appears.

**Fork (the swap seam):** **trigger** = Master later wants off-box authority → the ONLY change
is repointing this function's body at Ed25519 `verify(pubkey, sig, canonical(descriptor))`.
The funnel, descriptor, store, and tests are unchanged. Documented here so the executor does
NOT scatter auth logic into the funnel.

### M4 — The funnel is the SOLE load-bearing gate (enqueue-defer-on-first-arrival)

Red-team pass 1 proved the verdict path CANNOT be relied on: the pre-hook is pattern-only and
never reads the config lists ([cerberus.py:1224-1268](../../modules/cerberus/cerberus.py#L1224));
the plan-gate is a documented log-only stub in the live graph
([plan_node.py:47](../../modules/shadow/graph/plan_node.py#L47),
[cerberus_subgraph.py:37-44](../../modules/shadow/graph/cerberus_subgraph.py#L37)); and
`_action_category` short-circuits the verdict to ALLOW. **So the gate lives entirely at the
funnel, below every dispatch fork (sync, async, task_chain, graph nodes all converge on
`SecuritySurface.handle`). No verdict layer is trusted.**

**The pass-2 CRITICAL:** re-invoking the shared `SecuritySurface.handle` to perform the approved
move routed the authorized action back through the same door the planner dispatches to. Because
`handle` is caller-blind and the authorization was "does an `approved` store entry matching my
descriptor exist?", a planner re-issuing the same call could ride a genuine approval. **Fix: the
planner-reachable funnel NEVER moves a file; the move is a separate poll-loop-private capability
keyed on the opaque `approval_id`.** Two methods, one door each.

**Step B1 — `_quarantine_file` (the planner-reachable funnel via `handle`) ONLY ever enqueues. It
never moves a file, for any params, at any store state.** Replace its body (before the `shutil.move`
at [core.py:571](../../modules/cerberus/security/core.py#L571)) with:
```
def _quarantine_file(params):                        # reached by ANY caller via handle()
    descriptor = compute_descriptor(params)          # M2: realpath, args_sha256
    resolved_params = {"file_path": descriptor.absolute_target_path, "reason": ...}
    approval_id = pending_store.mint(descriptor, resolved_params)   # FRESH id + nonce, every call
    harbinger_surface(approval_id, descriptor)       # M6: alert Master, opaque id + ABS path
    return ToolResult(success=False, content={"approval_id": approval_id},
                      error="pending_approval")       # planner sees ONLY the opaque id
    # NO approved-branch here. This method has exactly one outcome: enqueue + pending.
```
There is **no path from `handle`/`_quarantine_file` to `shutil.move`.** A planner call — first,
tenth, during the approval window, whenever — returns `pending_approval` and nothing else. This is
the structural fix: the door the attacker uses cannot move a file.

(Optional display-dedupe, non-security: to avoid spamming Master when a planner re-issues an
identical still-`pending` request, the mint MAY return the existing id of a `pending` entry with the
same descriptor. It must NEVER return the id of an `approved`/`consumed` entry — those are done; a
re-issue mints fresh. The move authorization is keyed on `approval_id` regardless, so dedupe is a
notification nicety, not a gate.)

**Step B2 — `_execute_approved(approval_id)` is the ONLY mover, and it is poll-loop-private.** New
method, called **only** by the M5 poll loop's in-process Python reference:
```
def _execute_approved(approval_id):                  # NOT routable — see invariants below
    entry = pending_store.get(approval_id)           # keyed on the OPAQUE id, not the descriptor
    if entry is None or entry.status != "approved":  return  # nothing to do
    if utcnow() > entry.descriptor.not_after:        pending_store.expire(entry); return
    src = entry.descriptor.absolute_target_path
    if os.path.realpath(src) != src:                 return  # TOCTOU re-pin against STORED path
    if not verify_approval(entry.descriptor, entry.credential):  return  # M3 swap seam
    pending_store.consume(entry)                     # atomic: single-use, before the move
    shutil.move(src, dest_from(src))                 # the ONE host write, now authorized
```
**Invariants the executor MUST hold (each has a test):**
- `_execute_approved` is **not** in the `handle` dispatch map ([core.py:168-193](../../modules/cerberus/security/core.py#L168)), **not** in `SECURITY_TOOLS` ([core.py:57-83](../../modules/cerberus/security/core.py#L57)), **not** in any `get_tools()` schema. The planner has no routable name that reaches it.
- Its only argument is the server-minted opaque `approval_id`; it looks the entry up by that id, never by a planner-supplied descriptor. No collision, no confused deputy.
- Its only caller is the poll loop (M5). There is no race with the planner because the planner has no path to this method.

**Step A (optional, advisory only) — verdict surfacing, correctly wired or omitted.** Adding
`quarantine_file` to `approval_required_tools`/`never_autonomous`
([cerberus_limits.yaml:183,194](../../config/cerberus_limits.yaml#L183)) makes the *plan-gate*
verdict read `APPROVAL_REQUIRED`, useful for a user-facing "this needs approval" message. **It is
NOT a gate** (red-team HIGH #1/#2: pre-hook can't read those lists, graph plan-gate is a stub). If
the executor wants it, add a **real `hooks.pre_tool` rule** keyed to `quarantine_file` — but Step
B1/B2 is the enforcement. **Do not present Step A as the lock.**

**Target selection is a human-in-the-loop limit, stated plainly (red-team HIGH #3).** The planner
picks WHICH file is proposed for quarantine (`resolved_params` is `realpath` of the planner's
`file_path` — the server resolves symlinks, it does not choose the target). The channel
authenticates *the approver* and *binds the exact target to the approval via `approval_id`* — it
does NOT vouch that the target is safe. **The sole defense against a malicious planner-chosen target
is Master reading the absolute path in the Telegram alert and declining.** Therefore M6's alert MUST
show the absolute realpath prominently and unmissably (not a basename, not a truncated path). This
is the designed trust boundary, not a bug — but it must be explicit so the executor hardens the
alert. Residual R6 books it.

**Expected observation:**
- `test_handle_never_moves` — for a REAL existing tmpfile, call `handle("quarantine_file", ...)`
  under every store state (no entry / pending entry / an entry someone set to `approved`); assert
  the file is **never** moved by the `handle` call and every result is `pending_approval`.
- `test_execute_approved_not_routable` — assert `_execute_approved` (and any name for it) is absent
  from the `handle` dispatch map, `SECURITY_TOOLS`, and `registry.list_tools()`.
- `test_execute_approved_moves_once` — the poll loop's call path: set an entry `approved` with a
  valid credential, call `_execute_approved(approval_id)`; assert the file moves exactly once and a
  second call no-ops (`consumed`).
- `test_planner_cannot_ride_approved_entry` — the pass-2 attack, now a NEG: with entry A `approved`,
  a planner `handle("quarantine_file", {file_path: A's target})` mints a NEW pending entry and does
  **not** move A's file. (This replaces the old `test_approved_entry_moves_once`, which exercised the
  attack path and asserted success.)
- `test_approval_id_binds_target` — approving `approval_id=A` moves only A's stored target even if a
  different pending entry B names another file.

**Most likely failure:** the executor keeps the old "re-invoke `handle`" shortcut from the pass-1
draft, so the move is still reachable through the planner's door. **Cause:** convenience — `handle`
already dispatches `quarantine_file`. **Counter:** M5 calls `_execute_approved(approval_id)`
directly; `test_planner_cannot_ride_approved_entry` is RED if any `handle` path moves an approved
entry's file. That test is the guard against re-relocating the pass-2 hole.

**Abort trigger:** if R3 finds a planner-reachable host mutation that does NOT pass through
`SecuritySurface.handle`, **stop and flag** (abort #1). **And: if the authorized move cannot be made
reachable ONLY by the poll loop (i.e. it must re-enter the planner-facing `handle`), stop and flag
(abort #9)** — that is the pass-2 CRITICAL and must not be shipped.

### M5 — Cerberus-side inbound Telegram poll loop (identity bound at ingress)

**Build:** a Cerberus-owned component (`modules/cerberus/approval_channel.py`) that runs a
`getUpdates` long-poll against the Telegram Bot API in a Cerberus-managed thread/task (mirror
the `HeartbeatWriter` thread pattern at [watchdog.py:55-101](../../modules/cerberus/watchdog.py#L55)).
On each inbound message:
1. **Bind identity at ingress:** read the Telegram `message.chat.id` from the *transport
   payload*, compare against the configured `TELEGRAM_CHAT_ID` (from R4's source). Messages
   from any other chat_id are dropped and logged — identity is the transport fact, never a
   planned param.
2. Parse the reply against a *pending* entry (match by the opaque `approval_id` from M6, never
   the nonce).
3. On an approving reply from Master's chat_id: **entirely in-process**, look up the entry by the
   `approval_id` in Master's reply, mint the HMAC credential over the stored descriptor using
   `CREATOR_AUTH_TOKEN`, write it into the entry, set `entry.status = "approved"`, then call the
   **poll-loop-private mover directly**: `self._security._execute_approved(approval_id)` (Step B2) —
   **NOT** `SecuritySurface.handle(...)`. `_execute_approved` re-pins realpath against the stored
   path, calls `verify_approval`, consumes the nonce, and moves the file. **The move is keyed on the
   opaque `approval_id`, reachable only from this poll loop; the credential and target both come from
   the Cerberus-private store; neither is ever on the planner's `params` dict, in any tool result, or
   reachable through the routable `handle` surface.**

**This loop runs in Cerberus, not in planner-authored code** — the spec calls this load-bearing
and so does this plan. The planner has **no Telegram send capability** (Telegram send is
Harbinger's `notification_send`, which is `never_autonomous`
[cerberus_limits.yaml:196](../../config/cerberus_limits.yaml#L196)) and **no read access to the
poll loop's state or the store**.

**Expected observation:**
- `test_poll_loop_binds_chat_id` — feed a synthetic `getUpdates` payload with a WRONG chat_id
  carrying "approve <id>"; assert `entry.status` stays `pending`, no credential is minted, the file
  does not move.
- `test_approval_mints_and_moves_once` — feed the CORRECT chat_id + "approve <approval-id>"; assert
  the credential is minted into the store, `_execute_approved(approval_id)` moves the file exactly
  once, and a duplicate reply moves nothing (nonce consumed). **This is the mint→use test pass-1 said
  was missing** (HIGH #3): it exercises the whole outbound half through the private mover, not
  through `handle`.
- `grep -rn "getUpdates" modules/cerberus/` finds the loop; `grep -rn "getUpdates\|ApprovalChannel"
  modules/shadow/ modules/omen/ modules/reaper/ modules/harbinger/` returns nothing (Cerberus-only,
  not planner-reachable).

**Most likely failure:** the poll loop trusts a `chat_id` field inside the message *text* rather
than the transport `message.chat.id`. **Cause:** the exact regression the spec warns about.
**Counter:** `test_chat_id_from_transport_not_text` — a message whose *body text* claims
`chat_id=<master>` but whose transport `update["message"]["chat"]["id"]` is an attacker's → dropped.

**Fork:** if R4 shows the bot token is not reachable from Cerberus, **trigger:** wire it via main.py
into the Cerberus config (single source = `_shadow_config.harbinger.telegram_bot_token`/`.telegram_chat_id`),
do NOT create a duplicate secret key and do NOT read `.env` directly from the loop (that would itself
trip M7's boundary).

**Fail-loud, never fail-to-hang (red-team HIGH #3 note).** If the bot token / chat_id is absent when
Cerberus starts, the poll loop must NOT start silently and leave approvals hanging forever. It logs an
ERROR-level `APPROVAL CHANNEL UNAVAILABLE` line at boot (mirroring the ethical-topics fail-loud
pattern in [cerberus.py:199-216](../../modules/cerberus/cerberus.py#L199)) and any pending
`quarantine_file` returns `approval_channel_down` — a fail-CLOSED state (the move never happens), not
a fail-open one. `test_no_channel_fails_closed` asserts a pending action with no channel returns
`approval_channel_down` and does not move the file.

**Abort trigger:** if the only feasible way to receive replies is to route them through an
LLM-planned tool (i.e. the poll loop cannot be made Cerberus-private), **stop and flag** — that is
the design-gutting regression; escalate rather than ship a planner-drivable approval intake.

### M6 — Harbinger outbound surfacing of the pending descriptor (transport, not authority)

**Build:** when a `quarantine_file` action stops at `pending_approval`, Cerberus asks Harbinger to
send Master a Telegram alert (`send_alert`, [telegram.py:95](../../modules/harbinger/telegram.py#L95))
containing the human-readable descriptor (op, absolute target path, a short opaque approval-id, TTL)
— **never the nonce, never the credential, never the token.** Master replies "approve <approval-id>"
(handled by M5).

**The absolute target path is the load-bearing content (R6 — pass-2 HIGH #3).** Because the planner
selects WHICH file is proposed, the ONLY defense against a malicious target is Master reading the
path and declining. The alert MUST show the full absolute realpath prominently and unabbreviated —
no basename-only, no truncation, no ellipsis — so a proposed `…/data/memory/shadow_memory.db` or
`…/main.py` is unmissable. A one-line "op + full path + approval-id" is the required minimum.

**Alert-text integrity — the planner controls the `reason` free-text (pass-3 HIGH).** `reason` comes
from planner params ([core.py:550](../../modules/cerberus/security/core.py#L550)) and Telegram renders
`parse_mode:"HTML"` ([telegram.py:64](../../modules/harbinger/telegram.py#L64)). So the approval alert
MUST:
1. **Compute the authorization line server-side and escape everything.** The op + absolute realpath +
   `approval_id` line is built by Cerberus from the descriptor (not from `reason`), and any
   planner-supplied text is `html.escape`-d before it enters the message.
2. **Isolate planner free-text.** Render `reason` in a clearly-labeled, escaped "planner says:"
   section that is visually separate from the server-computed authorization line — so a planner cannot
   forge a second fake path or a fake "approve XYZ" instruction into the part Master trusts.
3. **Resist steering by competing messages.** A planner can emit `notification_send` to the same chat
   (its `never_autonomous` verdict is inert per S3). The approval alert must be self-identifying
   (a fixed Cerberus-signed prefix + the `approval_id`) so Master approves by matching the id in the
   alert he trusts, not by proximity/timing. Note this competing-message surface as residual R7 and
   flag `notification_send`'s inert gate to the follow-on host-write mission.

**Expected observation:** `test_surface_omits_nonce` — assert the payload contains the approval-id and
the FULL absolute path and does NOT contain the nonce/credential/token. `test_surface_shows_full_path`
— assert the exact absolute realpath appears verbatim. `test_surface_escapes_planner_reason` — pass a
`reason` containing HTML/`<b>`/a fake path/`approve OTHERID`; assert it is escaped and confined to the
"planner says:" section, and the server authorization line is untouched. The nonce never leaves the
Cerberus process.

**Most likely failure:** the executor includes the nonce in the message "so Master can confirm it,"
re-creating S8's leak on a new channel. **Cause:** conflating the opaque approval-id (safe to show)
with the nonce (must stay secret). **Counter:** the approval-id is a separate random public handle;
the nonce is the secret consumed by `verify_approval`. `test_surface_omits_nonce` is the guard.

### M7 — AR-P1-2: secret-unreachability boundary (the prerequisite that makes local-token sound)

**Build three parts:**

**Part A — path-deny at the tool boundary.** Every tool that takes a filesystem path resolves the
arg to `os.path.realpath` and passes through a Cerberus/Sentinel check that **denies** the resolved
path if it is the repo-root `.env` or matches a secrets glob (`**/.env`, `**/.env.*`, `**/.ssh/**`,
`**/.aws/credentials`, `**/*_token*`, the M1 pending-store file, `config/ethical_topics.yaml` if
scoped) **before the tool body executes.** This is a pre-execution check in the dispatch path (the
pre-hook is the natural home: [orchestrator.py:5289-5305](../../modules/shadow/orchestrator.py#L5289)),
returning `DENY` for a path-taking tool aimed at a secret.

**Part B — registry enumerator, not a hand-list.** Derive the set of path-taking tools by inspecting
`registry.list_tools()` ([base.py:432](../../modules/base.py#L432)) — a tool is "path-taking" if its
schema declares a path-ish param (`file_path`, `path`, `source`, `target`, `config_path`, …, matched
by a documented name set). So a tool added six weeks from now is automatically in scope. **Expected
observation:** `test_enumerator_covers_new_tool` — register a synthetic tool with a `file_path` param;
assert the enumerator includes it without a code edit.

**Part C — canary test.** Stand up the real tool surface (real registry, real modules ONLINE), point
every enumerated path-taking tool at the repo-root `.env`, assert each returns DENY and no tool reads
or returns `.env` contents. **Expected observation:** `test_secret_reach_canary` iterates the
enumerated set and asserts DENY for each; a deliberately-added "leaky" test tool that tries to open
`.env` is caught (the canary catches the canary).

**Most likely failure:** the deny check runs on the *raw* param, so `data/../.env` or a symlink
`data/x → .env` slips past. **Cause:** checking the string, not the realpath. **Counter:** resolve
`realpath` FIRST, then match — same discipline as M2. `test_canary_symlink` and `test_canary_dotdot`
assert both traversal forms are denied.

**Abort trigger:** if a path-taking tool cannot be routed through the pre-execution check (e.g. a
tool that opens files internally without surfacing the path to the dispatch layer), **stop and flag**
— that tool is a hole in the boundary, and AR-P1-2 is not canary-green until it is closed. Per the
spec's abliteration gate, the Heretic run does not proceed while a hole is open.

### M8 — Behavioral verification suite (positive + negative, fails on current broken behavior)

Each assertion certifies **behavior at the live `shutil.move`**, never a trust field's self-report.
Build a new `tests/test_auth_approval_channel.py`:

- **NEG(spoof) — the must-fail-today control.** Planner sets `params={"file_path": <REAL existing
  tmpfile>, "source": "approved"}` (or any self-labeled approval field) and calls the funnel with no
  genuine credential. **The tmpfile MUST exist** — else `_quarantine_file`'s `source.exists()` guard
  ([core.py:559](../../modules/cerberus/security/core.py#L559)) returns failure for the wrong reason
  and the test is vacuously red (red-team LOW). **Assert the tmpfile is still at its original path
  AND the failure reason is `pending_approval`** (not `File not found`). *Before M4-B this test is
  RED because the move runs* (S2) — it goes GREEN only when M4-B lands. That red→green transition is
  the proof the fix is real, not vacuous.
- **NEG(planner credential) — the CRITICAL guard.** Planner sets `params={"file_path": <real
  tmpfile>, "_approval_credential": <any forged value>, "_action_category": <any authorized label>}`.
  **Assert the file does NOT move** — the funnel reads no credential and no verdict label from
  `params`; it enqueues and returns `pending_approval`. This is the direct guard against the red-team
  CRITICAL (credential-on-params) and the `_action_category` MEDIUM.
- **NEG(action_category).** `test_action_category_does_not_move` — a planner-supplied
  `_action_category` that would make `_safety_check` return ALLOW ([cerberus.py:1015](../../modules/cerberus/cerberus.py#L1015))
  still does not move the file, because the funnel gate is independent of the verdict.
- **NEG(handle never moves) — the pass-2 CRITICAL guard.** `test_handle_never_moves` — for a real
  tmpfile, call `handle("quarantine_file", ...)` under every store state (no entry / a `pending`
  entry / an entry force-set to `approved` with a valid credential). **Assert the file is NEVER moved
  by any `handle` call** and every result is `pending_approval`. The move is unreachable through the
  routable door.
- **NEG(planner rides approval) — the pass-2 confused-deputy guard.** `test_planner_cannot_ride_approved_entry`
  — with entry A `approved`, a planner `handle("quarantine_file", {file_path: A's target})` mints a
  NEW pending entry and does **not** move A's file.
- **NEG(execute_approved not routable).** `test_execute_approved_not_routable` — assert the mover is
  absent from the `handle` dispatch map, `SECURITY_TOOLS`, and `registry.list_tools()`.
- **NEG(cross-action replay).** Mint a valid credential for descriptor A (target = file A). Replay it
  against descriptor B (target = file B). **Assert file B is not moved** — the credential is bound to
  A's `absolute_target_path` + `args_sha256`, so the MAC fails for B.
- **NEG(nonce reuse).** Consume a valid approval once (POS), then replay the same nonce+credential.
  **Assert the second attempt does not move the file** — nonce marked consumed atomically (M3 step 3).
- **NEG(secret reach) — AR-P1-2 canary.** Every enumerated path-taking tool aimed at `.env` → DENY
  (M7 Part C). Asserts no tool returns `.env` bytes.
- **NEG(nonce-leak).** Call every autonomous/routed read tool (`decision_queue_read`, any `*_read`,
  `memory_search`) while an approval is pending; **assert the nonce string appears in none of their
  results** (guards S8 by construction).
- **POS.** Simulate a valid Telegram approval from Master's `chat_id` over the real descriptor →
  the poll loop mints the credential into the store and calls `_execute_approved(approval_id)` → the
  file moves **exactly once**; a second identical reply does nothing (nonce consumed).
- **POS(target binding).** `test_approval_id_binds_target` — with two pending entries A and B naming
  different files, approving A moves ONLY A's target, never B's.
- **NEG(target swap / TOCTOU).** Enqueue a quarantine of a real tmpfile; between enqueue and approval,
  re-point the target (symlink swap or replace the file) so `realpath` differs; approve. **Assert the
  file does NOT move** (`_execute_approved` re-pin returns without moving).
- **NEG(no channel).** With the Telegram token absent, a pending quarantine returns
  `approval_channel_down` and the file does not move (fail-closed, not fail-to-hang).

**Expected observation:** all pass AFTER the build; NEG(spoof) is demonstrably RED before M4 (the
executor runs it once pre-fix to confirm the must-fail control actually fails today — if it passes
pre-fix, the test is vacuous and must be rewritten to actually drive the funnel). `test_handle_never_moves`
and `test_planner_cannot_ride_approved_entry` are the two that must be GREEN to certify the pass-2
hole is closed — if either goes red, a `handle` path can still move an approved entry's file.

**Most likely failure:** a NEG test asserts on the ToolResult's `error`/`success` field instead of the
filesystem state, so a bug that returns "denied" while still moving the file passes green. **Cause:**
tag-checking instead of behavior-checking. **Counter:** every NEG asserts `os.path.exists(original)`
and `not os.path.exists(dest)` — the file's actual location is the certifier.

---

## 4. Abort conditions (stop and flag — do not improvise)

1. **A second ungated funnel (R3) — ALREADY FIRED (pass-3).** Any planner-reachable host mutation that
   does not pass through `SecuritySurface.handle` → this funnel's gate does not cover it. **Pass-3
   verified `code_edit` and `sandbox_to_production` are exactly this** — they are documented in the
   SCOPE BOUNDARY section and belong to the follow-on host-write mission, NOT this funnel. The R3 sweep
   at build must confirm no *additional* routed host-write exists beyond that known set; any new one is
   a fresh stop-and-flag added to SCOPE BOUNDARY. This mission does not proceed as if its funnel makes
   the host-write surface safe — it does not.
2. **The poll loop cannot be made Cerberus-private (M5 abort).** If replies can only arrive via an
   LLM-planned tool, the approval intake is planner-drivable — the exact design-gutting regression.
   Escalate to Master/Opus; do not ship.
3. **`CREATOR_AUTH_TOKEN` does not load into the singleton (R1 fails).** Do NOT hardcode, default, or
   swallow the RuntimeError to "degrade." A missing key means no approval is possible — that is the
   correct fail-closed state; fix the config wiring or flag BLOCKED.
4. **NEG(spoof) passes BEFORE the fix.** The must-fail-today control is vacuous — the test isn't
   actually driving the live move. Rewrite the test before trusting any green.
5. **A path-taking tool cannot be routed through the M7 pre-execution check.** The secret boundary has
   a hole; AR-P1-2 is not canary-green; the abliteration gate stays shut.
6. **The nonce appears in any routed-tool result (M8 NEG-leak RED).** The store leaked; stop and
   re-privatize before proceeding — a readable nonce is a replayable approval.
7. **The credential cannot reach the funnel without touching `params` (red-team CRITICAL).** If the
   enqueue-defer-then-poll-loop-re-invoke design of M1/M4-B/M5 cannot be built — i.e. the only way to
   get a credential to `_quarantine_file` is through the planner's `params` dict — **STOP and flag.** A
   planner-visible credential field defeats the entire design and enables replay. Do NOT ship a
   `params.get("_approval_credential")` shortcut.
8. **The approval channel would fail-open or fail-to-hang.** If an absent token or a down poll loop
   would let a pending action proceed (fail-open) OR silently hang with no operator signal
   (fail-to-hang), **stop and flag.** The correct state is fail-CLOSED with a loud
   `APPROVAL CHANNEL UNAVAILABLE` ERROR log.
9. **The authorized move is reachable by any caller other than the poll loop (red-team pass-2
   CRITICAL).** If the `shutil.move` for an approved entry can be triggered through the routable
   `SecuritySurface.handle(tool_name, params)` — i.e. the move's authorization is a property of store
   state that any caller can name, rather than a capability only the poll loop holds via
   `_execute_approved(approval_id)` — **STOP and flag.** Re-entering the shared funnel to perform the
   move makes the planner a confused deputy for the approval. The planner's `handle` path must ALWAYS
   return `pending_approval`, never move a file, regardless of store state.

---

## 5. Verification runs (what the executor runs, when, and what PASS looks like)

Run in the venv (`source ~/dev/Shadow/shadow_env/bin/activate`), targeted per CLAUDE.md
(no full suite):

- **V0 — pre-build baseline (before M4-B).** Run `tests/test_auth_approval_channel.py::test_neg_spoof`.
  **PASS = it FAILS** (RED), proving the funnel is ungated today. If it passes, abort #4.
- **V1 — funnel gate (after M2–M4).** `python -m pytest tests/test_auth_approval_channel.py -v` for the
  descriptor, `verify_approval`, and funnel-defer tests. **PASS =** NEG(spoof), NEG(planner
  credential), NEG(action_category), NEG(handle never moves), NEG(planner rides approval),
  NEG(execute_approved not routable), cross-action replay, nonce-reuse, target-swap, POS(target
  binding) all green; the file stays put under every NEG (filesystem-state assertion, not an
  error-tag check). **`test_handle_never_moves` + `test_planner_cannot_ride_approved_entry` green is
  the certification that the pass-2 confused-deputy hole is closed.**
- **V2 — secret boundary canary (after M7).** `test_secret_reach_canary`, `test_canary_symlink`,
  `test_canary_dotdot`, `test_enumerator_covers_new_tool`. **PASS =** every enumerated path-taking tool
  DENIES `.env` including via symlink and `..`; the synthetic new tool is auto-covered.
- **V3 — approval channel identity + mint→use (after M5–M6).** `test_poll_loop_binds_chat_id`,
  `test_chat_id_from_transport_not_text`, `test_approval_mints_and_moves_once`,
  `test_no_channel_fails_closed`, `test_surface_omits_nonce`. **PASS =** wrong chat_id never mints a
  credential; identity comes from transport; a correct approval mints-and-moves exactly once; an
  absent channel fails closed; the nonce never leaves the Cerberus process.
- **V4 — full behavioral certifier.** Whole `tests/test_auth_approval_channel.py` + the Cerberus suite
  `python -m pytest tests/test_cerberus.py -v`. **PASS =** all six M8 assertions green AND
  test_cerberus.py shows no regression (the funnel change didn't break the 24-tool surface).
- **V5 — live smoke (Master-in-the-loop, manual).** With Shadow running, plan a quarantine of a
  disposable file; confirm it stops pending, a Telegram alert arrives, and the file moves **only** after
  Master replies "approve <id>" from his own chat, exactly once. **PASS =** file moves once, post-approval,
  never before.

**Built is not done. V0 red → V1–V4 green → V5 live-once = done.**

---

## 6. Gates & Autonomy Ledger

Every move that writes to Shadow's code/config, acts autonomously, or touches the host/network/an
external account, with its gate and earned-by condition.

| # | Move | What goes wrong ungated | Gate | Earned-by (must be true before the gate opens) |
|---|---|---|---|---|
| G1 | **The `shutil.move` (host write).** | An unauthenticated planner quarantines/moves any file (S2: today it does); a planner rides a genuine approval (pass-2). | The planner-facing funnel (`handle`→`_quarantine_file`) ONLY enqueues, never moves. The move is `_execute_approved(approval_id)` — poll-loop-private, not routable, keyed on the opaque id — which re-pins realpath, verifies the credential, and consumes the nonce. | Store entry `approved` (set only by the chat_id-bound poll loop); the move triggered only by `_execute_approved` via the poll loop's in-process reference (not reachable from `handle`); credential a valid HMAC over the exact descriptor (M3) keyed by `CREATOR_AUTH_TOKEN` (R1 loaded); nonce unconsumed; realpath still matches the bound target; **Master read the absolute path in the alert and approved that specific `approval_id`** (target legitimacy is the human's call — R6). |
| G2 | **M5 — the inbound Telegram poll loop (autonomous network intake that can mint a credential).** | A planner-drivable or spoofable intake self-authorizes an action. | Loop runs Cerberus-private (not a routed tool); identity read from transport `message.chat.id`, matched to `TELEGRAM_CHAT_ID`; planner has no Telegram-send and no loop-state read. | `test_poll_loop_binds_chat_id` + `test_chat_id_from_transport_not_text` green; `grep` proves the loop is referenced only in `modules/cerberus/`. |
| G3 | **M4-A — OPTIONAL advisory config/verdict edits.** | Presenting these as the gate is the "looks governed but isn't" trap: the pre-hook can't read the lists (red-team HIGH #1) and the graph plan-gate is a stub (HIGH #2). | These are advisory ONLY; the enforcement is G1's funnel. If added, a real `hooks.pre_tool` rule must back them, and Master reviews the diff. | Enforcement proven at the funnel (G1), NOT at the verdict; `test_cerberus.py` green; NEG(spoof) red→green observed. |
| G4 | **M7-A — path-deny boundary edits the dispatch path (code write, affects EVERY tool).** | A bug here could deny legitimate file tools (over-block) or miss a traversal (under-block, `.env` leaks). | The check is realpath-first and canary-tested against `.env` via symlink and `..`; enumerator derives scope from the live registry. | V2 green including `test_canary_symlink`/`test_canary_dotdot`; no legitimate path tool regresses (spot-check a known-good `code_read` of a repo file still succeeds). |
| G5 | **The credential/nonce/token themselves (secret handling).** | Leaking any into model context or logs enables replay or key theft. | `verify_approval` never returns/logs the credential or key; M6 surfacing omits the nonce; M1 store is planner-invisible. | `test_no_credential_in_logs`, `test_surface_omits_nonce`, M8 NEG-leak all green. |
| G6 | **The whole gated-host-action capability going live (autonomy earned).** | Opening quarantine-move autonomy before the boundary is real re-creates the exact exposure the spec pressure-tested. | The gate opens for host actions ONLY after M4-B + M7 are canary-green. | **Abliteration-gate contribution (spec):** AR-P1-2 (M7) canary-green is a HARD precondition — if the boundary isn't built and green, the local-token authority is the exposure, so it gates the Heretic run; it does not float. |
| G7 | **The WHOLE host-write surface, not just this funnel (pass-3 CRITICAL).** | `code_edit`/`sandbox_to_production` (and the R3 set) mutate the host — including the gate's own source — unauthenticated, bypassing this funnel; "approval channel green" would falsely read as "host safe." | Every routed host-write tool routed through the descriptor + `verify_approval` seam OR independently gated (the follow-on mission; overlaps `omen-part3-selfmod.md`). | The Heretic run's host-write precondition is the WHOLE surface gated (this funnel + `code_edit` + `sandbox_to_production` + R3), NOT this funnel alone. This mission does not earn that condition by itself; it earns only its own funnel. |

**Capability planned in full, gated:** the seam supports the full intended power — quarantine now,
and `firewall_apply`/`software_install`/`av_scan` the moment their host-mutating bodies exist (they
snap into the same descriptor + `verify_approval` gate via M2's extensible enum). Nothing is
amputated; every dangerous edge arrives wearing G1–G7. The off-box Ed25519 upgrade is a one-function
repoint (M3 swap seam), not a rewrite — the gate's strength can grow without the funnel changing.

**Security before autonomy is the column, not a later phase:** M7 (the boundary) and M4-B (the funnel
lock) are built and proven-closed BEFORE M5/M6 (the approval channel that opens them). The lock holds
shut before the key is minted.

---

## 7. Split justification

**Not split.** AR-P1-1 (authority) and AR-P1-2 (secret boundary) are one mission because the spec's
fork *requires* both together: the local-token authority is sound **iff** the planner provably cannot
reach the token, and only AR-P1-2 makes that provable. Splitting would sever the dependency the entire
design rests on — a plan for AR-P1-1 alone would ship an on-box secret with no mechanism proving it
unreachable (the exact exposure the prior wargame flagged). One funnel, one gate, one boundary, one
plan.
