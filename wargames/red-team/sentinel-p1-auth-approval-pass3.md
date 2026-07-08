# Red-Team Kill Report (Pass 3) — Sentinel P1: Authenticated Approval Channel

**Target plan:** `wargames/plans/sentinel-p1-auth-approval.md` (post-pass-2 patch)
**Prior reports:** `.../sentinel-p1-auth-approval.md` (pass 1), `.../sentinel-p1-auth-approval-pass2.md` (pass 2)
**Posture:** READ-ONLY. Nothing changed. Every claim traced to file:line in the live tree.
**Focus (per brief):** the current design — `_quarantine_file` enqueues only; the move lives in
poll-loop-private `_execute_approved(approval_id)`, keyed on the opaque id, not routable,
not descriptor-keyed. Did the hole move a third time, or is it closed?

---

## Verdict up front

The pass-2 CRITICAL **is closed** on its own terms. I attacked the `_execute_approved`
unreachability and the approval-id binding hardest, and the *confused-deputy-through-the-funnel*
break of pass 2 does not survive the B1/B2 split: `handle` dispatches by a hardcoded dict lookup
(no `getattr`), `_execute_approved` is not in the dispatch map / `SECURITY_TOOLS` / any
`get_tools()`, and the move keys on a server-minted opaque id the planner never controls. A
planner re-issuing `quarantine_file` can no longer ride an approved entry.

**But the hole did move a third time — sideways, out of the frame the plan drew.** The plan's
load-bearing recon claim, *"today the gate must protect exactly one live op: `quarantine_file`"*
(plan:122) and R3's abort-#1 premise (*"prove no OTHER host mutation exists outside that funnel,"*
plan:249), are **factually false against the tree.** At least two other **registered,
planner-routable** tools mutate **arbitrary planner-chosen filesystem paths** without ever
touching `SecuritySurface.handle` or the new gate:

- **`code_edit`** (Omen) — `permission_level: "autonomous"`, arbitrary-target `write_text`.
- **`sandbox_to_production`** (Omen) — arbitrary-target `shutil.copy2` + `unlink`.

`code_edit` is the worst: it is autonomous, needs no approval, and can overwrite Shadow's own
source — including `modules/cerberus/security/core.py`, the very file the gate lives in. The
authenticated-approval channel is a strong lock bolted to one door of a house with the back door
propped open. **This trips the plan's OWN abort #1** ("a second ungated funnel … stop and flag"),
which the plan mis-answered in its own recon. **One CRITICAL** (the un-swept second funnel), plus
one HIGH (planner controls the alert text Master reads on an unescaped HTML channel with no flood
control — the id-confusion vector the brief named), plus MEDIUM/LOW findings.

**Framing note:** none of the design (`PendingApprovals`, `_execute_approved`, `verify_approval`,
the poll loop) exists on disk yet — `modules/cerberus/security/core.py` is unmodified since the
Sentinel port (`855cd44`); no `approval.py`/`approval_channel.py`; grep for
`PendingApprovals|_execute_approved|verify_approval|getUpdates` returns nothing in `modules/`.
This is expected: the wargame skill produces the route, not the code. So pass 3 attacks the design
as written (M1–M8 as the spec an executor will build) and the live tree it depends on.

---

## What re-verified against the tree (credit + anchors)

I opened every file the brief named. These plan claims are **true**:

- Funnel: `shutil.move(str(source), str(dest))` at `security/core.py:571` inside
  `_quarantine_file` (`core.py:543`). ✅
- `handle` dispatch is a **hardcoded dict lookup**: `handler = handlers.get(tool_name)`
  (`core.py:195`), map at `core.py:168-193`. **No `getattr`, no reflection** — a planner passing
  `tool_name="_execute_approved"` gets `None` → "Unknown security tool" (`core.py:196-200`). ✅
  (Directly answers brief Q1 for the `handle` leg: `_execute_approved` is not name-reachable here.)
- Sole Cerberus reach: `elif tool_name in SECURITY_TOOLS: self._security.handle(tool_name, params)`
  (`cerberus.py:504-508`), no auth guard on the branch. ✅
