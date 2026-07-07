# Red Team — Sentinel Part 1 Posture, Pass 3

**Target:** `wargames/plans/sentinel-part1-posture.md` (twice-patched)
**Scope (as briefed):** ONLY the pass-2 patches to (a) the APPROVAL AUTHORITY
(F5-0b: secret token + ingress-bound source + single-use nonce) and (b) the
non-security host-tool path (F5-0 step-1). The step-2 security-surface gate
was confirmed solid in pass 2 and is NOT re-litigated here.
**Method:** READ-ONLY. Every claim traced to file:line in the live tree.
**Verdict:** **CRITICAL landed.** F5-0b's "authoritatively-bound source at ingress"
is an ingress-binding that **does not exist in the code** — it is the same
"named but not wired" failure the plan was patched to fix, moved up one layer.
The token requirement is real but, as written, either breaks the flow or is
inert; and the nonce leaks to the untrusted planner through `decision_queue_read`.

---

## CRITICAL — F5-0b's "source bound authoritatively at ingress" points at an ingress that stamps nothing and never reaches the resolver

### The plan line under attack

> F5-0b step 2 ([plan L180-181]): "The **`source` must be bound authoritatively
> by the harness/orchestrator at the ingress boundary (the same place Step-1.5
> stamps the input source), NOT read from tool params** — so a planned/injected
> `source` field is ignored."

> Pass-2 ledger P1 ([plan L692-695]): "binds `source` **authoritatively at ingress**
> (not from params)".

> G0 earned-by ([plan L614]): "an **authoritatively-bound source** (not a planned param)".

The plan's entire escape from P1 (the spoofable-source break) rests on the claim
that there is an ingress point — "the same place Step-1.5 stamps the input source" —
whose stamp survives, un-spoofable, all the way to `_decision_queue_resolve`.
**That place does not stamp anything, and even the value it holds never travels to
the resolver.** Traced:

