# RED TEAM — Sentinel Part 1 (Host Posture, Self-Red-Team, Live Loop & Gates)

**Target plan:** `wargames/plans/sentinel-part1-posture.md`
**Method:** Read-only. Verified every file:line claim the plan cites against the
actual source (`core.py`, `cerberus.py`, `creator_override.py`, `reversibility.py`,
`cerberus_limits.yaml`, `harbinger.py`, both watchdog files, and the live orchestrator
dispatch path). Attacked the gate front (Front 5) hardest because the plan stakes its
entire safety story on it running FIRST and WORKING.

**Verdict:** The plan does NOT establish that its central gate works before Fronts
1/3/4 lean on it. The one move that is supposed to install the first lock (F5-1) wires
a check on a code path the real quarantine dispatch never travels, and the approval path
it hands to Fronts 1/3/4 (F5-2) is built on a Harbinger API that has no approve/reject
semantics. Several "expected observations" would report GREEN while the dangerous door
stays open. Multiple recon marks are load-bearing and the plan proceeds on the guess.

---

## THE SINGLE WORST BREAK (CRITICAL)

### B0 — F5-1 adds `quarantine_file` to `never_autonomous`, but the runtime dispatch of `quarantine_file` never consults `never_autonomous`. The gate is named, not wired. The door stays open and the test goes green.

**Plan text attacked** (F5-1, lines 98-115; Gate ledger G1, line 429; Verification V1,
line 405):
> "Add `quarantine_file` to the `never_autonomous` list ... After the edit, a fresh
> `safety_check` on `quarantine_file` ... returns `verdict == DENY` ... A new test
> `test_quarantine_requires_approval` goes green."

**How it fails — traced end to end:**

The plan proves the gate against a REPL call to `safety_check`. But at runtime,
`quarantine_file` is dispatched to Cerberus as one of the 24 `SECURITY_TOOLS`, and that
dispatch path never calls `_safety_check` and never reads `never_autonomous`:

1. **Runtime dispatch (orchestrator.py:5205-5254).** In Step 5 the ONLY pre-execution
   gate is `hook_pre_tool` (line 5207), then the tool is dispatched directly:
   `module.execute(tool_name, params)` (line 5254). There is no `safety_check` call on
   this path.
2. **`_pre_tool_hook` (cerberus.py:1204-1273)** only evaluates `hooks.pre_tool.deny`
   rules, and each rule fires only `if tool_name in rule.get("applies_to", [])`. The
   `applies_to` lists (cerberus_limits.yaml:143-159) are `bash_execute`, `code_execute`,
   `file_write`, `email_send`, `notification_send`. `quarantine_file` is in NONE of them
   → every deny rule is skipped → `hook_pre_tool` returns `ALLOW`. **`_pre_tool_hook`
   never reads `never_autonomous` or `autonomous_tools` at all** (confirmed: the only
   readers of `never_autonomous` in the module are `classify_new_tool` and
   `auto_register_tool`, cerberus.py:1634/1707 — neither is on the dispatch path).
3. **Cerberus.execute (cerberus.py:484-490)** routes `tool_name in SECURITY_TOOLS`
   straight to `self._security.handle(...)` → `_quarantine_file` → `shutil.move`
   (core.py:571). No gate. No `never_autonomous` lookup. No `safety_check`.

So adding `quarantine_file` to `never_autonomous` changes the outcome of exactly one
thing: a *direct, manual* call to `safety_check` — which is NOT how the tool is
dispatched. The live quarantine still runs autonomously and unsnapshotted.

**And the plan's own proof is a green test guarding a bypassed path.** Even the
`safety_check` verdict the plan asks for is not what the plan claims. Trace
`_safety_check` → `_check_permission_tier` (cerberus.py:1148-1200) for `quarantine_file`
AFTER the F5-1 edit:
- Not in `autonomous_tools` (verified: `quarantine_file` appears nowhere in
  cerberus_limits.yaml).
- Not in `approval_required_tools`.
- Falls to `auto_register_tool` → `classify_new_tool` (cerberus.py:1633-1636), which
  **does** check `never_autonomous` first — so with the F5-1 edit it returns
  `approval_required`, i.e. verdict `APPROVAL_REQUIRED`, NOT `DENY`.

