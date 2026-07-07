# RED TEAM — Sentinel Part 1, PASS 2 (attacking the patches)

**Target plan:** `wargames/plans/sentinel-part1-posture.md` (patched draft)
**Prior pass:** `wargames/red-team/sentinel-part1.md` (landed CRITICAL B0 + HIGH B1/B2 + MEDIUMs)
**Method:** Read-only. Re-verified every file:line the patched plan cites against live
source (`cerberus.py`, `security/core.py`, `orchestrator.py`, `async_tasks.py`,
`harbinger.py`, `creator_override.py`, `emergency_shutdown.py`, `reversibility.py`,
both `watchdog.py`, `claudemd_generator.py`, `cerberus_limits.yaml`). Concentrated on the
NEW/CHANGED moves (F5-0, F5-0b, F5-2, F5-3, F5-4, F4-3, F1-1) and the Gates ledger.

**Verdict:** The F5-0 *step-2* gate (the `Cerberus.execute` SECURITY_TOOLS branch) is the
one genuinely load-bearing patch and it **HOLDS** — it sits on the single universal
choke-point to `shutil.move`, so the original B0 (quarantine reaching the host ungated) is
correctly closed *if implemented as written*. **But the approval half of the fix does not
hold.** F5-0b's external-source auth check reads a caller-supplied `params["source"]` that
no dispatch path binds authoritatively, so an internal module can still self-approve — B1
survives the patch, re-dressed. Two verification moves (V4 grep, V3/F5-3 target test) are
blind or vacuous against the very code they claim to prove. Findings below.

---

## WHAT HELD (the hardest thing I attacked, and why it survived)

