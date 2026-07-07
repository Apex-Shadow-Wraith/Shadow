# BATTLE PLAN — Sentinel Part 1: Host Posture, Self-Red-Team, Live Loop & Gates

**Mission:** Make the absorbed Sentinel security surface a real defensive posture on
Citadel — Fronts 1, 3, 4, 5 of the brief. Front 2 (prompt-injection defense) is a
separate mini-mission in `sentinel-part2-injection.md`; this plan references its
earned-by condition but does not build it.

**Executor:** Opus 4.8, max effort. Runs this plan on its own turn. You are following a
route, not improvising one. Every move below has an expected observation and a failure
branch. Do not deviate without hitting a stated fork trigger or abort condition.

**RULE (carried from CLAUDE.md): No bandaid fixes, no temporary workarounds, no
TODO-later patches. Every fix is permanent and complete. If the root cause needs a
larger refactor, do it. If a fix exceeds this plan's scope, flag it and stop — do not
commit a partial fix that masks the real issue.**

---

## 0. Recon truth table (what the code ACTUALLY is, with file:line)

The brief describes what Sentinel *should become*. This is what it *is* right now,
confirmed by reading the code. Plan against this column, not the brief.

| Claim | Reality | Evidence |
|---|---|---|
| "Sentinel is a live routable module" | **FALSE.** Merged into Cerberus in Phase A. `modules/sentinel/` deleted (commit `cfcb79d`). | No `modules/sentinel/`; code at `modules/cerberus/security/{core,analyzer,threat_intelligence}.py` |
| Security is a `BaseModule` | **FALSE.** `SecuritySurface` is a plain helper owned by Cerberus. | [core.py:85](../../modules/cerberus/security/core.py#L85) `class SecuritySurface:` (no base) |
| 24 absorbed security tools | **TRUE.** Frozenset of 24; schemas in `Cerberus.get_tools()`. | [core.py:57-82](../../modules/cerberus/security/core.py#L57-L82); [cerberus.py:687-830](../../modules/cerberus/cerberus.py#L687-L830) |
| "Defense-only" HARD CONSTRAINT is enforced | **FALSE — docstring only, no runtime enforcement.** | [core.py:5-7](../../modules/cerberus/security/core.py#L5-L7) |
| "Sentinel proposes, Cerberus checks" | **Aspirational.** Security tools dispatch *through* `Cerberus.execute()`; gating is the orchestrator's `hook_pre_tool` + plan `safety_check`, which for security tools is mostly a pass. `SecuritySurface.handle()` makes zero calls back into Cerberus gating. | [cerberus.py:484-490](../../modules/cerberus/cerberus.py#L484-L490); [core.py:159-213](../../modules/cerberus/security/core.py#L159-L213) |
| File-integrity monitoring exists | **PARTIAL.** Real SHA-256 hash + baseline compare, BUT watches only caller-passed `file_paths`, has **no scheduler**, and the baseline file is empty `{}`. | hash [core.py:803-809](../../modules/cerberus/security/core.py#L803-L809); compare [core.py:277-298](../../modules/cerberus/security/core.py#L277-L298); baseline `data/sentinel_baseline.json` == `{}` (2 bytes on disk) |
| Malware/AV defense exists | **ABSENT.** No ClamAV/AIDE/rkhunter/chkrootkit/yara invoked. All references are knowledge strings in `threat_intelligence.py`. Host confirms none installed. | `command -v clamscan/aide/rkhunter/chkrootkit/yara` → all ABSENT; only `bwrap`, `ufw`, `nft`, `iptables` present |
| Quarantine is wired | **LIVE in security surface, UNUSED by Reaper.** `_quarantine_file` does real `shutil.move`. Reaper's quarantine dir is created but never written. | move [core.py:571](../../modules/cerberus/security/core.py#L571); Reaper dir created [reaper.py:315] but no quarantine call |
| Network monitoring | **READ-ONLY.** `psutil.net_connections` read; no block/kill. `network_monitor` + `threat_scan` are `"not_operational"` stubs. | [core.py:232](../../modules/cerberus/security/core.py#L232); stubs [core.py:361,380-397](../../modules/cerberus/security/core.py#L361) |
| Firewall analysis | **parse/grade/generate LIVE; APPLY ABSENT.** Generates nftables/iptables text; nothing applies it. | analyzer parse [analyzer.py:361-395], generate [analyzer.py:1587+], no `nft`/`iptables`/`ufw` subprocess anywhere |
| A monitoring daemon runs | **ABSENT.** All 24 tools are call-on-demand. No loop/thread/scheduler in `security/`. | agent E sweep: zero async loop/Timer/schedule in `security/*.py` |
| Cerberus heartbeat + external watchdog | **LIVE.** Cerberus writes `data/cerberus_heartbeat.json` inline; `cerberus_watchdog` daemon escalates on staleness. | write [cerberus.py:1089-1093](../../modules/cerberus/cerberus.py#L1089-L1093); check [daemons/cerberus_watchdog/watchdog.py:71-92] |
| Rollback (reversibility) works | **LIVE, real snapshot/rollback.** Default dir is a Windows path but Cerberus overrides it to `data/snapshots`. | engine [reversibility.py](../../modules/cerberus/reversibility.py); Windows default [reversibility.py:55]; override [cerberus.py:138](../../modules/cerberus/cerberus.py#L138) |
| Master-approval primitives | **TWO exist.** `CreatorOverride` (token override-of-block, external-source-only) and Harbinger `decision_queue_*` (async approval queue). | override [creator_override.py:63,93-125]; queue [harbinger.py:523-651] |
| Gate classification of security tools | **13 of 24 marked `autonomous`; `quarantine_file` is in NEITHER list** → auto-classified with `use_llm_judgment:false`. | `autonomous_tools` [cerberus_limits.yaml:245-259](../../config/cerberus_limits.yaml#L245-L259); `never_autonomous` [cerberus_limits.yaml:194-204](../../config/cerberus_limits.yaml#L194-L204) |
| **`never_autonomous` is enforced on the live dispatch path** | **FALSE — CRITICAL (red-team B0).** `never_autonomous` is read ONLY by the classifier (`classify_new_tool`/`auto_register_tool`), which is OFF the dispatch path. The live path is `hook_pre_tool` → `module.execute`; `_pre_tool_hook` only fires deny rules whose hardcoded `applies_to` list contains the tool, and no security tool is in any `applies_to`. So `quarantine_file` returns **ALLOW** and `shutil.move` runs ungated. Adding a name to `never_autonomous` gates the classifier, not the door. | classifier readers [cerberus.py:1633-1636,1707]; live hook [cerberus.py:1213-1273](../../modules/cerberus/cerberus.py#L1213-L1273); dispatch [orchestrator.py:5205-5254](../../modules/shadow/orchestrator.py#L5205-L5254); security branch [cerberus.py:484-490](../../modules/cerberus/cerberus.py#L484-L490) |
| **A working Master-approval path exists for an internal module** | **FALSE — HIGH (red-team B1).** `_decision_queue_resolve` sets `status="resolved"` + free-text; there is **no approve/reject field**. `CreatorOverride` forbids internal-module callers (`cerberus` ∈ `INTERNAL_MODULES`). So an internal security action has no code-enforced approve/reject path today — it must be built. | resolve [harbinger.py:604-653](../../modules/harbinger/harbinger.py#L604-L653); override source-block [creator_override.py:44-47,113-125](../../modules/cerberus/creator_override.py#L113-L125) |
| **`SafetyVerdict` enum values** | ALLOW, DENY, MODIFY, APPROVAL_REQUIRED (settles the "whichever the enum uses" ambiguity — red-team B6). | [cerberus.py:41-48](../../modules/cerberus/cerberus.py#L41-L48) |
| **Cerberus heartbeat is loop-driven** | **FALSE — R4 SETTLED (red-team B8).** `send_heartbeat` fires at init + inside `safety_check` only; there is no interval loop. An idle Shadow goes stale and the existing watchdog would `pkill` a healthy process. The exemplar F4-3 wanted to copy is itself broken. | `send_heartbeat` call sites [cerberus.py:238,1070-1095](../../modules/cerberus/cerberus.py#L1070-L1095) |

**The through-line:** the absorbed Sentinel is a *knowledge base with a few live read
paths and one live host-mutating tool (`quarantine_file`) that is ungated*. It is not a
monster; it is a well-read librarian with one unlocked door. This mission installs the
locks first (Front 5), then the muscle (Fronts 1/3/4), and never opens a dangerous door
without a gate wired to it.

---

## RECON NEEDED (unsettled — settle FIRST, before the move that depends on it)

Each carries the exact check. Do not plan around these with a guess; run the check.

- **R1 — SETTLED (red-team B0/B6).** The question "does `safety_check` DENY or ALLOW
  `quarantine_file`" was the WRONG question — it settles a path the live tool never travels.
  Settled facts: (a) on the live dispatch path, `quarantine_file` returns **ALLOW** from
  `hook_pre_tool` and `shutil.move` runs ungated; (b) on the manual `safety_check` path,
  post-edit it would classify `APPROVAL_REQUIRED` (not DENY). The real requirement is to
  enforce `never_autonomous` at the LIVE choke-point — that is Move **F5-0**, and its
  verification asserts on `module.execute`, not on a REPL `safety_check`.
- **R2 — Where do Shadow's identity / system-prompt files actually live?**
  There is **no `identity/` dir at repo root** (CLAUDE.md is stale). The FIM watch-list
  cannot target a path that doesn't exist. **Check:** `find . -path ./shadow_env -prune
  -o \( -iname '*identity*' -o -iname '*system_prompt*' -o -iname '*persona*' \) -print`
  and grep the orchestrator for where the system prompt is loaded
  (`grep -rn "system_prompt\|identity" modules/shadow/*.py | grep -i load`).
  **Blocks Move F1-1's watch-list.**
- **R3 — Is a host firewall active on Citadel right now?**
  `ufw`, `nft`, `iptables` binaries are present; active state needs root. **Check:**
  `sudo ufw status verbose; sudo nft list ruleset | head`. If `sudo` is unavailable to
  the executor, this is a question for Master, not a guess. **Blocks Move F1-4's
  baseline grade.**
- **R4 — SETTLED (red-team B8): the Cerberus heartbeat is NOT loop-driven.**
  `send_heartbeat` fires at init and inside `safety_check` only ([cerberus.py:238,1070](../../modules/cerberus/cerberus.py#L1070));
  no interval task drives it. Consequence: an idle Shadow (no safety checks) goes stale and
  the existing `cerberus_watchdog` would fire a false "Cerberus DOWN" and `pkill` a healthy
  process. **This exemplar is broken** — F4-3 must NOT copy it, and F4-6 (new) flags the
  existing bug for Master. Sentinel's own heartbeat must be written by the monitor loop on
  every tick (genuinely periodic).
- **R5 — Exact on-disk path of the `gemma4:26b` model blobs (for optional model-file FIM).**
  **Check:** `ls -la ~/.ollama/models/blobs 2>/dev/null | head; ollama show gemma4:26b
  --modelfile 2>/dev/null | head`. If blobs are not readable, mark model-file FIM
  **out of scope** and note it — do not fabricate a path. **Affects Move F1-1 scope.**
- **R6 — SETTLED (red-team B3): the Windows-path drift is in THREE places, not two, and
  not in the daemon I first cited.** `modules/cerberus/watchdog.py:37-39` holds THREE
  Windows defaults (`DEFAULT_HEARTBEAT_PATH`, `DEFAULT_LOCK_PATH`, `DEFAULT_EMERGENCY_LOG`),
  plus `reversibility.py:55`. `daemons/cerberus_watchdog/watchdog.py` is already clean.
  Additionally `modules/shadow/claudemd_generator.py:246-259` emits `C:\Shadow` template
  strings. All confirmed via `grep -rn 'C:/Shadow\|C:\\Shadow' modules/`. Fixed in Move F5-4;
  V4's grep must return empty across `modules/`.

---

## ⚠ ARCHITECTURE RESIDUAL & BLOCKED-on-Master (surfaced by pass-3 red-team; do not paper-patch)

Pass 3 proved the approve/reject MECHANISM (fields, choke-points, nonce single-use) is now
correct, but the **trust signal that decides "who may approve" still originates outside anything
Shadow can authenticate**. Two items are Master's, not the executor's:

- **AR-P1-1 — There is no authenticated approval channel (architecture, BLOCKED-on-Master/Opus).**
  F5-0b requires `source` to be "bound authoritatively at ingress." Recon (pass-3) shows that
  binding does not exist: `process_input(source="user")` is a plain default arg
  ([orchestrator.py:1157]), `main.py:726` passes no source at all, and `decision_queue_resolve`
  is a **routed tool** whose params are LLM-planned ([orchestrator.py:5203,5254]) — the
  orchestrator's `source` local is never merged in. Building a trustworthy approval requires an
  **out-of-band channel** (an approval path that does NOT traverse LLM-planned tool params and
  whose caller identity is authenticated) — an architecture decision CLAUDE.md reserves for Opus
  sessions. Until it exists, **the entire gated-host-action capability (G1–G4) cannot open**; the
  buildable pieces (F5-0 choke-points, nonce, redaction) are necessary but not sufficient without
  it. Book BLOCKED-on-Master.
- **BLOCKED — `CREATOR_AUTH_TOKEN` is unset on Citadel.** `verify_hardware_auth` RAISES
  `RuntimeError` when the token is absent ([creator_override.py:105-110]); recon (pass-3) found no
  token in `.env`/`config.yaml`/`config.local.yaml` (defaults to None,
  [cerberus/config.py:46]). So the token-gated approval path is **dead on arrival** and any
  "degrade to no-token" would re-open the gate. **Exact input needed from Master:** provision
  `CREATOR_AUTH_TOKEN` in `.env` (secrets-only) before F5-0b can function. Do NOT invent a
  default or a bypass.

**Consequence for sequencing:** the READ-ONLY posture (FIM, self-audit, monitor loop alerts,
firewall-PROPOSE, quarantine-PROPOSE) is buildable and safe now. The GATED HOST ACTIONS
(quarantine move, firewall apply, install, process kill) stay dormant until AR-P1-1 is decided
and `CREATOR_AUTH_TOKEN` is provisioned — a stronger, more honest gate than the first draft's.

---

## FRONT 5 FIRST — The Gates (security before autonomy is a column, not a phase)

The brief and SUCCESS point 9 both demand the gates exist *before* the capability they
guard. So Front 5 is built first: every host-mutating or self-modifying capability this
plan later adds already has its lock installed here. If any Front-1/3/4 move tries to use
a capability whose gate is not yet wired, that is an **abort**.

> **Red-team correction (B0/B1) — the two locks the first draft named but never wired.**
> The first draft added tool names to `never_autonomous` and called that a gate. The
> attacker proved `never_autonomous` is read ONLY by the off-path classifier — the live
> dispatch (`hook_pre_tool` → `module.execute` → `SecuritySurface.handle` → `shutil.move`)
> never consults it, so the door stayed open behind a green test. And the approval path the
> draft handed to Fronts 1/3/4 (`decision_queue`) has no approve/reject semantics at all.
> **Both must be BUILT before any name-listing matters. F5-0 wires enforcement onto the
> live path; F5-0b builds the approve/reject mechanism. Only then does F5-1's list edit
> mean anything.**

### Move F5-0 — Wire `never_autonomous` enforcement onto the LIVE dispatch path (was missing)
The gate has to sit where each class of tool actually travels. **Pass-2 red-team surfaced that
the two tool CLASSES take different paths, so the gate needs BOTH legs to be real — not one
load-bearing and one decorative:**
- **Security-surface tools** (the 24 `SECURITY_TOOLS`, incl. `quarantine_file`) travel through
  `Cerberus.execute`'s `SECURITY_TOOLS` branch → step-2 gate covers them (confirmed by pass-2:
  every route to `shutil.move` funnels through the one caller of `_security.handle` at
  [cerberus.py:488](../../modules/cerberus/cerberus.py#L488)).
- **Non-security host tools** (`software_install`, `firewall_apply`, `process_kill`, `host_write`)
  are NOT `SECURITY_TOOLS`; they never reach [cerberus.py:484](../../modules/cerberus/cerberus.py#L484),
  so step-2 does NOT cover them. **For these, step-1 is the ONLY gate and MUST be made real** —
  the plan cannot "not rely on" step-1 for them (pass-2 ledger finding).
**Do:**
1. **At `_pre_tool_hook`** ([cerberus.py:1213-1273](../../modules/cerberus/cerberus.py#L1213-L1273)):
   add a generic rule that, for ANY `tool_name` in the `never_autonomous` set (read from
   `self._limits`), returns `SafetyVerdict.APPROVAL_REQUIRED` (the enum value confirmed to
   exist, [cerberus.py:41-48](../../modules/cerberus/cerberus.py#L41-L48)) — independent of
   the hardcoded `applies_to` deny rules. Then **make `APPROVAL_REQUIRED` actually stop
   execution at BOTH verdict handlers**: the plan-level `safety_check` currently LOGS it and
   proceeds ([orchestrator.py:4642-4651](../../modules/shadow/orchestrator.py#L4642-L4651)) and
   the pre-hook only branches on DENY/MODIFY ([orchestrator.py:5211-5223](../../modules/shadow/orchestrator.py#L5211-L5223))
   — both must route `APPROVAL_REQUIRED` to the F5-0b approval path instead of `module.execute`.
   **This leg is load-bearing for the non-security host tools** (they have no step-2), so it gets
   its own live-path test, not just "fix but don't rely on."
2. **At the `SECURITY_TOOLS` branch in `Cerberus.execute`** ([cerberus.py:484-490](../../modules/cerberus/cerberus.py#L484-L490)):
   before delegating to `self._security.handle(...)`, check `never_autonomous` membership;
   if the tool is gated and **no valid single-use approval nonce (F5-0b) is presented**, return a
   "pending approval" ToolResult and do NOT call `handle()`. The open-condition is a per-approval
   nonce minted by the F5-0b resolver and consumed on use — **never a static sentinel the planner
   can carry on first dispatch** (pass-2 P2). This covers the loop calling
   `cerberus.execute("quarantine_file", …)` directly, which bypasses the orchestrator hook.
**Expected observation (asserts on the LIVE path, not a REPL):**
- `test_quarantine_ungated_dispatch_is_blocked` — spies `shutil.move`
  ([core.py:571](../../modules/cerberus/security/core.py#L571)), drives
  `await cerberus.execute("quarantine_file", {...})` AND a full Step-5 dispatch; `shutil.move`
  call count **0** in both; ToolResult pending/blocked.
- `test_nonsecurity_host_tool_blocked_via_step1` — a synthetic never-autonomous non-security tool
  (e.g. `software_install`) driven through Step-5 does NOT execute (verdict `APPROVAL_REQUIRED`
  routes to approval, not `module.execute`) — proving step-1 is real, since step-2 can't cover it.
- `test_static_token_does_not_open_gate` — a dispatch carrying a guessed/replayed token in params
  is refused; only a freshly-minted F5-0b nonce opens it.
**Most likely failure:** the pre-hook is edited but the orchestrator still calls `module.execute`
on `APPROVAL_REQUIRED` (only DENY handled today). **Cause:** verdict handling branches only on
DENY/MODIFY at both sites. **Counter:** extend BOTH handlers; assert the non-security tool's move
count 0.
**Abort:** if `shutil.move` (or any non-security host mutation) fires in any invocation, STOP —
the gate is not on that tool's live path (the abort that would have caught the first draft's B0,
now extended to the non-security host tools pass-2 flagged).

### Move F5-0b — Build the approve/reject mechanism with an AUTHORITATIVE trust signal (it does not exist today)
`decision_queue` stores items and marks them `resolved` with free text — no approve/reject
([harbinger.py:604-653](../../modules/harbinger/harbinger.py#L604-L653)); `CreatorOverride`
forbids internal-module callers AND requires a secret token. So the approval path must be built
as real code. **The load-bearing lesson (pass-2 red-team P1): the signal that decides "who may
approve" must NOT come from LLM-planned tool params — the planner is untrusted, and an injected
instruction can emit `{"decision":"approved","source":"user_input"}` to self-approve.
`CreatorOverride` is safe only because it ALSO requires the secret creator token; mirroring only
its source-string check is not enough.**
**Do:**
1. Extend `decision_queue_add` items with `kind: "approval_request"` and a structured
   `proposed_action` (`{tool, params, rationale, risk, rollback_available: bool}`).
2. Extend `_decision_queue_resolve` to accept `decision: "approved" | "rejected"`, set
   `item["decision"]`, AND require the **secret creator auth token** (reuse
   `CreatorOverride.verify_hardware_auth`, [creator_override.py:93-111](../../modules/cerberus/creator_override.py#L93-L111))
   — an `approved` with no valid token is refused. The **`source` must be bound authoritatively
   by the harness/orchestrator at the ingress boundary (the same place Step-1.5 stamps the input
   source), NOT read from tool params** — so a planned/injected `source` field is ignored.
3. On `approved`, the resolver **mints a single-use nonce**, stores it on the item, and the gated
   tool's host action runs (deferred, inside a snapshot) ONLY when it presents THAT nonce, which
   is consumed on use. **The nonce MUST be redacted from every model-visible surface (pass-3
   HIGH): `decision_queue_read` (an `autonomous`-permission routed tool) currently returns raw
   item dicts unredacted ([harbinger.py:589-599](../../modules/harbinger/harbinger.py#L589-L599)),
   so the planner could read `item.nonce` into LLM context and replay it as the FIRST use.**
   `decision_queue_read`/`_resolve` return values and the persisted queue must strip `nonce` (and
   the token) before any model-visible return. Pending/`rejected`/replayed-nonce/leaked-nonce → no
   execution.
**Expected observation:** `test_approval_requires_token` — `decision="approved"` with no/invalid
token is refused; with the valid token, accepted. `test_source_is_not_param_spoofable` — a
dispatch whose LLM-planned params contain `{"source":"user_input","decision":"approved"}` does
NOT self-approve. `test_nonce_is_single_use` — the minted nonce unlocks once; a replay is refused.
`test_nonce_not_in_model_visible_read` — `decision_queue_read`'s tool result contains NO `nonce`
or token field (pass-3 redaction). `test_gated_tool_respects_decision` — the tool runs only on
approved+valid-nonce, no-ops otherwise (spy the mutating call).
**Most likely failure:** the "approved" branch executes inline the moment Master approves,
re-introducing autonomy from inside the resolve call. **Cause:** coupling execution to
resolution. **Counter:** resolution only sets the field + mints the nonce; execution is a
SEPARATE deferred step that reads the field and consumes the nonce — assert resolve() itself
performs no host action.
**Abort:** if the approval decision or source can be set from LLM-planned tool params, STOP —
the trust signal is spoofable and the whole gate is theater (pass-2 P1).
**Fork:** if Harbinger's queue is persisted per-process and a deferred executor can't see a
resolution written in another process (**trigger:** `decision_queue_read` in a fresh process
returns the item without the `decision` field), then the queue must persist `decision` to
its backing store — confirm `_save_queue` writes the new field; if not, that is the fix.

### Move F5-1 — List the host-mutating tools as never-autonomous (now the list is load-bearing)
With F5-0 wiring `never_autonomous` onto the live path, editing the list finally changes
behavior.
**Do:** Add `quarantine_file` to `never_autonomous`
([cerberus_limits.yaml:194-204](../../config/cerberus_limits.yaml#L194-L204)), plus the
host-mutating tool names this plan introduces so they are gated the moment they exist:
`firewall_apply`, `process_kill`, `host_write`, `av_quarantine`.
**Expected observation:** rerun `test_quarantine_ungated_dispatch_is_blocked` (F5-0): with
`quarantine_file` now in `never_autonomous`, the live dispatch returns APPROVAL_REQUIRED and
`shutil.move` call count is 0. Remove `quarantine_file` from the list and the same test goes
RED — proving the list entry, not something else, is what gates it.
**Most likely failure:** the limits loader caches at construct time so the edit isn't seen
by a long-lived Cerberus. **Cause:** in-process cache. **Counter:** confirm `self._limits`
is (re)read at classification/hook time or reconstruct Cerberus; do not "fix" by editing the
test.

### Move F5-2 — Route gated security actions through the F5-0b mechanism, at the choke-point
F5-0b built the approve/reject mechanism; this move connects the security surface to it and
pins WHERE the interception happens (the first draft left this unscoped — red-team B2).
**Do:** The interception is the F5-0 gate at the `SECURITY_TOOLS` branch
([cerberus.py:484-490](../../modules/cerberus/cerberus.py#L484-L490)) **before**
`self._security.handle(...)` — the single point every security tool passes through, and
`handle()` makes zero calls back into gating ([core.py:159-213](../../modules/cerberus/security/core.py#L159-L213)),
so the gate cannot live inside it. When a gated tool is dispatched without an approval token,
the branch enqueues an `approval_request` (F5-0b schema) and returns a "pending approval"
ToolResult **instead of** calling `handle()`. Master resolves via the F5-0b approve/reject.
On `decision=="approved"`, the deferred executor re-dispatches the tool WITH the approval
token, inside a reversibility snapshot.
**Expected observation:** `test_gated_action_enqueues_not_executes` spies `_quarantine_file`
/ `shutil.move` and asserts, in one dispatch of `quarantine_file` with no token: queue length
+1 (an `approval_request`), mutating-function call count **0**, host unchanged (file still at
origin, `nft` ruleset unchanged).
**Most likely failure:** the enqueue is added but `handle()` still runs afterwards (additive,
not replacing). **Cause:** gate placed after the branch delegates. **Counter:** the branch
must `return` the pending ToolResult before `handle()`; the spy asserts call count 0.
**Abort:** if the mutating call is not provably skipped, STOP — an approval path that still
executes is worse than none. This abort is now backed by F5-0's live-path test, not a REPL.

### Move F5-3 — Enforce the defense-only line in code, not just the docstring
The HARD CONSTRAINT is a comment ([core.py:5-7](../../modules/cerberus/security/core.py#L5-L7)).
**Do:** Add a single choke-point in `SecuritySurface.handle()` ([core.py:159-213](../../modules/cerberus/security/core.py#L159-L213))
that rejects any tool call whose params describe a target Shadow does not own — an
allow-list of self-targets (localhost, `127.0.0.1`, Citadel's own hostname/IPs, Shadow's
own repo paths) for any tool that scans, probes, or generates rules against a target.
Anything outside the allow-list returns a failed ToolResult with reason
`"defense-only: refusing to act on a non-owned target"`. This is the code that makes
"never probes systems it does not own" real.
**Scope (pass-2 P5): this is FORWARD-LOOKING, and the plan must say so.** Today NO
`SECURITY_TOOL` actually reaches an external host — `network_scan`/`firewall_analyze` take no
host-target param and `vulnerability_scan` is a stub, so `TARGETS_A_HOST` is currently EMPTY and
a test that "refuses `network_scan` against 8.8.8.8" is vacuous (the tool ignores the param).
The gate is built now so that the MOMENT any tool gains a host-target parameter (e.g. a future
active scanner), it is refused for non-owned targets by construction.
**Most likely failure:** the allow-list is defined but only checked per-tool, so a future
host-targeting tool bypasses it; or the test asserts on params current tools ignore (false
confidence). **Cause:** per-tool checks / vacuous test. **Counter:** enforce at `handle()`
before dispatch, keyed by a `TARGETS_A_HOST` set; **test with a SYNTHETIC host-targeting tool**
added to the set — assert an external target is refused and localhost allowed — rather than
against current tools that ignore the target. `TARGETS_A_HOST` is empty today and every entry is
justified by a real host-target param.
**Expected observation (revised):** `test_defense_only_rejects_external_target` uses a synthetic
tool declared to take a `target` param; external target → `success=False` + refusal reason;
localhost → allowed. A second assertion documents that no CURRENT `SECURITY_TOOL` is in
`TARGETS_A_HOST` (so the gate is dormant-but-wired, not falsely claiming to refuse today).
**RECON NEEDED inside this move:** the exact self-owned identity of Citadel — hostname and
local IPs. **Check:** `hostname; hostname -I`. Bake the result into the allow-list as
config (`config.yaml` `security.owned_targets`), never hardcode.

### Move F5-4 — Fix the Windows-path drift (R6) so gate infrastructure is trustworthy
**Do:** Change ALL FOUR Windows defaults to Linux-relative defaults (red-team B3 — the first
draft cited the wrong file and missed two of them):
- `modules/cerberus/watchdog.py:37` `DEFAULT_HEARTBEAT_PATH` → `Path("data/cerberus_heartbeat.json")`
- `modules/cerberus/watchdog.py:38` `DEFAULT_LOCK_PATH` → `Path("data/cerberus_lock")`
- `modules/cerberus/watchdog.py:39` `DEFAULT_EMERGENCY_LOG` → `Path("data/emergency_shutdown.log")`
- `modules/cerberus/reversibility.py:55` snapshot default → `Path("data/snapshots")`
Also fix `modules/shadow/claudemd_generator.py:246-259`, which EMITS `C:\Shadow` venv/path
strings into a generated CLAUDE.md — on Citadel it must emit the Linux venv path
(`~/dev/Shadow/shadow_env`). (`daemons/cerberus_watchdog/watchdog.py` is already clean — do
not touch it.) These are defense-in-depth: callers currently override, but a default writing
to a literal `C:/Shadow/...` dir on Linux is a latent trap.
**Expected observation:** `grep -rniE 'C:[\\/]+Shadow' modules/` returns **nothing** (the
case-insensitive, backslash-class pattern catches the generator's double-backslash literals that
a plain `C:\\Shadow` grep misses — pass-2 P3). PLUS a behavioral test
`test_generated_claudemd_uses_linux_venv` asserts the generator OUTPUT contains
`~/dev/Shadow/shadow_env` and NOT `C:\Shadow` — because a grep alone proved blind to the
generator's escaping. `test_reversibility_default_dir_is_relative` and
`test_watchdog_defaults_are_relative` assert the defaults are under `data/`.
**Most likely failure:** a test elsewhere pins a Windows default string, or the generator
fix breaks a claudemd snapshot test. **Cause:** tests written against the old drift.
**Counter:** update those tests to the correct Linux path — they were asserting drift, not
behavior (Fix Quality Rule: fix the root cause).

**Gate-front done-condition:** F5-0, F5-0b, F5-1, F5-2, F5-3, F5-4 all green — and the
live-path abort in F5-0 has NOT triggered. Only now may Fronts 1/3/4 build capabilities that
use these gates. If a later move needs a gate not listed here, add it
here first.

---

## FRONT 1 — Defend Citadel (the host)

### Move F1-1 — A real, scheduled File-Integrity watch-list over Shadow's own surface
Today FIM hashes only what a caller passes and never re-checks ([core.py:277-298](../../modules/cerberus/security/core.py#L277-L298); empty baseline).
**Do:**
1. Define a **watch-list** in `config.yaml` under `security.fim_paths`: Shadow's own code
   (`modules/`, `main.py`), config (`config/config.yaml`, `config/cerberus_limits.yaml`),
   and — pending **R2** — the identity/system-prompt files. Add model blobs **only if R5
   resolved a readable path**; otherwise note "model-file FIM out of scope: Ollama blobs
   not readable" and move on.
2. Add a `fim_baseline_build` operation that populates `data/sentinel_baseline.json` with
   `{path: sha256}` for every watch-list file, and a `fim_verify` that re-hashes and
   returns the diff (added / removed / **modified**).
3. Schedule `fim_verify` on the live loop (Front 4). **Reconcile with emergency-shutdown
   semantics (red-team B5):** `cerberus_protected_paths` (`modules/cerberus/`,
   `config/cerberus_limits.yaml`, [cerberus_limits.yaml:45-47](../../config/cerberus_limits.yaml#L45-L47))
   are ALREADY an emergency-shutdown-class trigger — tampering there is the nuclear option,
   not an alert. So the FIM response splits by path, and the trigger decides — no judgment
   call: **(a)** a diff to a `cerberus_protected_path` routes to the EXISTING emergency path
   (do not raise a duplicate/competing "critical alert"; hand off to the emergency-shutdown
   contract); **(b)** a diff to the broader watch-list (other `modules/`, `config/config.yaml`,
   identity files) raises a **critical Harbinger alert**, report-only. Never self-heal a
   changed file in either case.
**Expected observation:** After `fim_baseline_build`, `data/sentinel_baseline.json` is a
non-empty JSON object with one sha256 per watch-list file (row count == file count).
`fim_verify` on an unchanged tree returns `{modified: []}`. A test that touches one byte
of a temp watched file then runs `fim_verify` returns that file in `modified`.
**Most likely failure:** baseline includes volatile files (logs, `__pycache__`, the
heartbeat json, the snapshot db) → `fim_verify` screams every cycle → alert fatigue →
real alerts ignored. **Cause:** watch-list globbed too wide. **Counter:** the watch-list
is an explicit allow-list of *stable* files, never a recursive glob of `data/`; add a
denominator test asserting no path under `data/logs`, `data/*.db`, or `__pycache__` is in
the list.
**Fork:** If **R2** cannot locate identity files (they genuinely don't exist yet — recon
found no `identity/` dir at repo root; the system prompt is loaded from code), FIM still
covers code+config; note identity FIM as **BLOCKED on Master** (where do identity files live
/ should they be created) and continue — do not invent a path. **This BLOCK also propagates
to F3-1's self-audit** (red-team B4): the identity-integrity surface must appear in the audit
report as `status=BLOCKED` with the R2 question, never silently omitted — an audit that drops
the highest-value tamper target reports a false clean posture.
**Abort:** if `fim_verify` would ever *modify* a watched file to "restore" it — stop. FIM
reports; it does not write. Self-healing Shadow's own code is a self-modification and is
out of scope for autonomous action (see Gates ledger).

### Move F1-2 — Malware/rootkit defense: install the tools, integrate as PROPOSALS
Host has zero AV/rootkit tooling (all ABSENT).
**Do:**
1. **Installation is a gated host action** (`software_install` is `never_autonomous`,
   [cerberus_limits.yaml:199](../../config/cerberus_limits.yaml#L199)). Enqueue a
   `decision_queue_add` proposal listing exactly what to install: `clamav clamav-daemon`
   (signatures + `clamscan`), `rkhunter`, `chkrootkit`, `aide`. The executor does NOT run
   `apt install` autonomously.
2. Once Master approves and installs (Master's turn), add a `malware_scan` operation that
   shells `clamscan` over `data/research/quarantine/` and `data/downloads/` (the untrusted
   ingress dirs) and a `rootkit_check` that shells `rkhunter --check --sk`. Both are
   **read-only scans**; a detection **proposes** quarantine via the F5-2 path, never
   auto-quarantines.
**Expected observation:** proposal row appears in `decision_queue_read` with the exact
package list. Post-approval, `clamscan --version` succeeds; `malware_scan` on a directory
containing the EICAR test string returns a detection; `rootkit_check` returns a parsed
summary. Test `test_malware_scan_parses_clamscan_output` uses a captured clamscan output
fixture (not a live scan) and asserts the detection is parsed and routed to a proposal.
**Most likely failure:** `clamscan` invoked with unsanitized path params → shell-metachar
risk, or the ClamAV daemon isn't running so first scan is cold/slow (minutes). **Cause:**
subprocess argument handling / no `freshclam` DB. **Counter:** use `subprocess.run([...],
shell=False)` with list args (the pre_tool `shell_metacharacters` deny only covers
`bash_execute`/`code_execute`, [cerberus_limits.yaml:145-147](../../config/cerberus_limits.yaml#L145-L147),
so the security surface must sanitize its own subprocess args); run `freshclam` (also a
gated install-class action) before first scan; document expected first-scan latency.
**Fork:** If Master declines the install (**trigger:** `decision_queue_resolve` returns
`rejected`), malware defense degrades to "quarantine-dir hygiene + FIM only" — record
that as a known residual in the ledger; do not attempt to hand-roll a scanner.

### Move F1-3 — Wire quarantine as the detection sink (it exists; connect it)
`_quarantine_file` is live but nothing feeds it ([core.py:543-598](../../modules/cerberus/security/core.py#L543-L598)).
**Do:** Make F1-2's detections and FIM's flagged files route to a **proposed** quarantine
(F5-2 gate). On approval, the quarantine move runs inside a reversibility snapshot
([cerberus.py:1296-1326](../../modules/cerberus/cerberus.py#L1296-L1326)) so it is
reversible. Never delete — quarantine only (aligns with hard limit "never delete without
backup", [cerberus_limits.yaml:20](../../config/cerberus_limits.yaml#L20)).
**Expected observation:** an approved quarantine moves the file to
`data/research/quarantine/`, writes the `.meta.json` sidecar ([core.py:574-583](../../modules/cerberus/security/core.py#L574-L583)),
and a matching snapshot row exists in `data/snapshots/cerberus_snapshots.db`. Rollback
restores the file. Test `test_quarantine_is_reversible` proves move + rollback round-trip.
**Most likely failure:** `shutil.move` across filesystems (repo on NVMe, quarantine
elsewhere) or a snapshot taken *after* the move (nothing to roll back to). **Cause:**
ordering. **Counter:** snapshot BEFORE move; assert the snapshot exists before the move
call in the test.

### Move F1-4 — Network posture: keep read-only monitoring; firewall stays PROPOSE-only
`psutil.net_connections` is read-only and fine ([core.py:232](../../modules/cerberus/security/core.py#L232));
firewall generate is text-only ([analyzer.py:1587+]).
**Do:**
1. Grade Citadel's *current* firewall (pending **R3**): feed the live ruleset into
   `firewall_evaluate` ([analyzer.py:397-644]) → letter grade + findings.
2. `firewall_generate` proposes an improved nftables/ufw ruleset **as text**, routed to
   `decision_queue_add`. **A new `firewall_apply` is `never_autonomous` (added in F5-1)**
   and only ever runs on Master's turn, inside a config snapshot, with the exact
   `nft`/`ufw` command shown in the proposal.
**Expected observation:** `firewall_evaluate` returns a grade for the real ruleset (or, if
R3 shows no active firewall, grade "F — no active firewall" with a proposed baseline
default-deny ruleset). The proposed ruleset is valid syntax (`nft -c -f <file>` dry-run
check passes — itself read-only). No rule is applied without approval.
**Most likely failure:** generated ruleset locks out Citadel's own SSH / Ollama / Langfuse
ports → Master approves a self-DoS. **Cause:** generator doesn't know Citadel's required
inbound/outbound. **Counter:** the proposal must enumerate currently-listening ports
(from the psutil read) and preserve them; `nft -c` dry-run must pass; the proposal
explicitly lists what it will block. **Abort:** never propose a ruleset that drops the
loopback or the port Shadow's own services bind — flag instead.

---

## FRONT 3 — Red-team Shadow itself (white-hat self-assessment)

### Move F3-1 — A standing, repeatable self-audit of Shadow's own attack surface
**Do:** Build `shadow_self_audit` (extends the existing `threat_shadow_assessment` stub,
[core.py:777-783](../../modules/cerberus/security/core.py#L777-L783)) that enumerates
Shadow's real surface and runs one concrete defensive check per item:

| Surface | Concrete check the audit runs |
|---|---|
| Reaper web ingress → Grimoire | Confirms Part-2 injection mitigations are live (recall `min_trust` floor enforced; untrusted content wrapped). Until Part 2 lands, this item reports **FAIL — highest severity**. |
| Grimoire write path | Confirms no caller writes creator-trust (≥0.9) from an untrusted `source_module`; greps recall sites for missing `min_trust`. |
| `.env` secrets | Confirms `.env` is gitignored, not world-readable (`stat -c %a`), and never logged (grep logs for token patterns). |
| Telegram/Discord tokens | Confirms tokens are `SecretStr`, redacted in `repr`/`model_dump_json` (per CLAUDE.md config rules). |
| MCP tool surface (Grimoire/Reaper HTTP) | Confirms the external MCP servers bind localhost only, not `0.0.0.0`. |
| Identity / system-prompt | **BLOCKED on R2** — no `identity/` dir exists; system prompt is code-loaded. Reports `status=BLOCKED` with the R2 question to Master (where identity lives / whether to externalize it for FIM). Never silently omitted (red-team B4). |
| Host | Runs FIM verify + (if installed) rootkit check summary. |

**Output:** a **posture report** routed through Harbinger (`safety_report` /
`decision_queue` for findings needing action), findings ranked by severity, each with a
proposed fix. **Every fix that touches Shadow's code/config is a PROPOSAL, gated behind
Master — the audit never self-patches.**
**Expected observation:** `shadow_self_audit` returns a structured report with one entry
per surface, each `{surface, status: PASS|FAIL, severity, evidence, proposed_fix}`.
Running it twice with no change yields identical findings (repeatable). The Reaper-ingress
item is FAIL until Part 2 is live. A test asserts the report contains all **seven** surfaces
(including the BLOCKED identity row) and that no audit path writes to `modules/` or `config/`.
**Most likely failure:** the audit *reads* a secret to check it (e.g. opens `.env`) and
that value lands in the report or logs → the audit becomes the leak. **Cause:** checking
presence by reading content. **Counter:** check secrets by metadata only (file mode,
gitignore membership, `SecretStr` type) — never read or echo the value; add a test that
greps the report for known token prefixes and asserts absent.
**Abort:** if any self-audit check would itself perform a state change (e.g. "test" the
injection defense by actually writing a poisoned memory into the live Grimoire) — stop.
Self-audit is read-only; adversarial *tests* run against a throwaway Grimoire in Part 2,
never the live DB.

---

## FRONT 4 — Detect, decide, respond (the live loop) + dead-man's switch

### Move F4-1 — The monitor→detect→assess→decide→act/alert loop
No monitoring loop exists today.
**Do:** Add a Sentinel monitor loop (a systemd `--user` timer or an async task owned by
Cerberus — match the existing daemon pattern under `daemons/`) that on each tick runs the
**read-only, non-destructive** set: `fim_verify`, `psutil` connection snapshot, quarantine-dir
hygiene, and (if installed) a scheduled `malware_scan`/`rootkit_check`. Results feed
`threat_assess` ([core.py:476-541](../../modules/cerberus/security/core.py#L476-L541)) for
a severity score.
**The autonomy split is the load-bearing decision:**
- **Autonomous (provably safe, read-only):** log the finding, raise a Harbinger alert,
  write the finding to Grimoire at `source_module="cerberus.security"` trust.
- **Gated (Master-in-loop):** anything that quarantines, applies a firewall rule, kills a
  process, or writes to the host → `decision_queue_add` proposal (F5-2). A detection
  response that can itself cause harm is **not** autonomous.
**Expected observation:** one loop tick produces a log line + (on a planted change) a
Harbinger alert, and takes zero host-mutating action. Test `test_loop_tick_is_readonly`
spies every host-mutating function and asserts call count 0 across a tick with a planted
FIM change (the change yields an *alert + proposal*, not an auto-quarantine).
**Most likely failure:** the loop's `malware_scan` blocks the tick for minutes → ticks
pile up / overlap. **Cause:** synchronous long scan on the monitor cadence. **Counter:**
long scans run on their own slower cadence (e.g. daily), decoupled from the fast
FIM/connection tick; guard against overlapping runs with a lock file.

### Move F4-2 — Decision logic as an explicit, testable table
**Do:** Encode the autonomous-vs-gated split as a static table keyed by response type,
mirroring `cerberus_limits.yaml` classification, so the loop never makes an ad-hoc call.
`{alert, log, grimoire_write} → autonomous`; `{quarantine, firewall_apply, process_kill,
host_write} → gated`.
**Expected observation:** `test_response_classification` iterates every response type and
asserts autonomous ones never enqueue and gated ones always enqueue + never execute inline.
**Most likely failure:** a new response type added later defaults to autonomous. **Cause:**
default-allow. **Counter:** the table is default-**deny**: an unknown response type is
gated, not autonomous. Assert with an unknown key in the test.

### Move F4-3 — Sentinel's own dead-man's switch (the SearXNG-dead-for-months lesson)
If the security loop goes silent, that silence must alert. **Do NOT copy the Cerberus
heartbeat as an exemplar — R4/red-team B8 settled that it is broken** (fires only inside
`safety_check`, so an idle Shadow goes stale). Build a genuinely periodic writer.
**Do:** The monitor loop writes its own heartbeat `data/sentinel_heartbeat.json` **on every
tick, unconditionally** (not gated behind any check running). Add a watcher — extend the
external `cerberus_watchdog` structure ([daemons/cerberus_watchdog/watchdog.py:71-92]) or a
sibling — that reads that file; staleness beyond N ticks → Harbinger **critical** alert
("security monitoring is down"). The watcher only ALERTS; it must never `pkill` on Sentinel
staleness (unlike the Cerberus watchdog's kill path — see F4-6).
**Expected observation:** `test_sentinel_heartbeat_is_loop_driven` runs the loop idle-but-alive
for several ticks and asserts the heartbeat timestamp advances each tick (proving it is NOT
gated behind activity — the bug that breaks the Cerberus exemplar). `test_stale_sentinel_heartbeat_alerts`
fakes an old timestamp and asserts the critical alert fires and NO process kill occurs.
**Most likely failure:** the watcher watches a heartbeat nobody writes (the exact SearXNG-dead
failure) → permanent false "down" or permanent silence. **Cause:** writer not actually wired
to the loop, or watcher disabled by config default. **Counter:** a first-class test that (a)
proves the loop writes a fresh heartbeat each tick and (b) proves the watcher reads *that*
file; and confirm the watcher's `enabled` default is true, not the
Morpheus-style opt-out.
**R4 SETTLED:** the Cerberus heartbeat is NOT loop-driven (fires in init + `safety_check`
only) — so it is NOT reused as an exemplar; Sentinel's writer is independent and periodic.

### Move F4-4 — Reuse, don't reinvent, the watchdog escalation
**Do:** Route Sentinel-down to the same emergency-alert path Cerberus-down uses; do not
build a parallel escalation. Keep one escalation spine. **But** Sentinel-staleness must map
to ALERT-only, not the Cerberus watchdog's `pkill` kill path — a silent security monitor is
a reason to notify Master, not to kill Shadow.
**Expected observation:** grep shows a single escalation entry point handling both
heartbeats; no duplicate alert code path; the Sentinel branch reaches alert, never `pkill`.
**Most likely failure:** duplicate escalation drifts (one gets fixed, the other rots), OR the
shared spine applies Cerberus's kill semantics to Sentinel staleness. **Counter:** single
function, two callers, per-caller severity (Cerberus-down → existing kill/lockdown;
Sentinel-down → alert); test both callers hit it and assert Sentinel-down does not kill.

### Move F4-6 — Flag the pre-existing Cerberus heartbeat bug (R4/B8) as a Master proposal
Recon settled that the EXISTING Cerberus heartbeat is not loop-driven, so an idle Shadow can
go stale and the existing `cerberus_watchdog` would `pkill` a healthy process. This is a
pre-existing latent bug outside Sentinel's build, but Sentinel's self-audit surfaced it, so
it must not be swallowed.
**Do:** File a `decision_queue` proposal (not an autonomous fix — it touches Cerberus's own
lifecycle) recommending the Cerberus heartbeat be driven by a periodic task rather than
`safety_check`, with the exact file:line ([cerberus.py:238,1070](../../modules/cerberus/cerberus.py#L1070)).
**Expected observation:** a proposal row exists describing the idle-stale → false-kill risk;
no code change is made by Sentinel to Cerberus's lifecycle.
**Most likely failure:** the executor "helpfully" fixes Cerberus's heartbeat inline. **Cause:**
scope creep. **Counter:** this is a proposal only; Cerberus lifecycle changes are Master's
call (and touching `modules/cerberus/` is a `cerberus_protected_path`). Assert no edit to
`cerberus.py` from this move.

---

## Abort conditions (stop and flag — do not improvise)

1. **LIVE-PATH GATE ABORT (the one that would have caught B0).** If `module.execute(<any
   host-mutating security tool>)` — driven through the real Step-5 dispatch OR a direct
   `cerberus.execute(...)` as the monitor loop makes — reaches `shutil.move`/`nft`/`pkill`
   without first hitting the F5-0 gate (spied mutating-fn call count > 0 with no approval
   token), STOP. A green `safety_check`/classifier test does NOT satisfy this; the assertion
   must be on the live dispatch.
2. **Any host-mutating action reached without its gate.** If quarantine/firewall-apply/
   process-kill/host-write executes without an F5-0b `approval_request` + `decision=="approved"`,
   STOP.
3. **FIM or self-audit about to WRITE to Shadow's own code/config to "fix" it.** Report-
   only is the invariant. Self-healing is out of scope. STOP.
4. **FIM response to a `cerberus_protected_path` diff is ambiguous** (both a "critical alert"
   AND emergency-shutdown could fire). If the executor cannot cleanly route protected-path
   diffs to the EXISTING emergency path and broader-watch-list diffs to alert-only (F1-1
   step 3), STOP and flag — do not ship two competing responses to the same event.
   **Event-model note (pass-2 P4):** FIM produces a POST-HOC hash diff (the change already
   happened); `EmergencyShutdown` ([emergency_shutdown.py:244-254](../../modules/cerberus/emergency_shutdown.py#L244-L254))
   is a PRE-WRITE intercept keyed on the `target_path` of an *intended* write. They are different
   event models — a FIM diff cannot be fed into the pre-write trigger without an adapter. So the
   protected-path FIM response is a DISTINCT "post-hoc tamper detected" critical alert (escalated
   like, but wired separately from, the pre-write emergency intercept). Do not pretend the FIM
   diff plugs into the pre-write path; if it can't be cleanly separated, STOP (Abort #4).
5. **An adversarial test about to run against the live Grimoire / live host.** Tests use
   throwaway fixtures. STOP.
6. **A firewall proposal that would drop loopback or a port Shadow's own services bind.**
   Flag, do not propose.
7. **The F5-0 live-path gate cannot be made to block a never-autonomous security tool at
   `module.execute`.** The gate layer is not trustworthy → STOP the whole autonomy expansion;
   an ungoverned Sentinel is more dangerous than a weak one (brief constraint).
8. **Benchmark regression below the 78.18% Phase-0 floor** after wiring (CLAUDE.md rule).
   STOP and investigate before proceeding.
9. **Reaper→Grimoire ingress (Tier-2 web autonomy) about to be enabled while Part 2's
   injection defense is not live.** That is the load-bearing sequencing gate — STOP.

---

## Verification runs (built is not done; live-verified is done)

Run each after its move; the mission is done only when all pass live.

| # | When | Run | PASS looks like |
|---|---|---|---|
| **V0** | After F5-0 | `pytest -k quarantine_ungated_dispatch_is_blocked` (spies `shutil.move`; drives BOTH `cerberus.execute("quarantine_file",…)` and a full Step-5 dispatch) | `shutil.move` call count **0** in BOTH; ToolResult pending/blocked; **F5-0 live-path abort NOT triggered** |
| **V0b** | After F5-0b | `pytest -k approval_requires_token -k source_is_not_param_spoofable -k nonce_is_single_use -k gated_tool_respects_decision` | `approved` requires the secret creator token; a planned `{"source":"user_input","decision":"approved"}` param does NOT self-approve (source bound at ingress); nonce is single-use (replay refused); tool runs only on approved+valid-nonce; `resolve()` performs no host action |
| **V0c** | After F5-0 step-1 | `pytest -k nonsecurity_host_tool_blocked_via_step1 -k static_token_does_not_open_gate` | a never-autonomous NON-security tool (software_install) does not execute via Step-5 (APPROVAL_REQUIRED routes to approval, not module.execute); a replayed/static token does not open the step-2 gate |
| V1 | After F5-1 | rerun `-k quarantine_ungated_dispatch_is_blocked` with `quarantine_file` in `never_autonomous`, then removed | in-list → move count 0 + APPROVAL_REQUIRED; removed-from-list → test goes RED (proves the list entry is what gates) |
| V2 | After F5-2 | `pytest -k gated_action_enqueues_not_executes` | queue +1 (an `approval_request`) AND mutating-fn call count 0; host unchanged |
| V3 | After F5-3 | `pytest -k defense_only_rejects_external_target` | external target refused; localhost allowed; loops over all `SECURITY_TOOLS`; `TARGETS_A_HOST` set justified per-tool (not prose) |
| V4 | After F5-4 | `grep -rn 'C:/Shadow\|C:\\Shadow' modules/` ; `pytest -k default_dir_is_relative -k watchdog_defaults_are_relative` | grep **empty** across all of `modules/` (all 4 defaults + generator template); tests green |
| V5 | After F1-1 | `fim_baseline_build` then touch a temp watched file, `fim_verify`; also touch a `cerberus_protected_path` fixture | baseline non-empty (row count == file count); touched file in `modified`; no volatile paths present; protected-path diff routes to emergency path, broader diff routes to alert-only |
| V6 | After F1-2 | post-approval `clamscan --version`; `pytest -k malware_scan_parses` (fixture) | version prints; EICAR fixture detected → proposal, not auto-quarantine |
| V7 | After F1-3 | `pytest -k quarantine_is_reversible` | move + rollback round-trip; snapshot precedes move |
| V8 | After F1-4 | `nft -c -f <proposed_ruleset>` dry-run; confirm listening ports preserved | dry-run OK; loopback + service ports retained; nothing applied |
| V9 | After F3-1 | run `shadow_self_audit` twice | identical findings; all **7** surfaces present (incl. BLOCKED identity row); Reaper item FAIL until Part 2; no write to `modules/`/`config/`; no secret value in report |
| V10 | After F4-1/4-2 | `pytest -k loop_tick_is_readonly` and `-k response_classification` | tick host-mutation call count 0; unknown response type gated (default-deny) |
| V11 | After F4-3/4-4/4-6 | `pytest -k sentinel_heartbeat_is_loop_driven -k stale_sentinel_heartbeat_alerts` | heartbeat advances each idle tick; stale → critical alert AND no `pkill`; single escalation spine; F4-6 proposal filed, no edit to `cerberus.py` |
| V12 | End-state | `python -m pytest tests/test_cerberus*.py tests/test_harbinger.py tests/test_decision_loop.py` then the benchmark | targeted suites green; benchmark ≥ 78.18% |

---

## GATES & AUTONOMY LEDGER (SUCCESS point 9 — the contract Master approves)

Every move that writes to Shadow's own code/memory/config/identity, acts autonomously, or
touches the host/network/another machine, with its gate and the earned-by condition that
lets the gate open. **Capability is planned in full above; here each dangerous move
arrives wearing its lock.**

| # | Move / capability | What goes wrong ungated | Gate (the wired check) | Earned-by condition |
|---|---|---|---|---|
| G0 | **The gate mechanism itself** (F5-0, F5-0b) | The lock is on a door nobody walks through: `never_autonomous` gates only the off-path classifier; `decision_queue` has no approve/reject; and the approval trust signal came from the untrusted LLM planner (red-team B0/B1 + pass-2 P1/P2). | **F5-0** wires `never_autonomous` into `_pre_tool_hook` (step-1, load-bearing for non-security host tools) AND the `SECURITY_TOOLS` branch (step-2); **F5-0b** builds real approve/reject requiring the **secret creator token**, an **authoritatively-bound source** (not a planned param), and a **single-use nonce** to unlock execution | V0 (live `shutil.move` count 0) + V0b (token required; source not param-spoofable; nonce single-use) — **the whole gate front is void until both are green** |
| G1 | `quarantine_file` host move (F1-3, F5-1, F5-2) | Autonomous file move / mis-quarantine of a legit file; today it's ungated | **F5-0 step-2 gate** at the `SECURITY_TOOLS` branch → `approval_request`; runs only on F5-0b approval + single-use nonce **inside a reversibility snapshot** (confirmed by pass-2: every route to `shutil.move` crosses [cerberus.py:488]) | V0 + V1 (list entry gates at `module.execute`) AND F1-3 rollback round-trip (V7) |
| G2 | AV/rootkit tool install (F1-2) | Autonomous `apt install` = unapproved software on host (`software_install` hard limit) | `software_install` is **NOT a `SECURITY_TOOL`** → gated via **F5-0 step-1** (the pre-hook `never_autonomous` rule + fixed `APPROVAL_REQUIRED` handlers), which pass-2 flagged must be made real for this class; F5-0b approval + nonce; install runs only on Master's turn | `test_nonsecurity_host_tool_blocked_via_step1` green (V0) AND Master approves (V0b, V6) |
| G3 | `malware_scan` / `rootkit_check` execution (F1-2) | Long subprocess, unsanitized path args (shell-metachar), false-positive auto-action | Read-only scans, `shell=False` list-args; **detections propose, never auto-quarantine** | Tools installed (G2) AND parse test green (V6) |
| G4 | `firewall_apply` (F1-4) | Self-DoS: lock out SSH/Ollama/Langfuse/loopback | `firewall_apply` is **NOT a `SECURITY_TOOL`** → gated via **F5-0 step-1** (same as G2); `nft -c` dry-run + listening-port preservation + F5-0b approval + nonce **inside a config snapshot** | `test_nonsecurity_host_tool_blocked_via_step1` + V8 dry-run pass + Master approval |
| G5 | FIM baseline write / verify (F1-1) | Baselining volatile files → alert fatigue; or "restoring" a changed file = self-modification | Watch-list is an explicit stable allow-list (no `data/logs`, `*.db`, `__pycache__`); **verify is report-only, never writes a watched file** | Watch-list denominator test green (V5) |
| G6 | Self-audit findings that propose code/config change (F3-1) | Sentinel self-patches Shadow → unreviewed self-modification | Findings are **proposals only**; audit path proven to never write `modules/`/`config/`; fixes go to `decision_queue` for Master's diff review | V9 (no-write assertion) AND Master reviews each diff before it lands |
| G7 | Autonomous alert/log/Grimoire-write in the loop (F4-1/4-2) | A "read-only" response that actually mutates; unknown response type defaults to autonomous | Response classification table is **default-deny**; loop tick proven host-mutation-free | V10 (call count 0; unknown key gated) |
| G8 | Grimoire writes at `source_module="cerberus.security"` (F1/F3/F4 findings) | Security findings stored could be over-trusted or poison recall | Writes use the security source tag at appropriate (non-creator) trust; recall of them respects Part-2 min_trust floor | Part 2 recall floor live (cross-ref) |
| G9 | Defense-only target enforcement (F5-3) | Sentinel scans/probes a system Master doesn't own → crosses the white-hat line | `handle()` choke-point allow-list of owned targets (localhost/Citadel IPs/own repo); external targets refused in code | V3 green across all `SECURITY_TOOLS`; `security.owned_targets` set from `hostname -I` |
| G10 | **Tier-2 web autonomy** (Reaper research pulls scraped content into Grimoire) | Persistent prompt-injection: one poisoned memory poisons every future recall; abliterated model has no refusal backstop | **DORMANT until Part 2's injection mitigations are live AND its adversarial test suite passes** — hard sequencing gate | `sentinel-part2-injection.md` verification V-P2 all green (recall floor enforced + untrusted content wrapped + adversarial corpus 0 executions) |
| G11 | Sandboxing (bubblewrap) + Semgrep static policy | Next gate tier; if skipped, scans/scaffolds run unsandboxed | Planned as the **next gate tier, running WHILE Tier 2 runs** — not a blocker for everything, but required before autonomous code-exec expansion | `bwrap` present (confirmed); Semgrep install is a G2-class proposal |

**Gate-front invariant:** no row's capability is amputated — quarantine, firewall apply,
AV, self-audit, and the full monitor loop are all planned to their intended power. Each
simply arrives already wearing the lock in its Gate column, and none of those locks is
merely named — every one cites the wired check and the verification that proves it holds.

---

## Attack that failed / patch that landed (SUCCESS point 7)

A fresh attacker (`wargames/red-team/sentinel-part1.md`) played the blind executor and
attacked the gate front hardest. It broke the plan on the first hard push. Every break was
verified against source before patching.

**The attack that landed (CRITICAL, B0) — "the lock is on a door nobody walks through."**
The first draft's F5-1 added `quarantine_file` to `never_autonomous` and proved the gate with
a REPL `safety_check` call. The attacker traced the LIVE dispatch and showed `never_autonomous`
is read only by the off-path classifier: the real path is `hook_pre_tool` (which only fires
hardcoded `applies_to` deny rules — no security tool is listed) → `module.execute` →
`SecuritySurface.handle` → `shutil.move`, ungated and unsnapshotted. The draft's own proof
(`test_quarantine_requires_approval`) was a green test guarding a bypassed path — the exact
"looks governed but isn't" failure. **Patch:** new Move **F5-0** wires `never_autonomous`
enforcement into BOTH live choke-points (`_pre_tool_hook` and the `SECURITY_TOOLS` dispatch
branch), and its verification **V0 spies `shutil.move` and asserts call count 0 on the live
`module.execute` path**, not a REPL. New **Abort #1** stops the mission if any host-mutating
tool reaches its mutating call ungated. This break independently matches the parallel Omen
wargame's finding that `APPROVAL_REQUIRED` is a no-op verdict (logged-and-proceeds at
orchestrator.py:4642-4651) — so F5-0's load-bearing enforcement is the branch that returns a
pending ToolResult directly, not any verdict.

**Second landed break (HIGH, B1) — the approval path didn't exist.** The draft routed gated
actions to `decision_queue`, but `_decision_queue_resolve` only sets `status="resolved"` from
free text — no approve/reject — and `CreatorOverride` forbids internal-module callers. "On
approved / returns rejected" described an API that doesn't exist. **Patch:** new Move **F5-0b**
builds a real `decision: approved|rejected` field with external-source auth, and separates
resolution from execution; **V0b** proves the field is real and internal sources are refused.

**Also patched:** F5-2 now pins the interception point (the `SECURITY_TOOLS` branch before
`handle()`) so its own "prove the mutating call is skipped" abort is satisfiable (B2). F5-4
now targets all four real Windows-path defaults (`modules/cerberus/watchdog.py:37-39` +
`reversibility.py:55`) plus the generator template, not the already-clean daemon (B3). F1-1
reconciles the FIM-vs-emergency-shutdown collision on `cerberus_protected_paths` with an
explicit path-split trigger (B5), and marks identity FIM BLOCKED-on-Master (B4). F3-1 adds the
identity-integrity row so the audit can't report a false-clean posture over the highest-value
tamper target (B4). F4-3 no longer copies the broken Cerberus heartbeat exemplar and proves
its own heartbeat is loop-driven; F4-6 (new) files the pre-existing idle-stale→false-kill bug
as a Master proposal (B8). V1's ambiguous "DENY/REQUIRES_APPROVAL whichever" is replaced by a
concrete live-path assertion (B6); `SafetyVerdict` values are settled in recon.

**What the pass-1 attacker could not break:** it conceded F5-3 (defense-only choke-point) is
"directionally good."

### Pass 2 (confirmatory) — the B0 patch HELD; the B1 patch did NOT

A second fresh attacker (`wargames/red-team/sentinel-part1-pass2.md`) attacked the patched plan.

**What held (it attacked this hardest):** F5-0 **step-2** — the gate in the `SECURITY_TOOLS`
branch before `_security.handle`. It chased every route to quarantine's `shutil.move` (async
task queue, direct callers, the monitor loop) and confirmed all funnel through the single caller
at [cerberus.py:488](../../modules/cerberus/cerberus.py#L488). **B0 is genuinely closed for the
security surface.**

**But two HIGH breaks landed on the approval mechanism, plus scope and MEDIUM issues:**
- **P1 (HIGH) — the trust signal was spoofable.** F5-0b's "only an external source may approve"
  read `params["source"]`, but nothing binds the true source — LLM-planned params pass straight
  through, so an internal module (or an injected instruction) can emit
  `{"decision":"approved","source":"user_input"}` and self-approve. `CreatorOverride` is safe
  only because it ALSO requires the secret token; I mirrored only the source half. **Patch:**
  F5-0b now requires the **secret creator token**, binds `source` **authoritatively at ingress**
  (not from params), and mints a **single-use nonce**; new tests
  `test_approval_requires_token` / `test_source_is_not_param_spoofable` / `test_nonce_is_single_use`.
- **P2 (HIGH) — the step-2 open-condition was an unspecified token.** If static, the untrusted
  planner replays it and re-opens B0. **Patch:** the open-condition is the F5-0b single-use
  nonce, never a static sentinel; `test_static_token_does_not_open_gate`.
- **Ledger scope (important).** Step-2 covers only the 24 `SECURITY_TOOLS`; `software_install`
  and `firewall_apply` are NOT security tools, so they ride **step-1** — the verdict path the
  draft told itself not to trust. **Patch:** F5-0 makes step-1 load-bearing for that class (fix
  both `APPROVAL_REQUIRED` handlers), with `test_nonsecurity_host_tool_blocked_via_step1`; G2/G4
  re-cite step-1.
- **P3 (MEDIUM):** V4's grep was blind to the generator's double-backslash `C:\Shadow`. **Patch:**
  case-insensitive backslash-class grep + a behavioral `test_generated_claudemd_uses_linux_venv`.
- **P4 (MEDIUM):** F1-1 fed a post-hoc FIM diff into `EmergencyShutdown`'s pre-write intercept —
  different event models. **Patch:** the protected-path FIM response is a distinct "post-hoc
  tamper" alert, wired separately from the pre-write path.
- **P5 (MEDIUM):** F5-3/V3 was vacuous — no current `SECURITY_TOOL` takes a host target. **Patch:**
  F5-3 is marked forward-looking; the test uses a synthetic host-targeting tool, and asserts
  `TARGETS_A_HOST` is empty today (dormant-but-wired), instead of "refusing" tools that ignore
  the target.

**What the pass-2 attacker could not break:** the step-2 security-surface gate — it confirmed no
route reaches the host without crossing it. That leg is DONE; the approval-authority leg needed
the token/nonce/source-binding patch above.

### Pass 3 (confirmatory) — the approval-authority leg is an architecture decision, not a paper-patch

A third fresh attacker (`wargames/red-team/sentinel-part1-pass3.md`) attacked the pass-2 approval
patch and landed a CRITICAL + a HIGH — both proving the approve/reject MECHANISM is now correct
but its TRUST SIGNAL is unbindable in Shadow's current architecture:
- **CRITICAL — "source bound authoritatively at ingress" is wired to nothing.** `process_input`'s
  `source` is a spoofable default arg, `main.py:726` passes none, and `decision_queue_resolve` is
  a routed tool whose params are LLM-planned — the same "named but not wired" defect as the first
  draft, moved up a layer. AND `CREATOR_AUTH_TOKEN` is unset on Citadel, so the token path raises.
  **Response: NOT a further paper-patch — escalated to the ARCHITECTURE RESIDUAL / BLOCKED section
  above (AR-P1-1: an out-of-band authenticated approval channel; token provisioning is
  BLOCKED-on-Master).** The gated host actions stay dormant until Master decides the channel and
  provisions the token.
- **HIGH — the single-use nonce leaks to the planner.** `decision_queue_read` (autonomous routed
  tool) returns raw items unredacted, so the planner can read the nonce and replay it as the FIRST
  use. **Patched (buildable): F5-0b now requires the nonce/token be redacted from every
  model-visible surface; `test_nonce_not_in_model_visible_read` asserts it.**

**What the pass-3 attacker could not break:** the step-2 security-surface gate again (re-confirmed
the `shutil.move` funnel and the graph-routed async path hold), and the step-1 chokepoint
placement (structurally correct — the failure was downstream in the authority, now escalated).

**Honest terminal state (Part 1):** the READ-ONLY posture and the gate CHOKE-POINTS are wargamed
and buildable; the GATED HOST ACTIONS are correctly gated in placement but their approval
AUTHORITY is BLOCKED on an architecture decision + a Master-provisioned token. Three passes drove
this from "gate is theater" → "gate placement is solid, authority needs an authenticated channel."
The red-team loop is stopped here: pass 4 would re-find the same architecture gap.