- Pre-hook `_pre_tool_hook` (`cerberus.py:1224-1268`) is pattern-only; it reads
  `hooks.pre_tool.deny/modify` and **never** consults `approval_required_tools`/`never_autonomous`. ✅
- Orchestrator pre-hook branches only on `DENY`/`MODIFY`; `APPROVAL_REQUIRED` falls through to
  `module.execute` (`orchestrator.py:5296-5306`, execute at `:5340`). ✅
- `_action_category` short-circuits `_safety_check` to ALLOW before the approval check
  (`cerberus.py:1016-1022`). ✅
- Plan-gate is a documented stub: `plan_node.py` docstring — "APPROVAL_REQUIRED is a log-only
  Phase-1 stub … the plan still ends approved"; `cerberus_subgraph.py:37-44` — "no parent graph
  yet wires the short-circuit edges." ✅
- `quarantine_file` is in NONE of `approval_required_tools` / `never_autonomous` /
  `autonomous_tools` (`cerberus_limits.yaml:183-263`); schema advertises
  `{"file_path":"str","reason":"str"}`, `permission_level:"autonomous"` (`cerberus.py:768-771`). ✅
- `emergency_shutdown.py:400` `shutil.move` operates on a **fixed** internal path
  (`self._state_file` → `self._history_dir`), not routed, not planner-targeted. ✅ (R3 partial holds.)
- MCP servers (`grimoire/mcp_server.py`, `reaper/mcp_server.py`): hardcoded FastAPI endpoint
  decorators, no name-dispatch, no `getattr`, localhost-bound — **cannot** name an arbitrary
  method or reach a Cerberus/Security method. ✅ (Answers brief Q1 for the MCP leg: closed.)
- `tool_creator.py`: `stage_tool` writes to disk only; no in-process import/exec of the generated
  file; not routable. ✅ (Answers brief Q1 for tool-creation leg: closed.)

The design's own recon is again largely non-phantom. It fails on the mutation surface it never
enumerated, and on the human-facing alert it under-specifies.

---

## BREAKS

### CRITICAL — the second (and third) ungated funnel: `code_edit` and `sandbox_to_production` mutate arbitrary planner-chosen paths outside `SecuritySurface.handle`; the plan declares them nonexistent. This trips the plan's OWN abort #1.