I attacked **F5-0 step-2** (the gate at `cerberus.py:484-490`, before `self._security.handle`)
hardest, because it is the patch the plan itself calls "the load-bearing one" and the abort
(#1) that would have caught B0 rests entirely on it. I tried to find a route to `shutil.move`
that skips it:

- **Unique mover.** `shutil.move` for quarantine lives only at `core.py:571`, inside
  `_quarantine_file`, which is only reachable from the `handlers` table in
  `SecuritySurface.handle` (`core.py:179`). `grep` across `modules/ daemons/ main.py`
  confirms `_security.handle` has exactly ONE caller: `cerberus.py:488`. So every route to
  the quarantine `shutil.move` funnels through the `SECURITY_TOOLS` branch at
  `cerberus.py:484`. A gate placed there before `handle()` is genuinely universal.
- **Async task queue bypass (the sneakiest path).** Step-5 dispatch, on a security tool
  flagged async, `submit_task()`s and `continue`s (`orchestrator.py:5225-5245`) —
  bypassing the pre-hook's post-check. I chased the worker: `async_tasks.py:241-252` has
  two branches. With `orchestrator` set (production wires `orchestrator=self` at
  `orchestrator.py:676`) it routes through `run_deferred_through_graph`
  (`orchestrator.py:1128-1154`) → the compiled parent graph → `_step4_plan` + `_step5_execute`,
  which re-enter the pre-hook AND `module.execute`. With `orchestrator=None` it calls
  `module.execute` directly (`async_tasks.py:251-252`). **Both branches still land on
  `Cerberus.execute` → `cerberus.py:484` for a security tool.** No async bypass of step-2.
- **Direct internal callers / monitor loop.** The F4-1 monitor loop does not exist yet;
  when built, if it calls `cerberus.execute("quarantine_file", …)` it hits `cerberus.py:484`
  too. There is no other door.
- **`quarantine_file ∈ SECURITY_TOOLS`** confirmed in the frozenset (`core.py:57-82`), so it
  cannot slip past the branch as an "unknown tool."

**Conclusion on the CRITICAL question:** *No*, there is no code path by which quarantine's
`shutil.move` reaches the host without crossing the F5-0 step-2 gate — **provided step-2 is
implemented as the plan describes**. The plan's own recon that step-1 verdict handlers are
no-ops today (confirmed: `orchestrator.py:5211-5223` branches only DENY/MODIFY;
`orchestrator.py:4642-4651` logs APPROVAL_REQUIRED and proceeds) is *correct*, and the plan
correctly does not lean on them. **This is the move that held. The B0 patch is real.**

---

## BREAKS IN THE PATCHES

### P1 — F5-0b's external-source auth check reads a spoofable, caller-supplied `params["source"]`. No dispatch path binds the true source into tool params, so an internal module can still self-approve. B1 survives. (**HIGH**)

**Plan text (F5-0b, lines 164-167):**
> "Extend `_decision_queue_resolve` to accept `decision: "approved" | "rejected"` ... with a
> source-auth check that mirrors `CreatorOverride._validate_source` — only an EXTERNAL source
> (user_input/telegram/discord) may set `approved`; an internal caller resolving its own
> request is refused."

**How it fails (traced):** `Harbinger.execute(tool_name, params)` (`harbinger.py:113`) takes
**no `source` argument** — every handler reads only `params`. `_decision_queue_resolve`
(`harbinger.py:604-653`) can therefore learn the caller only via `params.get("source")`. But
on the live dispatch path, tool params are the *plan step params*: `params = step.get("params", {})`
(`orchestrator.py:5203`), passed straight to `module.execute(tool_name, params)`
(`orchestrator.py:5254`). The orchestrator's real `source` variable is threaded to logging
and the graph (`orchestrator.py:1153, 1311`) but is **never injected into a tool's params**.
The only module-context injection anywhere is `requesting_module = classification.target_module`
at `orchestrator.py:4617-4627`, and (a) it's the routed *module* name, not the external
origin, and (b) it's injected only into the `safety_check` call, not into the step-5 execute
dispatch. `CreatorOverride` is safe because it *also* requires a secret `auth_token`
(`verify_hardware_auth`, `creator_override.py:105-111`) on top of `_validate_source`; F5-0b
mirrors only the source half. **Net:** a step whose params carry `{"decision":"approved",
"source":"user_input"}` — trivially emitted by the abliterated, no-refusal planner — passes
F5-0b's "external only" check from inside Cerberus. The plan describes the auth check but does
not build the authoritative source-binding substrate it depends on; that substrate does not
exist in the codebase. This is B1 re-dressed: the approve/reject *field* is now real, but the
*guard on who may set it* is not enforceable as written.

### P2 — F5-0's "approval token in params" bypass is only as strong as an unspecified token. A self-authored plan step can carry it and skip the step-2 gate on first dispatch. (**HIGH**)

**Plan text (F5-0 step 2, lines 136-140):**
> "check `never_autonomous` membership; if the tool is gated and **no approval token is
> present in params**, return a 'pending approval' ToolResult and do NOT call `handle()`."
> and (F5-2, line 212) "the deferred executor re-dispatches the tool WITH the approval token."

**How it fails:** The gate's open-condition is "an approval token is present in params." Params
originate from `step["params"]` (`orchestrator.py:5203`), which the planner controls. The plan
never specifies the token is an unforgeable, per-request secret bound to a specific
`decision=="approved"` queue item. If it is a static sentinel (e.g. `{"_approved": true}` or a
fixed string), the planner can emit it in the very first dispatch and walk straight through the
step-2 gate to `handle()` → `shutil.move`. The whole B0 fix collapses back to the pre-patch
state through a param the same untrusted planner writes. **Counter the plan must add but does
not:** the token must be a random nonce minted by the F5-0b resolver, stored on the approved
queue item, single-use, and verified against that item at the gate — not merely "present."
Without that spec, P2 is a latent re-open of B0.

### P3 — V4's grep pattern is blind to the generator's `C:\\Shadow` strings. F5-4 added `claudemd_generator.py` to scope, but the proof that "clears" it never sees it. (**MEDIUM**)

**Plan text (F5-4, lines 251, 256; V4, line 551):**
> "Also fix `modules/shadow/claudemd_generator.py:246-259`, which EMITS `C:\Shadow` ... "
> Expected: "`grep -rn 'C:/Shadow\|C:\\Shadow' modules/` returns **nothing**."

**How it fails (verified by running the exact grep read-only):** The generator's literals on
disk are double-backslash — `claudemd_generator.py:246` = `` `C:\\Shadow\\shadow_env` ``,
`:248`, `:259` = `C:\\Shadow/`. The plan's V4 pattern `C:\\Shadow` in a single-quoted basic-regex
arg matches `C:` + ONE literal backslash + `Shadow` = `C:\Shadow`. The generator text is
`C:` + backslash + backslash + `Shadow`, so the regex position after the first `\` is another
`\`, not `S` — **no match**. I confirmed: the exact V4 grep returns only the four
`watchdog.py`/`reversibility.py` lines and does NOT list the generator. Consequence: fixing
only the four forward-slash defaults makes V4 grep go empty **while all four `C:\\Shadow`
generator strings remain unfixed and invisible to the proof.** The generator was the B3
addition to F5-4's scope, and V4 — the move's only cited verification — cannot observe it.
The move can report GREEN with the generator drift still live. (Severity MEDIUM: the generator
only *emits* a stale CLAUDE.md; it doesn't write to a `C:\` dir at runtime — but the plan
claims V4 proves the generator fixed, and it does not.)

### P4 — F1-1 conflates FIM (post-hoc hash diff) with EmergencyShutdown's pre-write intercept. The "route protected-path diffs to the existing emergency path" hand-off is across two different event models and is left unwired. (**MEDIUM**)

**Plan text (F1-1 step 3, lines 289-292; Abort #4, lines 522-525):**
> "a diff to a `cerberus_protected_path` routes to the EXISTING emergency path ... hand off to
> the emergency-shutdown contract."

**How it fails:** `EmergencyShutdown`'s protected-path trigger (`emergency_shutdown.py:244-254`,
"Trigger 2") fires on `system_state["target_path"]` — i.e. when a module **attempts a write**
to a protected path, evaluated *before* the write. It is not a filesystem-integrity monitor.
`fim_verify` detects a file that has **already changed on disk** (possibly out-of-band, e.g. a
direct editor write) — a detection *after* the fact, with no in-flight `target_path` and no
active module to name. Routing a FIM diff into `check_and_execute` therefore requires
synthesizing a `system_state` the emergency contract was never designed to receive, and the
plan specifies none of that wiring — it says "hand off to the contract" as if the two share an
interface. They don't. Abort #4 tells the executor to STOP if the split is ambiguous; per this
analysis the split *is* ambiguous by construction (different trigger timing, different inputs),
so the plan may self-trigger its own abort. The `cerberus_protected_paths` values
(`config/cerberus_limits.yaml:45-47` = `modules/cerberus/`, `config/cerberus_limits.yaml`) and
the emergency trigger are real and correctly cited; the gap is the unspecified adapter between a
hash-diff event and a pre-write-intercept API.

### P5 — F5-3 / V3 defense-only test is vacuous: the tools it names take no host target, and NO current security tool actually reaches an external host. `TARGETS_A_HOST` is an empty set today; the test proves nothing. (**MEDIUM**)

**Plan text (F5-3, lines 232-234; V3, line 550):**
> "calling `network_scan`/`firewall_analyze` with a target of `8.8.8.8` or `example.com`
> returns `success=False`."

**How it fails (verified handler by handler):** `_network_scan` (`core.py:217-`) reads local
`psutil.net_connections` — no target param. `_firewall_analyze` (`core.py:602-`) reads
`config_text` — no target. `_firewall_evaluate/_compare/_explain_rule/_generate` operate on
text (`analysis`/`configs`/`rule_text`). `_vulnerability_scan` (`core.py:399-416`) accepts an
optional `target` but is a hard `"not_operational"` stub. `_threat_scan`, `_network_monitor`,
`_firewall_status`, `_log_analysis`, `_breach_check` are stubs or local-only. **No tool in
`SECURITY_TOOLS` reaches an external host today.** So F5-3's choke-point would validate a
`target` key that `network_scan`/`firewall_analyze` never read (the test's own examples pass
params the tools ignore), and `TARGETS_A_HOST` contains zero currently-network-reaching tools.
The gate is defensible as defense-in-depth for *future* tools, but V3 as scripted is
theater — it can only "refuse" tools the executor arbitrarily decided are host-targeting, which
is the prior pass's B9 circularity, unfixed. Not a live security hole (nothing reaches out),
but a green V3 asserts a property no live tool exercises.

### P6 — F5-0b cross-process persistence is fine for the FIELD but the plan's own "deferred executor in another process" model is unsupported by a single-file, load-at-init queue. (**LOW**)

**Plan text (F5-0b Fork, lines 181-183):** worries whether `_save_queue` writes the new field.

**Verified:** `_save_queue` (`harbinger.py:1081-1093`) `json.dump`s the whole `self._queue`
list, so an added `decision` field DOES persist; `_load_queue` (`harbinger.py:1064-1079`) reads
it back whole. So the Fork's narrow question ("does the field persist") resolves YES — good.
BUT the queue is an in-memory list loaded once at `__init__` (`harbinger.py:101`); a resolution
written by process A is invisible to a long-lived process B until B re-`_load_queue`s, and
nothing in the code reloads on read (`_decision_queue_read` reads `self._pending_items` in
memory). The plan's separation-of-resolution-from-execution model ("execution is a SEPARATE
deferred step ... that reads the field") therefore only works within one process, or requires a
reload the plan doesn't specify. LOW because same-process resolve→execute is the likely path,
but the plan's multi-process framing is not backed by the store's behavior.

---

## GATES LEDGER RE-CHECK (G0–G11): still named-but-not-wired?

| Gate | Patch claim | Post-patch reality |
|---|---|---|
| **G0** gate mechanism (F5-0/F5-0b) | V0 live `shutil.move`==0 AND V0b real approve/reject + internal refused | **Half-wired.** F5-0 step-2 choke-point is real (holds). F5-0b's "internal source refused" is **NOT enforceable** — the `source` it checks is spoofable (P1). G0 is not fully green. |
| **G1** quarantine | step-2 gate → approval_request; runs on `decision=="approved"` | Gate placement correct; **opens on a spoofable approval (P1) or an unspecified token (P2).** |
| **G2** software_install | `never_autonomous` via F5-0 + approval | Enforcement now on the live path via step-2 — *for security tools*. `software_install` is NOT a `SECURITY_TOOL`; it is an Omen/host tool that does NOT pass `cerberus.py:484`. F5-0 step-2 does **not** cover it; step-1 (`_pre_tool_hook` generic never_autonomous rule) would — but step-1's verdict is a no-op unless the orchestrator APPROVAL_REQUIRED handlers are also fixed (plan admits this). So G2 rests on the *weaker* of the two gates. **Named, partially wired.** |
| **G4** firewall_apply | `never_autonomous` via F5-0 | `firewall_apply` doesn't exist yet and won't be a `SECURITY_TOOL` unless added to the frozenset; if it's a host tool it rides step-1 only → same no-op-verdict dependency as G2. **Wiring conditional on unbuilt code.** |
| **G6** self-audit no-write | audit proven never writes | Assertion-only, plausible; inherits P4's protected-path ambiguity. |
| **G9** defense-only | `handle()` allow-list; V3 across all SECURITY_TOOLS | Vacuous today (P5) — no tool reaches a host, `TARGETS_A_HOST` empty. |

**Key ledger finding:** The plan's step-2 gate (the strong one) only covers the **24
`SECURITY_TOOLS`** because it lives in the `elif tool_name in SECURITY_TOOLS` branch. G2
(`software_install`) and G4 (`firewall_apply`) are NOT security-surface tools and do **not**
traverse `cerberus.py:484`; they can only be gated by F5-0 **step-1** (`_pre_tool_hook` generic
`never_autonomous` rule). But the plan itself concedes step-1's APPROVAL_REQUIRED verdict is a
no-op at both orchestrator handlers (`orchestrator.py:5211-5223`, `4642-4651`) unless those are
also fixed — and step-1 is explicitly labeled "do not rely on it." So **for non-security
host-mutating tools, the ledger still leans on the gate the plan told itself not to trust.**
The "belt-and-suspenders" only has suspenders where the tool happens to be a `SECURITY_TOOL`.

## Abort #1 (live-path gate) — sufficient?

Abort #1 is correctly *scoped* to the live dispatch (spies `shutil.move`, asserts on
`module.execute`, not a REPL) — that is the right fix for B0 and it WOULD catch a quarantine
mutation. **But it only guards mutating calls that pass `cerberus.py:484`.** A host-mutating
tool that is not in `SECURITY_TOOLS` (a future `firewall_apply`/`process_kill`/`host_write`
implemented as an Omen or Cerberus non-security tool) reaches its mutation without crossing
step-2, and Abort #1's spy targets (`shutil.move`/`nft`/`pkill`) would need step-1's no-op
verdict to actually block. So Abort #1 is **sufficient for the quarantine case it was written
for, insufficient as the general "no mutating call slips past" guarantee the ledger implies.**

---

## Severity roll-up

| ID | Break | Severity |
|---|---|---|
| P1 | F5-0b external-source auth reads spoofable `params["source"]`; internal module can self-approve — B1 survives | **HIGH** |
| P2 | F5-0 "approval token in params" unspecified/forgeable; planner can carry it and skip step-2 on first dispatch — latent B0 re-open | **HIGH** |
| P3 | V4 grep pattern blind to generator's `C:\\Shadow` (double-backslash); "clean grep" proof never sees the file F5-4 added | MEDIUM |
| P4 | F1-1 routes post-hoc FIM diff into EmergencyShutdown's pre-write-intercept API; adapter unwired; self-triggers Abort #4 | MEDIUM |
| P5 | F5-3/V3 defense-only test vacuous — named tools take no target; no SECURITY_TOOL reaches a host; `TARGETS_A_HOST` empty (B9 unfixed) | MEDIUM |
| P6 | F5-0b resolve/execute-across-processes model unsupported by single-file load-at-init queue (field persists, visibility doesn't) | LOW |

**Ledger structural finding (not a numbered break but load-bearing):** the strong gate
(step-2) is `SECURITY_TOOLS`-only; G2/G4 host tools ride the weak, self-admittedly-no-op
step-1. Abort #1 inherits the same scope limit.

---

## Honest bottom line

The patch **closes the CRITICAL B0** for the tool it was written for: quarantine's `shutil.move`
has exactly one route to the host and the F5-0 step-2 gate sits astride it. I could not find a
dispatch (async, graph, direct, monitor-loop) that reaches `shutil.move` without crossing
`cerberus.py:484`. That is the move I attacked hardest and it held — the B0 fix is real, not
named-only.

But the patch does **not** close B1: F5-0b's "only an external source may approve" is described,
not wired, because no dispatch path gives `_decision_queue_resolve` an authoritative source —
it reads a planner-controlled `params["source"]`. That is a **HIGH** re-open. And the F5-0
"approval token" is left unspecified enough (**HIGH**) that, if built as a static sentinel, it
re-opens B0 through the same untrusted param channel. Both are governance-substrate gaps: the
*fields and choke-points* are now correct, but the *trust signal that decides who may open the
lock* still comes from the untrusted planner. Until the plan builds authoritative source-binding
(inject the real request `source` into tool params at dispatch, out of the LLM's reach) and a
single-use nonce-based approval token minted by the resolver, the gate front is not DONE.

Two verification moves (V4 grep P3, V3 defense-only P5) would report GREEN without proving what
they claim — soft spots that let a real gap ship behind a passing check.