**1. Step 1.5 does not stamp a source. It reads a plain function parameter.**
`process_input(self, user_input, source: str = "user")`
([orchestrator.py:1157](../../modules/shadow/orchestrator.py#L1157)). `source` is
a **caller-supplied argument with default `"user"`** — not derived from the
transport, not authenticated, not stamped. Step 1.5 merely *forwards* it:
`self._step1_5_injection_screen(user_input, source)`
([orchestrator.py:1187](../../modules/shadow/orchestrator.py#L1187)), and inside
that method `source` is only *read* and logged
([orchestrator.py:1960,1976,1996](../../modules/shadow/orchestrator.py#L1960)).
There is no assignment `source = <trusted transport identity>` anywhere. The plan's
anchor — "the same place Step-1.5 stamps the input source" — describes a stamp that
is not in the code. The real ingress (`main.py:726`) calls
`orchestrator.process_input(user_input)` **with no source argument at all**
([main.py:726](../../main.py#L726)), so the value is the literal default `"user"`
— exactly the string an injected instruction would want.

**2. Even that (weak) `source` value never reaches the resolver.**
`decision_queue_resolve` is a **routed tool** — registered in Harbinger's handler
map ([harbinger.py:131](../../modules/harbinger/harbinger.py#L131)) with schema
`{"decision_id": "str", "resolution": "str"}`
([harbinger.py:220-225](../../modules/harbinger/harbinger.py#L220)). It is reached
through the normal dispatch:
- Step-5 dispatch: `params = step.get("params", {})`
  ([orchestrator.py:5203](../../modules/shadow/orchestrator.py#L5203)) — the params
  are **LLM-planned** — then `await module.execute(tool_name, params)`
  ([orchestrator.py:5254](../../modules/shadow/orchestrator.py#L5254)).
- `Harbinger.execute(self, tool_name, params)`
  ([harbinger.py:113](../../modules/harbinger/harbinger.py#L113)) has **no `source`
  parameter** and passes `params` straight to the handler: `result = handler(params)`.
- `_decision_queue_resolve(self, params)`
  ([harbinger.py:604](../../modules/harbinger/harbinger.py#L604)) reads only
  `params.get("decision_id")` / `params.get("resolution")`.

The orchestrator's `source` local is **never merged into the params dict**. A grep
for `params[...] = source` in `_step5_execute` returns nothing; the async path is
the same story — `run_deferred_through_graph(task.description, source="autonomous")`
([async_tasks.py:245-246](../../modules/shadow/async_tasks.py#L245)) passes `source`
to the graph, not into tool params. **There is no wire from the (already weak)
ingress `source` to the resolver.** So F5-0b's step-2, if built as the plan
literally says ("bound at ingress, ignore the param"), has *no value to bind* — the
resolver would have to invent one, and the only `source` the LLM planner controls is
`params`, which is precisely what the plan forbids reading. The route asserts an
authoritative binding that has no carrier in any real call path.

**Consequence — the P1 break is NOT closed by the source-binding half.** An injected
Telegram/user instruction that gets the planner to emit
`decision_queue_resolve(decision_id=X, decision="approved")` reaches the resolver with
the *ambient* ingress source = `"user"` (the default). Nothing distinguishes it from a
genuine Master approval, because the harness never captured a trustworthy source and
never carried it here. The plan's "the param is ignored; the authoritative source is
bound elsewhere" is true only in that **the source is bound nowhere** — the resolver
sees neither the param nor an ingress stamp. This is the identical class of failure
("a lock named but not wired to the door it guards") that killed the first draft (B0)
and pass-2 P1 — the plan moved it from `params["source"]` up to a mythical ingress
stamp without verifying the stamp or its carrier exists.

### Why the token requirement does not save it (as written)

The plan's genuine safety comes from the **secret creator token** half, not the source
half (the plan even concedes this at L172, L692-694). But as routed, the token half is
either **flow-breaking or inert**, and cannot be silently assumed:

- **`CREATOR_AUTH_TOKEN` is not configured on Citadel.** It is absent from
  `config/.env` (grep: key not present), from `config/config.yaml`, and from
  `config/config.local.yaml`. The field defaults to `None`
  ([cerberus/config.py:46-53](../../modules/cerberus/config.py#L46)).
- `CreatorOverride.verify_hardware_auth` **raises `RuntimeError` when the token is
  unset** ([creator_override.py:105-110](../../modules/cerberus/creator_override.py#L105)) —
  it does not return False. So F5-0b's "reuse `verify_hardware_auth`" ([plan L178])
  means the FIRST real approval attempt **throws**, not "refuses cleanly." The plan's
  `test_approval_requires_token` would pass in CI only if the test sets a token — but
  the LIVE resolver on Citadel has none, so the approval path is **dead on arrival**:
  every `decision="approved"` raises. That either (a) breaks the entire gated-action
  flow (nothing Master approves can ever execute — F1-2 install, F1-4 firewall, F1-3
  quarantine all stall), or (b) invites the executor to wrap the RuntimeError and
  "degrade," which re-opens the gate. Neither is stated; the plan asserts the token is
  "reused" as if wired. This is a hard prerequisite the plan never books as BLOCKED-on-
  Master (unlike R2/R3/R5 which it does book).
- The remaining `CreatorOverride` guard the plan leans on — internal-module rejection
  via `_validate_source` — is *itself* fed `source` from a caller argument
  ([creator_override.py:113-125](../../modules/cerberus/creator_override.py#L113),
  default `source="user_input"` at
  [creator_override.py:137](../../modules/cerberus/creator_override.py#L137)). So
  reusing `CreatorOverride` inherits the **same** unbound-source problem: its source
  check is only as good as whoever passes `source`, and in the resolver call path no
  authoritative source is passed. The token is the only real barrier — and it's unset.

**Net:** the approval authority is protected by exactly one thing (the secret token),
that thing is unconfigured so the path raises, and the plan's *second* claimed
protection (ingress-bound source) is wired to nothing. Remove the token (its live
state) and an injected "approved" self-authorizes. That is a CRITICAL: an action can
reach execution authority without genuine Master authority the moment the token gap is
"handled" by anything other than a hard stop — and the plan gives no such stop.

---

## HIGH — the single-use nonce leaks to the untrusted planner via `decision_queue_read`, so it can be replayed

### The plan line under attack

> F5-0b step 3 ([plan L182-186]): "On `approved`, the resolver **mints a single-use
> nonce** and stores it on the item; the gated tool's host action runs ... ONLY when
> it presents THAT nonce, which is consumed on use."

> Second attack vector in brief: "Is there a path where the nonce leaks into
> LLM-visible context (e.g. the `decision_queue_read` tool returns the item including
> the nonce to the model)? If the model can read the nonce, it can replay it."

**Traced — yes, it leaks.** The nonce is stored "on the item" (`item[...] = nonce`).
`decision_queue_read` returns the **raw item dicts wholesale**:

```
items = sorted(self._pending_items | self._queue, key=...)   # harbinger.py:589-591
return ToolResult(success=True, content={"items": items, ...})  # harbinger.py:593-599
```
([harbinger.py:580-602](../../modules/harbinger/harbinger.py#L580)). There is **no
field redaction** — every key on the item, including any `nonce` the F5-0b resolver
minted, is serialized into `content.items[*]` and handed back to the caller.
`decision_queue_read` is itself a **routed, `autonomous`-permission tool**
([harbinger.py:214-218](../../modules/harbinger/harbinger.py#L214)) — the planner can
call it freely. And `_decision_queue_resolve` **returns the whole resolved item**
(`content=item`, [harbinger.py:648-653](../../modules/harbinger/harbinger.py#L648)),
so the nonce also flows straight back in the resolve tool's own result.

**Cross-process makes it worse, not better.** The nonce is persisted to disk by
`_save_queue` (`json.dump(data, ...)` at
[harbinger.py:1081-1091](../../modules/harbinger/harbinger.py#L1081)) and reloaded by
`_load_queue` ([harbinger.py:1064-1078](../../modules/harbinger/harbinger.py#L1064))
as plain JSON with no field filtering. So the deferred executor in another
turn/process *can* read it — the plan's Fork condition ([plan L201-204]) is satisfiable
— but so can any planner turn that calls `decision_queue_read`. The nonce travels to
the executor **and** to the model on the same unredacted channel. There is no
"executor-only" path in the code; items are one flat dict returned by an autonomous
read tool.

**Attack:** an injected instruction drives `decision_queue_read`, reads
`items[i].nonce` from the tool result now in LLM-visible context, then emits the gated
tool call presenting that nonce — a replay before or racing the legitimate consumption.
The plan's "consumed on use" defends against a *second* use, not against the planner
reading it and being the *first* to use it. The nonce, as routed through the existing
read/resolve surface, is not a secret from the party it must be secret from.

The plan does not name `decision_queue_read` as a nonce-exposure surface anywhere
(F5-0b, F5-2, and the G0 row are silent on read-side redaction), so this is an unhandled
leak, not a covered risk.

---

## MEDIUM (informational) — F5-0 step-1 for non-security host tools is a sound *route*, with one un-booked dependency

The brief asked whether step-1 for `software_install`/`firewall_apply` is "actually made
real" or "still leans on fixing two verdict handlers that might have other callers/paths."
Traced, and — crediting that this is a route, not code — the step-1 route is **sound in
shape**:

- The two verdict handlers the plan says it must fix are the only two live verdict sites,
  and both today ignore `APPROVAL_REQUIRED`:
  - Pre-hook handler branches only on `DENY`/`MODIFY`
    ([orchestrator.py:5211-5223](../../modules/shadow/orchestrator.py#L5211)); on
    `APPROVAL_REQUIRED` it falls through to `module.execute`
    ([orchestrator.py:5254](../../modules/shadow/orchestrator.py#L5254)).
  - Plan-gate handler logs `APPROVAL_REQUIRED` and proceeds
    ([orchestrator.py:4642-4651](../../modules/shadow/orchestrator.py#L4642)).
  The plan correctly targets BOTH ([plan L134-138]).
- **The one execution path that could bypass a fixed pre-hook is the async task queue**
  — and the recent Item-13 change closes it: the worker routes through
  `run_deferred_through_graph(..., source="autonomous")`
  ([async_tasks.py:241-247](../../modules/shadow/async_tasks.py#L241)) so the plan-gate
  applies; the direct `module.execute` branch only fires when `self._orchestrator is
  None` ([async_tasks.py:250-252](../../modules/shadow/async_tasks.py#L250)), i.e. a
  degraded/test config. The plan should note the graph-routing dependency (if a future
  change reverts Item-13, step-1 for non-security tools is bypassed on the async path),
  but as of the live tree the bypass the brief worried about is closed.

**However** — the step-1 route terminates at the SAME F5-0b approval mechanism whose
authority is broken above. A non-security tool correctly stops at `APPROVAL_REQUIRED`,
routes to F5-0b — and then the CRITICAL applies: an injected "approved" (token unset →
raises, or token-gap "handled" → self-approves) releases it. So step-1 is real as a
*chokepoint* but inherits the approval-authority CRITICAL as its release condition. It
does not independently execute an action without authority; it hands off to a broken
authority. Reported as MEDIUM because the leg itself is wired; the failure is downstream.

---

## What I attacked hardest and could NOT break

- **Step-2 security-surface gate (out of scope, spot-checked).** I re-walked the
  quarantine `shutil.move` funnel through [cerberus.py:484-490](../../modules/cerberus/cerberus.py#L484)
  and the async worker; it still funnels through the single `_security.handle` caller and
  the graph-routed deferred path. Pass-2's confirmation holds; I found nothing new and did
  not re-litigate it.
- **F5-0 step-1 chokepoint placement.** The two verdict handlers are the only live sites,
  and the async-bypass is closed by Item-13. The route is structurally correct; my only
  finding there is the downstream-authority inheritance (folded into the CRITICAL) and the
  un-booked graph-routing dependency (MEDIUM/informational).

## Summary for the author

| Sev | Finding | Plan line | Killing evidence |
|---|---|---|---|
| **CRITICAL** | "Source bound authoritatively at ingress" is wired to nothing: Step 1.5 stamps no source (reads a defaulted param), and no path carries `source` into the resolver's params. Sole real barrier is the secret token, which is **unset** on Citadel and makes `verify_hardware_auth` **raise**, so the approval path is dead-on-arrival / invites a gate-reopening "degrade." | L180-181, L614, L692-695, L178 | orchestrator.py:1157,1187,1960; main.py:726; harbinger.py:113,131,604; orchestrator.py:5203,5254; cerberus/config.py:46; creator_override.py:105-125 |
| **HIGH** | Single-use nonce leaks to the untrusted planner: `decision_queue_read` (autonomous tool) returns raw item dicts with no redaction, and `_decision_queue_resolve` returns the whole item — the planner can read the nonce and replay it as the first use. | L182-186, L201-204 | harbinger.py:580-602, 648-653, 1064-1091, 214-218 |
| MEDIUM | Step-1 for non-security tools is a sound chokepoint (async bypass closed by Item-13) but (a) hands off to the broken F5-0b authority and (b) depends un-bookedly on graph-routing staying wired. | L123-138 | orchestrator.py:4642-4651, 5211-5223, 5254; async_tasks.py:241-252 |

**The through-line:** the pass-2 patch fixed the *shape* of the approval mechanism
(token + source + nonce) but relocated the "named but not wired" defect from a tool
param to a nonexistent ingress stamp, left its only real barrier (the token)
unconfigured and fail-raising, and routed its secret (the nonce) through the same
unredacted read surface the untrusted planner can call. **The gate is theater by the
plan's own Abort #2 test:** an injected "approved" can reach execution authority without
genuine Master authority. The DONE signal is NOT reached — a CRITICAL landed on the
approval-authority leg.

### The two fixes the route needs before it is sound (stated as symptoms, not prescriptions)
1. **The authoritative source must have a real carrier from a real ingress to the
   resolver, or the design must stop depending on source entirely.** Right now no ingress
   captures a trustworthy transport identity and nothing carries any source into the
   resolver's params. Either wire it end-to-end (and prove the injected param is provably
   overridden by the carried value) or drop the source claim and rest the whole gate on the
   token — but then the token cannot be optional.
2. **The token gap must be a hard, booked prerequisite.** `CREATOR_AUTH_TOKEN` is unset;
   `verify_hardware_auth` raises. The plan must book "no approval possible until
   CREATOR_AUTH_TOKEN is set" as BLOCKED-on-Master (like R2/R3), and forbid any
   RuntimeError-swallowing degrade — otherwise the one real barrier is absent in
   production and the flow is either dead or open.
3. **The nonce must not be readable by the planner.** It cannot live on an item returned
   by an autonomous `decision_queue_read` (or by resolve's own result). It needs an
   executor-only channel or read-side redaction, neither of which the plan specifies.