That is survivable for the *manual* `safety_check` call (V1 could pass). But it is
**irrelevant to the live door**, which never reaches this function. The plan's V1
("rerun R1 REPL `safety_check`") and its `test_quarantine_requires_approval` will both
go GREEN while `module.execute("quarantine_file", ...)` continues to `shutil.move` a
file with zero gating. This is the exact "looks governed but isn't" failure the brief
warns about — and it is the linchpin the whole plan builds on ("installs the locks
first," line 44-46).

**Severity: CRITICAL.** Every downstream gate that the ledger says is "wired" via
`never_autonomous` (G1 quarantine, G2 software_install, G4 firewall_apply, all through
F5-1) inherits this defect: `never_autonomous` gates the *classifier*, but the
*security-surface dispatch* and the *pre-tool hook* — the two paths a real detection
response actually takes — never consult it. The plan never traces the dispatch path; it
assumes `safety_check` sits in front of the tool. It does not.

**What F5-1 would actually have to do** (out of scope to fix here — the author patches):
gate `never_autonomous` at the real choke-point. Either (a) add `quarantine_file` (and
the future host-mutating names) to the `hook_pre_tool` deny `applies_to` set with a rule
that blocks never-autonomous tools, or (b) make `Cerberus.execute`'s `SECURITY_TOOLS`
branch (cerberus.py:484) run a `never_autonomous`/`safety_check` gate before delegating
to `_security.handle`. As written, F5-1 touches neither.

---

## OTHER BREAKS

### B1 — F5-2's approval path is built on a Harbinger API that has no approve/reject. "On `approved`" and "returns `rejected`" describe behavior the code cannot produce. (HIGH)

**Plan text:** F5-2 (lines 117-136): "Master resolves via `decision_queue_resolve` ...
On `approved`, the executor ... runs the action." F1-2 Fork (line 234): "**trigger:**
`decision_queue_resolve` returns `rejected`". Gate ledger G2 (line 430): "Master
resolves the proposal `approved`".

**How it fails:** `_decision_queue_resolve` (harbinger.py:604-653) takes a free-text
`resolution` string and sets `item["status"] = "resolved"`. There is no `approved`/
`rejected` enum, no boolean, nothing structured. `grep -n "approved\|rejected"
harbinger.py` returns **nothing** in the decision-queue code. So:
- The executor cannot branch on "approved vs rejected" — there is no such field to read;
  it would have to string-match free text ("approved"? "yes"? "do it"?), which is the
  hidden judgment call the brief tells us to hunt for.
- F1-2's Fork trigger (`decision_queue_resolve` returns `rejected`) can never fire as
  written — the method returns the resolved item, never the token `rejected`.

The plan treats `decision_queue` as an approve/deny gate. It is a resolved/unresolved
bridge. Building the entire gated-action contract (F5-2, and every G-row that says "runs
via decision_queue approval") on a non-existent approval semantics is a governance
illusion. **Severity: HIGH** — the approval path Fronts 1/3/4 are told to use does not
distinguish approve from reject, so "gated" collapses to "logged then executed on any
resolution."

### B2 — F5-2 never demonstrates the mutating call is skipped for the LIVE tool; its own "Abort" is unmet by its own design. (HIGH)

**Plan text:** F5-2 Abort (lines 135-136): "if you cannot prove the mutating call is
skipped, STOP." Counter (line 133-134): "the gated tool must `return` the 'pending
approval' ToolResult and never reach the mutating call."

**How it fails:** The mutating call for quarantine lives inside
`SecuritySurface._quarantine_file` (core.py:543-598), reached via
`Cerberus.execute → SECURITY_TOOLS branch → _security.handle` (cerberus.py:484-490).
F5-2 proposes to "route the *proposal* to Harbinger" but never says WHERE that
interception happens relative to `handle()`. `handle()` (core.py:159-213) dispatches
straight into `_quarantine_file` with no pre-call hook and "makes zero calls back into
Cerberus gating" (the plan's own recon, line 30). For the enqueue to actually replace
the move, F5-2 must insert a gate *inside or before* `handle()`/`execute`'s security
branch — which it does not scope. So the plan's own Abort condition ("cannot prove the
mutating call is skipped") is triggered by the plan as written, but the plan proceeds.
**Severity: HIGH.**

### B3 — F5-4 targets the wrong file. The Windows default is in `modules/cerberus/watchdog.py`, not the daemon the plan names. Editing "watchdog.py:37" is ambiguous and V4's grep may pass while a live Windows default remains. (MEDIUM)

**Plan text:** Recon row (line 37) identifies the watchdog as
`daemons/cerberus_watchdog/watchdog.py:71-92`. R6 (line 84) and F5-4 (line 161) say fix
`watchdog.py:37 → Path("data/cerberus_heartbeat.json")`.

**How it fails — verified:**
- `daemons/cerberus_watchdog/watchdog.py` has **no `C:/Shadow` anywhere**; its config
  default is already `Path("data/cerberus_heartbeat.json")` (config.py:29). The plan
  points its "the watchdog" arrow at the daemon that is already clean.
- The actual Windows defaults live in a SECOND, un-cited file
  `modules/cerberus/watchdog.py:37-39`:
  `C:/Shadow/data/cerberus_heartbeat.json`, `.../cerberus_lock`,
  `.../emergency_shutdown.log` — three of them, not one.
- `reversibility.py:55` Windows default is confirmed real.

Two problems: (1) The plan says "change `watchdog.py:37`" but there are two watchdog
files; an executor following blind edits the wrong mental model of which watchdog runs.
(2) F5-4 only mentions the heartbeat path — it misses the `lock` and `emergency_log`
Windows defaults on lines 38-39 of the in-module watchdog, so V4's `grep -rn 'C:/Shadow'
modules/` would **still hit** unless the executor notices and fixes all three, which the
plan does not instruct. V4 could be read as failing (grep non-empty) OR the executor
"fixes" only line 37 and V4 fails — either way the move as scripted is incomplete.
**Severity: MEDIUM** (latent trap, callers currently override — but the plan claims a
clean grep as PASS and its instruction won't produce one).

### B4 — R2 is load-bearing and unsettled, yet F1-1's watch-list and F3-1's audit both proceed assuming identity files. (MEDIUM)

**Plan text:** R2 (lines 61-67): "There is **no `identity/` dir at repo root**." F1-1
step 1 (line 181-184) adds "the identity/system-prompt files" to the FIM watch-list
"pending R2." Fork (lines 202-204) says continue without them.

**How it fails:** Verified — there is no `identity/` dir at repo root (CLAUDE.md's
Project Structure lists `identity/` but it does not exist). The system prompt is loaded
from code, not a standalone file (matches evidence in graphify output referencing
`system_prompt()` and compression logic, not a file). This is fine for F1-1 because the
Fork explicitly degrades gracefully. BUT: F3-1's self-audit table (line 284-291) has no
identity-integrity row and the plan's "posture report" claims to enumerate "Shadow's
real surface" — the identity/system-prompt surface (the thing an attacker most wants to
tamper) is silently absent from the audit because R2 was never settled into a concrete
target. The recon is marked, the Fork covers F1-1, but the *coverage gap it creates in
F3-1* is not flagged. **Severity: MEDIUM** — a self-audit that omits the identity surface
reports a clean posture over an unmonitored high-value asset.

### B5 — F1-1's "critical alert on any diff to a `cerberus_protected_path`" collides with EmergencyShutdown semantics; the fork between "alert" and "halt Shadow" has no trigger. (MEDIUM)

**Plan text:** F1-1 step 3 (lines 189-191): "on any diff to a `cerberus_protected_path`
... raise a **critical** Harbinger alert. Report only."

**How it fails:** `cerberus_protected_paths` (cerberus_limits.yaml:45-47) =
`modules/cerberus/` and `config/cerberus_limits.yaml`. In the existing safety model,
modification of a protected path is an EMERGENCY-SHUTDOWN-class event (the config header
line 2 says "Cerberus monitors this file for tampering"; `_check_config_integrity`
logs CRITICAL and the shutdown thresholds section is built around protected-path
tampering). F1-1 says the FIM response to the same event is "report only, critical
alert." Which wins — alert-and-continue (FIM) or halt (emergency shutdown)? The plan
never reconciles the two. An executor faces a judgment call with no trigger: does a FIM
diff on `config/cerberus_limits.yaml` alert, or does it trip the nuclear option? The
plan's "report only" invariant (Abort #2, lines 383-384) may directly contradict the
existing emergency-shutdown contract. **Severity: MEDIUM.**

### B6 — Vague "expected observation" flagged by the brief: V1's "DENY/REQUIRES_APPROVAL — whichever the enum uses" is a hidden judgment call, and the actual answer is neither on the live path. (MEDIUM)

**Plan text:** F5-1 (line 104-106) and V1 (line 405): "verdict DENY/REQUIRES_APPROVAL —
whichever the enum uses for never-autonomous."

**How it fails:** The enum (cerberus.py:41-48) has BOTH `DENY` and `APPROVAL_REQUIRED`.
For `quarantine_file` post-edit, the manual `safety_check` path returns
`APPROVAL_REQUIRED` (via classifier), never `DENY`. So an executor asserting `== DENY`
gets a fail; asserting "whichever" is not a testable predicate — it is the executor
guessing which is "correct." The move needs to name the exact expected verdict, and it
cannot, because (per B0) the verdict on the path that matters is `ALLOW` (hook_pre_tool)
regardless. **Severity: MEDIUM** — an ambiguous pass criterion masking a wrong-path
proof.

### B7 — Missing abort: nothing stops F1-2 from wiring `malware_scan`/`freshclam` subprocess execution before the never_autonomous gate for install is proven to actually deny at dispatch. (MEDIUM)

**Plan text:** F1-2 (lines 209-236) relies on `software_install` being `never_autonomous`
(cerberus_limits.yaml:199) to keep `apt install` gated. But per B0, `never_autonomous` is
only consulted by the classifier, not by `hook_pre_tool` or the security-surface
dispatch. F1-2 introduces new subprocess-executing operations (`malware_scan` shells
`clamscan`, `freshclam` "also a gated install-class action"). There is no abort tied to
"prove `software_install` actually denies at the dispatch path before shelling any
install-class subprocess." The plan assumes the classifier gate = a runtime gate.
**Severity: MEDIUM** (guarded partly by "Master's turn" human-in-loop, but the automation
the plan wires does not enforce it).

### B8 — F4-3 dead-man's switch reuses the `cerberus_watchdog` pattern, but R4 (is the Cerberus heartbeat loop even live?) is unsettled and the exemplar may be broken. (MEDIUM→LOW)

**Plan text:** F4-3 (lines 350-365) + R4 (lines 73-77): reuse the watchdog pattern,
"confirm the Cerberus heartbeat loop is itself live before reusing its pattern, so you
don't model on a broken exemplar."

**How it fails:** Verified — `send_heartbeat` (cerberus.py:1070-1095) is called only from
inside `safety_check` (cerberus.py:238). There is NO interval/async loop driving it; the
heartbeat advances only when a `safety_check` happens to run. If Shadow is idle (no
safety checks), the heartbeat goes stale and the *existing* `cerberus_watchdog` would
fire a false "Cerberus DOWN" → `pkill shadow_core` (watchdog.py `kill_shadow_process`).
So the exemplar F4-3 wants to copy is arguably already the SearXNG-dead failure mode in
reverse: a watcher that can kill a healthy-but-idle Shadow. R4 is genuinely load-bearing
and the plan flags it — good — but F4-3 still says "reuse this pattern" as the primary
route without settling whether the pattern is sound. **Severity: MEDIUM** for the reuse
risk, **LOW** for the plan (it does at least mark R4).

### B9 — F5-3 defense-only choke-point is real and well-specified, but its allow-list check has no abort for tools that legitimately take NO target (the read-only stubs), risking a false refusal or a bypass. (LOW)

**Plan text:** F5-3 (lines 138-157): reject any tool whose params describe a non-owned
target; iterate every `SECURITY_TOOLS` name.

**How it fails:** Most of the 24 tools take no host target at all (`threat_analyze`,
`firewall_generate` operate on text, `network_scan` reads local psutil). A blanket
"external target refused" check keyed by a `TARGETS_A_HOST` set is fine IF that set is
correct, but the plan defines the set by prose ("scans, probes, or generates rules
against a target") and then says "iterates every name in SECURITY_TOOLS and asserts
external-target tools are all refused" — the test can only assert refusal for tools the
executor *decided* target a host, which is circular. No abort if the `TARGETS_A_HOST`
classification is wrong. **Severity: LOW** (the gate is directionally good; the risk is a
mis-scoped set passing its own test).

---

## RECON MARKS THAT ARE LOAD-BEARING (answer to the brief's question)

- **R1** — Load-bearing and MIS-STATED. The premise "settle whether the classifier blocks
  `quarantine_file`" is answered by inspection: on the *manual* `safety_check` path it
  auto-classifies `autonomous` today (→ ALLOW), and on the *live dispatch* path it is
  never classified at all. R1 as scoped (REPL `safety_check`) settles the wrong path.
  See B0/B6.
- **R2** — Load-bearing for F3-1 coverage (identity surface), not just F1-1. Marked, but
  its downstream audit gap is not. See B4.
- **R4** — Load-bearing and correctly flagged; the exemplar it guards is arguably broken
  (idle-Shadow false-kill). See B8.
- **R3, R5, R6** — R3 (firewall active?) and R5 (model blobs) are genuinely gated by the
  plan and degrade gracefully. R6 is load-bearing for F5-4 and the plan points it at the
  wrong file. See B3.

---

## GATES NAMED-BUT-NOT-WIRED (the brief's key question)

| Gate | Plan claims it's wired via | Reality |
|---|---|---|
| **G1** quarantine | `never_autonomous` → `safety_check` DENY | `never_autonomous` not read on dispatch or in `hook_pre_tool`; live `quarantine_file` ungated. **NOT WIRED.** (B0) |
| **G2** software_install | `never_autonomous` + `decision_queue_add` | Same `never_autonomous` gap; `decision_queue` has no approve/reject. **PARTIAL — relies on human-in-loop, not code.** (B1/B7) |
| **G4** firewall_apply | `never_autonomous` + `nft -c` dry-run + approval | Inherits B0; `firewall_apply` doesn't exist yet so adding it to `never_autonomous` gates only the classifier of a not-yet-dispatched tool. **NOT WIRED at dispatch.** |
| **G6** self-audit no-write | "audit path proven to never write" | Assertion-only; plausible but the abort (Abort #2) contradicts emergency-shutdown semantics for protected paths. (B5) |

The invariant on line 441-444 ("none of those locks is merely named — every one cites
the wired check") is **false for G1/G2/G4**: they cite `never_autonomous`, and
`never_autonomous` is not on the enforcement path for the tools they guard.

---

## CreatorOverride / decision_queue as an approval path for an INTERNAL module (brief's direct question)

Confirmed both halves of the trap:

1. **CreatorOverride forbids internal-module callers.** `_validate_source`
   (creator_override.py:113-125) rejects any `source in INTERNAL_MODULES`, and
   `INTERNAL_MODULES` (line 44-47) includes `cerberus`. So a security action originating
   inside Cerberus can NEVER use `creator_exception`/`creator_authorize` to get unblocked
   — those require `source in EXTERNAL_SOURCES` (user_input/telegram/discord). The plan
   (F5-2, line 118-119) correctly notes CreatorOverride "only overrides ... from external
   sources" and routes around it to `decision_queue`. Good catch by the author.

2. **But the replacement (`decision_queue`) is not an approval mechanism** (B1): it has
   no approve/reject, so an internal module's "proposal" that gets `resolve`d cannot be
   programmatically distinguished as approved vs denied. The plan swapped a path that
   *forbids* internal callers for a path that *accepts* anything but *decides* nothing.
   Net: an INTERNAL module still has no code-enforced approval path for a gated host
   action. The governance is prose, resting on Master manually reading a free-text
   resolution and the executor manually branching on it — the hidden judgment call.

---

## Did Front 5 establish the gate works before Fronts 1/3/4 use it? (brief's headline question)

**No.** Front 5's "done-condition" (line 170-172) is "F5-1..F5-4 all green." But:
- F5-1 green proves a manual `safety_check` verdict on a path the live tool bypasses (B0).
- F5-2 green proves an enqueue happens, not that the mutating call is skipped on the real
  dispatch path, and rests on a non-existent approve/reject API (B1/B2).
- F5-4 green is a grep the plan's own instructions won't actually clear (B3).

So Fronts 1/3/4 would proceed on a gate front that *reports* green while the actual
enforcement choke-point (`hook_pre_tool` / `SECURITY_TOOLS` dispatch branch) is
untouched. This is precisely the "security-before-autonomy column that isn't wired"
failure. The plan assumes `safety_check` sits in front of every tool; the code puts only
`hook_pre_tool` there, and `hook_pre_tool` ignores `never_autonomous`.

---

## Abort conditions that should exist and don't

- **No abort for "never_autonomous gate not enforced at the dispatch choke-point."** The
  plan's Abort #5 (line 389-391) says stop if "`safety_check` cannot be made to DENY a
  never-autonomous security tool" — but it scopes the test to `safety_check`, the wrong
  path. The needed abort: "if `module.execute(<host-mutating tool>)` runs without passing
  the never_autonomous check, STOP." That abort would have caught B0; the plan's version
  does not.
- **No abort for the FIM-vs-emergency-shutdown contradiction** on protected paths (B5).
- **No abort for "decision_queue cannot express reject"** before treating it as a gate
  (B1).

---

## Honest assessment / what I attacked hardest

I attacked **F5-1 / the `never_autonomous` gate** hardest, because the entire plan's
safety claim ("installs the locks first," "each dangerous move arrives wearing its lock")
funnels through it. It broke cleanly: `never_autonomous` gates the classifier, but the
two paths a live quarantine/firewall-apply actually travel — `hook_pre_tool` and the
`Cerberus.execute → SECURITY_TOOLS → SecuritySurface.handle` dispatch — never read that
list. The plan proves the gate against `safety_check`, a function the tool's real
dispatch never calls. The proof (V1 + `test_quarantine_requires_approval`) goes GREEN on
a bypassed path. That is the worst break and it is CRITICAL.

**Run-through that reaches the worst break:**
1. Executor runs F5-1: edits `cerberus_limits.yaml` `never_autonomous` to add
   `quarantine_file`. ✅
2. Runs V1: constructs Cerberus, calls `safety_check("quarantine_file", ...)`. Classifier
   now returns `APPROVAL_REQUIRED` (not `DENY`, but "whichever the enum uses" — B6 lets it
   pass). `test_quarantine_requires_approval` asserts non-ALLOW → GREEN. ✅
3. Front 5 marked done. Fronts 1/3/4 build the live monitor loop (F4-1) that, on a planted
   FIM change, is supposed to "propose, never auto-quarantine."
4. The loop (or any router dispatch) calls `module.execute("quarantine_file", {...})`.
   Path: orchestrator.py:5207 `hook_pre_tool` → `quarantine_file` not in any `applies_to`
   → ALLOW → orchestrator.py:5254 `module.execute` → cerberus.py:484 SECURITY_TOOLS branch
   → `_security.handle` → `_quarantine_file` → **`shutil.move` executes. File moved.
   No approval. No snapshot.**
5. `test_gated_action_enqueues_not_executes` (V2) passes IF and only if the F5-2
   interception was placed correctly — but F5-2 never scoped where relative to `handle()`,
   and its approve/reject branch (B1) can't work — so the "green" test guards a path the
   live loop does not use.

The lock is on a door nobody walks through; the real door has no lock; and the test
checks the locked door.

**Could I NOT break it?** No — it broke on the first hard push at the gate front.

---

## Severity roll-up

| ID | Break | Severity |
|---|---|---|
| B0 | `never_autonomous` not enforced at live dispatch; F5-1 gate is on a bypassed path; green test guards it | **CRITICAL** |
| B1 | `decision_queue` has no approve/reject; F5-2/G2 "on approved / returns rejected" impossible | HIGH |
| B2 | F5-2 never proves mutating call skipped; own Abort self-triggers | HIGH |
| B3 | F5-4 edits wrong watchdog file; misses 2 of 3 Windows defaults; V4 grep won't clear | MEDIUM |
| B4 | R2 unsettled leaves identity surface out of F3-1 audit; not flagged | MEDIUM |
| B5 | FIM "report-only alert" on protected path collides with emergency-shutdown contract | MEDIUM |
| B6 | V1 "DENY/REQUIRES_APPROVAL whichever" is a hidden judgment call; actual live verdict is ALLOW | MEDIUM |
| B7 | No abort binding install-class subprocess to a proven dispatch-path gate | MEDIUM |
| B8 | F4-3 reuses a heartbeat exemplar that isn't loop-driven (idle-Shadow false-kill) | MEDIUM→LOW |
| B9 | F5-3 `TARGETS_A_HOST` set defined by prose; self-referential test | LOW |