- **Plan lines it contradicts:**
  - plan:122 — *"So today the gate must protect exactly one live op: `quarantine_file`."*
  - plan:134-138 (S1) — *"Confirmed no second caller … `shutil.move` at core.py:571; sole reach via cerberus.py:504-508."*
  - plan:240-252 (R3) — *"prove no OTHER host-mutating tool exists outside that funnel. Any planner-reachable host mutation NOT behind the funnel is an abort-and-flag (abort #1)."*
  - plan:697-699 (abort #1) — *"A second ungated funnel (R3). Any planner-reachable host mutation that does not pass through `SecuritySurface.handle` → … Stop."*
- **How it fails (one sentence):** `code_edit` is a **registered, `autonomous`** Omen tool
  (`omen.py:723-726`, dispatch `omen.py:586`, body `_code_edit` writing `path.write_text(new_content)`
  at `omen.py:1606`) whose only guard is `PROTECTED_PATHS = {"config",".git",".env"}`
  (`omen.py:443`) matched against the path **relative to the repo root** (`omen.py:1564-1570`) — so
  any target **outside** the repo root falls into the `except ValueError: rel = path` branch
  (`omen.py:1565-1566`) and matches none of the three names, and any in-repo target not under
  `config/`/`.git`/`.env` (e.g. `main.py`, `modules/cerberus/security/core.py`, `data/…`) is
  writable — a planner-reachable arbitrary-target host write that **never touches
  `SecuritySurface.handle`, never sees the approval gate, and carries no approval verdict at all.**
- **Second instance:** `sandbox_to_production` (registered `omen.py:608,929`; body `omen.py:2840`)
  copies to and unlinks a planner-chosen `production_path` via `shutil.copy2(src,dst)` /
  `dst.unlink()` (`sandbox.py:1126,1141,1144`). It is in `never_autonomous`/`approval_required`
  (`cerberus_limits.yaml:201`), but per S3 those verdicts are computed-then-discarded (pre-hook
  can't read the list; graph plan-gate is a stub), so on the live path it too is effectively
  ungated (it has an internal TestGate wrapper, not the approval channel).
- **Why this is the worst:** the entire plan is scoped by the claim that `quarantine_file` is the
  one live host-mutating op, so the authenticated channel is built to guard exactly that door. An
  attacker who wants to move/destroy/backdoor a file simply **does not use `quarantine_file`** — it
  uses `code_edit` (autonomous, unauthenticated) to overwrite the target directly, or
  `sandbox_to_production` to plant a file. The approval channel is real and sound for its one door;
  the house has at least two more. Worse still, `code_edit` can overwrite
  `modules/cerberus/security/core.py` itself — a planner could neuter the very gate this mission
  builds. Per the plan's own text this is a hard STOP (abort #1) that the recon answered "clear"
  while the hole sits one module over — the exact failure R3's pass-1 widening ("whole modules/
  tree," patch-log line 51) was supposed to prevent but did not.
- **Severity: CRITICAL.** See §WORST for the concrete run-through.

### HIGH — the planner controls the alert text Master reads; the surface is HTML with no escaping and no flood control, so a malicious pending entry can impersonate or crowd out the legitimate one and get the wrong `approval_id` approved.

- **Plan lines:** M4-B B1 (plan:427) — `resolved_params = {"file_path": ..., "reason": ...}`;
  M6 (plan:570-582) — the alert contains "op, absolute target path, a short opaque approval-id,
  TTL"; R6 (plan:260-266) — *"the ONLY defense against a malicious target is Master reading the
  path and declining."* The whole design's target-integrity guarantee reduces to: Master reads the
  alert and types the id he intends.
- **How it fails (one sentence):** `reason` is free-text planner input (`core.py:550`, advertised
  in the schema at `cerberus.py:770`) that the plan carries into `resolved_params` and the M6 alert;
  the Telegram transport is `parse_mode:"HTML"` (`telegram.py:64`) with **no `html.escape`
  anywhere** in `telegram.py`/`harbinger.py` and **no rate-limit/dedupe** on `send_message`, and
  the plan mandates neither escaping nor a pending-store size cap (grep of the plan for
  `escape`/`sanitize`/`flood`/`cap` → nothing) — so a planner can (a) craft `reason` to inject HTML
  that reshapes what Master sees, and (b) flood distinct pending entries (each distinct descriptor
  mints a fresh id + fresh alert; only *identical still-pending* descriptors dedupe, plan:438-442)
  so the malicious entry's alert is buried next to or made to mimic a benign one Master intends to
  approve. Approval keys on the id **in Master's reply text** (M5 step 3, plan:519-522); if the
  human approves the wrong id under crafted/crowded alerts, `_execute_approved` faithfully moves the
  attacker's chosen target. This is precisely the brief's Q2 sub-case ("make its alert look like the
  one Master intends to approve … flood so Master approves the wrong one … control the surfaced text
  Master reads").
- **Amplifier:** the planner can *also* send its own Telegram message to Master's chat via
  Harbinger `notification_send` (arbitrary `message`, `harbinger.py:359-473`, same HTML
  `send_message`). It is `never_autonomous` (`cerberus_limits.yaml:196`) — but per S3 that verdict
  is inert, so a planner today can post a spoof "approve A1" prompt or a fake alert into the same
  chat, further confusing which id Master approves.
- **Why HIGH not CRITICAL:** the plan *does* book target-legitimacy as a human-in-the-loop residual
  (R6) and mandates the absolute path be shown unmissably — so a careful Master reading the true
  path defeats it. But the plan hardens only *path visibility*; it never addresses *text
  controllability* (HTML injection, flooding, or a competing spoofed message), which degrades the
  human's ability to read the true alert. The one defense the entire design leans on is left
  attackable. **Severity: HIGH.**

### MEDIUM — `code_edit`'s protected-path check is repo-root-relative and name-substring based, so even the in-scope protection is bypassable; and it is the natural place an executor would (wrongly) think the M7 boundary already covers.

- **Plan line:** M7 Part A (plan:599-606) — the secret boundary denies path-taking tools aimed at
  `.env`/secrets via a realpath-first pre-execution check in the dispatch pre-hook.
- **How it fails (one sentence):** `code_edit`'s own guard checks `str(rel)` against literal names
  `{"config",".git",".env"}` (`omen.py:1568-1570`) **after** a repo-root `relative_to` that
  silently falls back to the raw path on `ValueError` (`omen.py:1564-1566`), so `.env` is protected
  only if it resolves under the repo root and only by exact name/prefix — a symlink or an
  out-of-root secret is unprotected — and M7 as specified enumerates *path-param* tools but the plan
  never lists `code_edit`/`sandbox_to_production` among the host-mutating ops it must gate, so an
  executor building M7 for read-secret-denial may still leave `code_edit`'s **write** to a
  non-secret-but-critical path (e.g. `main.py`, the gate file) ungated. M7 guards *reading* `.env`;
  nothing in the plan guards *writing* arbitrary code via `code_edit`.
- **Severity: MEDIUM** (compounds the CRITICAL; rated MEDIUM because it is the mechanism, and M7
  *could* be extended to a write-deny boundary — but the plan does not scope it that way).

### MEDIUM — the M7 secret-boundary abort names a real gap that exists in the tree: path-taking tools that open files via internally-derived or non-standard param names bypass a param-enumerator pre-hook.

- **Plan line:** M7 abort trigger (plan:625-628) — *"if a path-taking tool cannot be routed through
  the pre-execution check (e.g. a tool that opens files internally without surfacing the path to the
  dispatch layer), stop and flag."*
- **How it fails (one sentence):** The plan's enumerator keys on a documented name-set
  (`file_path`, `path`, `source`, `target`, `config_path`, plan:610), but the tree has registered
  read tools whose file access is derived internally or via other param names — e.g. Omen
  `file_read_safe` (`omen.py:251`) and Reaper/Grimoire internal file reads — so the enumerator's
  name-matching can miss a tool that reads a path it constructs from a non-path param, which is the
  exact hole the abort describes; it is a **real** gap, not a hypothetical, and the plan books it as
  an abort rather than closing it. (Not a break of the auth channel, but a confirmed real gap in the
  M7 half the brief asked me to check — Q4.)
- **Severity: MEDIUM** (correctly self-flagged by the plan; noted here as verified-real so it is not
  hand-waved past at build).

### LOW — brief Q1 residual: `omen.scaffold_test` is a routable tool that does dynamic `importlib` + `getattr` + `cls()`, but it CANNOT reach `_execute_approved`.

- **Finding:** `scaffold_test` (registered `omen.py:594`; body `_scaffold_test` at `omen.py:2101`)
  runs `importlib.import_module(f"modules.{module_lower}.{module_lower}")` →
  `getattr(mod, module_name.capitalize())` → `cls()` → `instance.get_tools()`
  (`omen.py:2118-2124`) on a planner-supplied `module_name`.
- **Why it is NOT a break of this design:** the import path is hardcoded as `modules.{x}.{x}` and
  the class as `{X}.capitalize()`, and the only call is a no-arg `cls()` + `get_tools()`. It cannot
  name an arbitrary method, cannot reach `SecuritySurface` (which lives at
  `modules.cerberus.security.core`, not `modules.security.security`, and is not a no-arg module
  class), and never invokes `_execute_approved`. So Q1's reflection/dynamic-dispatch vector is
  **closed** for the approval mechanism. It is a latent arbitrary-class-instantiation smell
  (constructor side effects) that predates and is orthogonal to this mission — flagged for the
  record, not scored against the plan.
- **Severity: LOW** (out-of-scope observation; the answer to Q1 is "unreachable").

---

## Brief attack-vector scorecard (the five the brief demanded)

1. **Is `_execute_approved` truly unreachable by the planner (reflection / dynamic dispatch /
   getattr / tool-creation / MCP)?** — **YES, unreachable.** `handle` is a hardcoded dict lookup,
   no `getattr` (`core.py:195`); MCP servers are hardcoded FastAPI routes, localhost, no
   name-dispatch; `tool_creator` writes to disk without in-process exec; `scaffold_test`'s dynamic
   import is shape-locked and cannot name the method. The B1/B2 split closes the pass-2 hole. ✅
2. **Can the planner influence which `approval_id` the poll loop approves?** — **YES, indirectly
   (HIGH).** Not by id collision/guessing (opaque, server-minted, keyed lookup) and not by flipping
   status (poll-loop-only), but by **controlling the alert text Master reads** (planner `reason` on
   an unescaped HTML channel) and **flooding distinct pending alerts** with no cap, so Master can be
   steered to approve the wrong id. The design's sole target-integrity defense (R6: human reads the
   path) is left attackable.
3. **Nonce/credential confidentiality.** — **Sound by construction, as designed.** The store is
   Cerberus-private, keyed by `approval_id`; the pending-approval leak surface (S8:
   `decision_queue_read`/`_decision_queue_resolve`, `harbinger.py:580,604`) is avoided because
   nothing places the nonce on a decision-queue item; the `pending_approval` ToolResult carries only
   the opaque id; M6 omits the nonce. No `logger.info(entry)` path in the design. The one caveat is
   the executor must not log the descriptor/credential (M3 warns of this) — a build risk, not a
   design break. **Closed as specified.**
4. **M7 secret boundary — does the enumerator + realpath-deny cover the store file and `.env`, or
   is there a path-taking-tool-opens-internally gap?** — **The gap is real** (MEDIUM above): the
   name-set enumerator can miss internally-derived paths; the plan books this as an abort rather
   than closing it. Separately, M7 as scoped guards *reading* secrets, not *writing* arbitrary code
   via `code_edit` — the CRITICAL's mutation surface is outside M7's frame.
5. **Any NEW move w/ vague obs / fork w/o trigger / gate named-not-enforced / dangerous write w/o
   gate / verification passing on broken result.** — **YES: a dangerous write with no gate.**
   `code_edit` (autonomous, arbitrary-target write, `omen.py:1606`) and `sandbox_to_production`
   (`sandbox.py:1126`) are dangerous host writes reachable by the planner with the approval gate
   nowhere in their path — the plan names the gate for `quarantine_file` only and declares no other
   mutation exists, so the gate is *named but not enforced* against the actual worst mutation
   surface. This is BREAK #1.

---

## WORST break — concrete run-through (the CRITICAL)

**Setup.** The executor builds M1–M8 exactly as written. The authenticated approval channel is real:
`_quarantine_file` only enqueues, `_execute_approved(approval_id)` is poll-loop-private and
unreachable, chat_id is transport-bound, the HMAC/nonce are sound, the M7 read-secret canary is
green. `quarantine_file` is fully, correctly gated. **V0→V5 all pass.** The mission certifies "done."

1. A compromised/confused planner wants `modules/cerberus/security/core.py` neutered (or any file
   destroyed). It does **not** emit `quarantine_file` — that door is now locked and would just
   return `pending_approval` and alert Master.
2. It first reads the target: `code_read(file_path="modules/cerberus/security/core.py")`
   (`omen.py:1620`, autonomous) → gets the exact source, picks a unique `old_text` (e.g. the body of
   `_execute_approved`'s guard, or `if entry is None or entry.status != "approved": return`).
3. It emits `code_edit(file_path="modules/cerberus/security/core.py", old_text=<unique guard line>,
   new_text=<neutered line>)`. Dispatch: `orchestrator.py:5340 → omen.execute → omen.py:586
   "code_edit" → _code_edit`. The PROTECTED_PATHS check (`omen.py:1568`) tests `str(rel)` — the file
   resolves under the repo root to `modules/cerberus/security/core.py`, which does **not** equal or
   start with any of `{"config",".git",".env"}` → check passes. `old_text` appears once → the write
   at `omen.py:1606` executes. **The gate file is now rewritten by an unauthenticated, autonomous,
   no-Telegram-round-trip planner call.**
4. No approval was requested. No alert reached Master. No credential, nonce, chat_id, or
   `_execute_approved` was involved. Every M8 test is green — because M8 only exercises
   `quarantine_file` and `handle`; nothing in the suite touches Omen. The authenticated channel is
   pristine and irrelevant.
5. **Result:** the "single dangerous-action funnel" was never single. The mission hardened one of
   at least three planner-reachable arbitrary-mutation doors and declared the other two nonexistent
   in its own recon. Per the plan's abort #1 this should have been a STOP before any build.

**Even simpler variant (no gate-file targeting):** `code_edit` any planner-named path to corrupt or
plant content — `main.py`, a systemd unit under the user's control, `data/memory/shadow_memory.db`
adjacent config — none of which is `quarantine_file`, none of which sees the approval channel.

**The fix the plan needs (named, not implemented):** R3 must actually enumerate host-mutating
**registered** tools (not just grep for primitives in `cerberus/`+`omen/` and conclude), find
`code_edit` and `sandbox_to_production`, and either route them through the same
descriptor+`verify_approval` gate (the plan's M2 enum is advertised as extensible for exactly this)
or explicitly document + gate them — otherwise abort #1 fires and the mission does not ship. The
authenticated channel is correct; its **scope** is wrong.

---

## Abort condition the plan has, correctly, but answered wrong

Unlike passes 1 and 2 (which each needed a *new* abort), pass 3's worst break is caught by an abort
the plan **already has** — **abort #1** (plan:697-699). The failure is not a missing abort; it is
that R3's recon **executed abort #1's check incorrectly** and returned "clear" when `code_edit` and
`sandbox_to_production` are sitting in `modules/omen/`. The corrective is procedural: R3 must derive
the mutation set from `registry.list_tools()` bodies (the plan already has the enumerator machinery
in M7 Part B — apply the same registry-derived discipline to host *mutations*, not just path
*reads*), not from a two-directory grep whose conclusion contradicts its own widened scope.

The one genuinely missing hardening (not a full abort) is on the human channel:

> **Harden the M6 alert against text control, not just path visibility:** `html.escape` all
> planner-derived fields (`reason`, path) before the HTML Telegram payload; cap pending-store size
> and rate-limit alerts so a planner cannot flood/crowd the approval surface; and treat any
> planner-issued `notification_send` to Master's chat as a spoofing risk while its `never_autonomous`
> verdict is inert (S3). The design leans its entire target-integrity guarantee on Master reading
> the true alert — so the alert's readability must itself be defended.

---

## Honest assessment

I attacked hardest at **`_execute_approved`'s unreachability and the approval-id binding** — the
exact seam the brief said moved in passes 1 and 2. **On that seam, the plan converged: it holds.**
`handle` is a hardcoded dict (no `getattr`), the MCP servers and `tool_creator` cannot name the
method, `scaffold_test`'s dynamic import is shape-locked away from it, the move is poll-loop-private
and opaque-id-keyed, the nonce/credential are confidential by construction, and the chat_id is
transport-bound. A planner can no longer ride an approval or forge one. The pass-2 confused-deputy
is genuinely closed. Credit: this is a real fix, not a relocation, for the door it guards.

The hole did not move *within* the approval mechanism — it moved *outside the mechanism's scope*.
The plan mis-scoped the problem: it asserted `quarantine_file` is the sole live host-mutating
routed tool and built a beautiful lock for that one door, while `code_edit` (autonomous, arbitrary
write, `omen.py:1606`) and `sandbox_to_production` (`sandbox.py:1126`) stand open one module away —
and `code_edit` can overwrite the gate's own source. That is the third relocation: not a subtler
attack on the same door, but the discovery that the recon fenced off the wrong perimeter. Under the
plan's own abort #1 this is a STOP.

**Secondary, real, and unpatched:** the design's single human-in-the-loop defense (Master reads the
alert) is attackable — the planner controls the alert's `reason` text on an unescaped HTML channel
with no flood control, and can post competing messages to the same chat. Path *visibility* is
hardened (R6); text *controllability* is not.

**Patch owner:** (1) redo R3 as a registry-derived enumeration of host-mutating tools, bring
`code_edit` + `sandbox_to_production` under the same gate or explicitly document+gate them, and only
then clear abort #1; (2) harden the M6 alert (escape planner fields, cap/rate-limit the store, treat
planner `notification_send` as a spoof vector). Then the approval channel — which is sound — finally
guards the whole mutation surface it claims to, not one door of three.
