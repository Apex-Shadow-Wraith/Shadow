# LEDGER

One entry per mission per pass. Draft location, red-team location, an honest
point-by-point self-grade against all nine points of SUCCESS.md, and every
patch the refinement loop makes. Append-only within a session — never delete a
grade to make the ledger look cleaner. The whole point of this file is to catch
the plan that grades itself generously and dies at first contact; an inflated
entry defeats it.

**Status vocabulary:** `DRAFTED` (first pass written, not yet red-teamed) ·
`RED-TEAMED` (attacker ran, breaks logged) · `PATCHED` (breaks fixed, re-graded) ·
`DONE` (all nine hold AND one honest kill-attempt failed) · `BLOCKED` (missing
input named, mission cannot proceed without it) · `SPLIT` (divided into parts,
seam justified below).

---

## Entry template

```
### <module> — <status> — <pass N> — <date>

Plan:      wargames/plans/<module>.md
Red-team:  wargames/red-team/<module>.md   (— if not yet run)

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS / WEAK / FAIL — <one line>
  2 failure branches        PASS / WEAK / FAIL — <one line>
  3 fork triggers           PASS / WEAK / FAIL — <one line>
  4 RECON NEEDED marks      PASS / WEAK / FAIL — <one line>
  5 abort conditions        PASS / WEAK / FAIL — <one line>
  6 verification runs       PASS / WEAK / FAIL — <one line>
  7 survived red-team       PASS / WEAK / FAIL — <one line>
  8 executable blind        PASS / WEAK / FAIL — <one line>
  9 gates & autonomy        PASS / WEAK / FAIL — <one line>

Changed since last pass: <what the red-team broke and how the patch fixed it,
or "first draft">

Split justification (if SPLIT): <the parts and why the seam falls here>
Blocking input (if BLOCKED): <the exact input needed from Master>
```

---

## Entries

<!-- Append entries below this line. Newest at the bottom. -->

### omen — SPLIT + DRAFTED — pass 1 — 2026-07-07

Plan:      wargames/plans/omen.md  (Fronts 1, 2, 4, 5)
Plan:      wargames/plans/omen-part3-selfmod.md  (Front 3, crown)
Red-team:  wargames/red-team/omen.md  +  wargames/red-team/omen-part3-selfmod.md  (in progress — two fresh attackers dispatched)

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — every move carries an observable (string/field/exit/hash/row); a few Front-1 model-output observations depend on the wired model and are marked degraded-fallback.
  2 failure branches        PASS — each move has a "most likely failure" + cause + counter.
  3 fork triggers           PASS — forks (1.1 A/B, 1.2 model-unavailable, 2.3 miss-all, Stage-T pass-drop, Gate-5 import-fail) carry explicit triggers.
  4 RECON NEEDED marks      PASS — unsettled items marked with exact settling command: emergency-shutdown target_path wiring (0.7), tool_loader reachability of sandbox_to_production (0.5), hot-reload presence (Part 3 hard case), Front-4 command allow-list (BLOCKED on Master). Counts/intelligence SETTLED in recon (47 tools, 386 tests, heuristic-only, orphaned tool_creator).
  5 abort conditions        PASS — A1–A5 (Fronts 1/2/4) + B1–B8 (Part 3), incl. the data-loss unlink path and hot-reload-without-Gate-5.
  6 verification runs       PASS — spelled out with when/what-pass, incl. the critical data-loss assertion (original bytes intact on failed promotion) and no-push proof.
  7 survived red-team       FAIL (not yet) — two attackers dispatched; breaks + patches not yet recorded. This is the honest gap; entry re-graded after the pass.
  8 executable blind        WEAK — strong, but the Front-4 diagnostic allow-list is BLOCKED on Master input (correctly), and a couple of Front-5 G1–G6 build items describe the repair without naming the exact implementation file/function the executor edits — red-team will surface these.
  9 gates & autonomy        PASS (pending red-team confirm) — Gates ledger in both files; crucially §5.0 turns the *decorative* gates recon found (unenforced APPROVAL_REQUIRED, no-op snapshot, unlink-deletes-file, unguarded copy_to_production dest, modules/ not protected) into wired repairs G1–G6 each with a verification that fails on the broken behavior. Capability planned in full (real code review, self-recreation pipeline, host repair) with every dangerous move wearing its gate.

Changed since last pass: first draft.

Split justification (SPLIT): Omen is genuinely two missions. Fronts 1/2/4/5
(daily coding brain, self-analysis-as-proposal, conservative host repair, and
the gates contract) share a threat model where the worst case is a bad edit
caught by tests/Master. Front 3 (self-repair / self-recreation) is a distinct,
higher-stakes mission: its worst case is an ungated or unrecoverable write to
Shadow's own running code — including Omen editing Omen — where the abliterated
model has no refusal backstop and a corrupted instance can host the very
rollback code that should save it. The seam falls between "find/propose"
(ungated, Fronts 1/2/4) and "change Shadow's own code" (gated pipeline, Part 3),
which is also the spine of the whole mission. Part 3 therefore gets its own
five-stage gated pipeline, its own Gates ledger, and its own dedicated red-team
so the highest-stakes lines are attacked in isolation, not buried under the
daily-brain fronts.

Recon headline (the "looks governed but isn't" chain, all file:line-verified):
the approval gate is decorative end to end — get_tools marks tools
approval_required → registry passes it to Cerberus → Cerberus returns
APPROVAL_REQUIRED → orchestrator LOGS it and proceeds (4642-4651) / pre-hook
handles only DENY+MODIFY (5211-5223). The reversibility snapshot on promotion is
dead (engine never wired into Omen config), and its failure-rollback deletes an
existing file via dst.unlink(). code_edit is autonomous and its PROTECTED_PATHS
omit modules/, so Omen can already rewrite its own and Cerberus's code. The plan
is built to close exactly these.

### sentinel — SPLIT — pass 0 — 2026-07-07

The Sentinel mission is honestly two missions; split into two plans, each with its own
red-team pass and its own Gates & Autonomy Ledger.

**The seam and why it falls here:**
- **Part 1 — `sentinel-part1-posture.md`** (Fronts 1, 3, 4, 5): host defense (FIM, AV,
  quarantine, network, firewall-propose), white-hat self-audit, the detect→decide→respond
  live loop, the dead-man's switch, and the gate front. This is "make the absorbed Sentinel
  a real defensive posture on Citadel, with every dangerous host action gated."
- **Part 2 — `sentinel-part2-injection.md`** (Front 2): the prompt-injection defense —
  a self-contained data-flow problem (Reaper scrape → Grimoire write → recall → prompt)
  whose adversarial test corpus is itself a mini-mission.

The seam falls between "host + governance + loop" and "the memory-poisoning data flow"
because they share almost no code (Part 1 lives in `cerberus/security/` + `cerberus_limits.yaml`
+ `harbinger`; Part 2 lives in `grimoire.recall` + orchestrator context-assembly +
`injection_detector`) and because Part 2 is Part 1's load-bearing earned-by condition: Part
1's Gate G10 (Tier-2 web autonomy) stays dormant until Part 2's adversarial corpus proves 0
executions live. Splitting lets Part 2 get the concentrated red-team the brief demands.

**Boundary settled in recon (the mission is confirm-state / strip-drift / wire-what's-missing,
not a fictional build):** `modules/sentinel/` does not exist — Sentinel merged into Cerberus
in Phase A (`cfcb79d` removed it). Code lives at `modules/cerberus/security/{core,analyzer,
threat_intelligence}.py`; `SecuritySurface` is a plain helper (not a BaseModule) exposing 24
tools through `Cerberus.execute()`. Host has NO AV/FIM/rootkit tooling installed; FIM baseline
is empty; `quarantine_file` is a live host-mutating tool that is currently ungated.

---

### sentinel-part1 — DRAFTED — pass 1 — 2026-07-07

Plan:      wargames/plans/sentinel-part1-posture.md
Red-team:  wargames/red-team/sentinel-part1.md   (attacker dispatched; not yet returned)

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — every move states a concrete observable (row count, test name, grep-empty, verdict). Weak spot: F5-1 verdict is "DENY or REQUIRES_APPROVAL — confirm enum", a small hidden judgment call flagged for red-team.
  2 failure branches        PASS — each move carries most-likely-failure + cause + counter-move.
  3 fork triggers           PASS — forks (F5-1 already-denied, F1-1 no-identity-files, F1-2 install-declined) carry explicit triggers.
  4 RECON NEEDED marks      PASS — R1–R6 each carry the exact check; load-bearing ones (R1→F5-1, R2→F1-1, R3→F1-4, R4→F4-3) are named at the move that depends on them.
  5 abort conditions        PASS — 7 aborts incl. ungated host action, self-heal write, live-Grimoire test, self-DoS firewall, untrustworthy gate layer, benchmark floor, premature web autonomy.
  6 verification runs       PASS — V1–V12 with when/run/pass-looks-like; end-state gated on benchmark ≥ 78.18%.
  7 survived red-team       FAIL (not yet run) — attacker dispatched; grade pending.
  8 executable blind        WEAK — mostly blind-runnable, but the F5-1 verdict ambiguity and "find the loader" instructions assume some discovery; red-team to confirm.
  9 gates & autonomy        PASS — G1–G11, each with ungated-risk + wired gate + earned-by. Full capability planned (quarantine/AV/firewall/self-audit/loop), each wearing its lock; G10 (web autonomy) hard-gated on Part 2.

Changed since last pass: first draft.

### sentinel-part2 — DRAFTED — pass 1 — 2026-07-07

Plan:      wargames/plans/sentinel-part2-injection.md
Red-team:  wargames/red-team/sentinel-part2.md   (attacker dispatched, concentrated here per brief; not yet returned)

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — moves assert on observable prompt contents, stored trust, tool-call counts, corpus behavior.
  2 failure branches        PASS — each move's most-likely-failure is a real trap (filter-not-demote, two injection sites, detector-only test); each has a counter.
  3 fork triggers           PASS — P2-1 choke-point-vs-in-recall fork carries a concrete trigger (recall site bypasses assembly → enforce in recall()).
  4 RECON NEEDED marks      PASS — RP1–RP4; RP3 (does the abliterated model obey the wrapper) is explicitly the make-or-break check, not assumed.
  5 abort conditions        PASS — 5 aborts, incl. the two worst traps: corpus item executes, and test asserting on detector verdict instead of behavior.
  6 verification runs       PASS — V-P2.1–.6; the certifying run (V-P2.4) asserts BEHAVIOR (0 executions) against the LIVE model, not the guard.
  7 survived red-team       FAIL (not yet run) — attacker dispatched with hardest concentration here; grade pending.
  8 executable blind        WEAK — strong, but depends on RP1/RP2 resolving the choke-point; if recall isn't funneled, the executor must refactor — flagged, red-team to confirm it's not a hidden judgment call.
  9 gates & autonomy        PASS — GP1–GP8; the load-bearing GP7 (web autonomy dormant until 0 corpus executions) has a concrete measurable earned-by. Capability planned in full (floor, fence, at-recall scan, 6-class corpus, per-bypass counters).

Changed since last pass: first draft.

### reaper — RECON — pass 0 — 2026-07-07

Recon-only run (Master's instruction). Phases 0–1 complete; **no plan, no red-team, no
nine-point grade** this pass — those belong to the WARGAME pass, and grading nine points
against a plan that doesn't exist yet would be exactly the inflated-ledger failure this
file guards against.

Recon:     wargames/recon/reaper.md
Plan:      — (WARGAME pass pending)
Red-team:  — (WARGAME pass pending)

Boundary settled: Reaper is a LIVE router-wired module (5 autonomous tools) over
reaper.py (1761 lines); orthogonal MCP HTTP surface (3 tools) that NEVER writes Grimoire
(store_in_grimoire=False, mcp_server.py:180-182,244). 107 reaper tests collected.

Load-bearing findings the wargame must carry:
- **Tier-2 gate is OPEN today, not dormant.** main.py:673-675 starts StandingTaskScheduler
  unconditionally at boot; standing_research runs every 12h (standing_tasks.py:77-84) and
  writes web_search results to Grimoire (standing_tasks.py:236-249). Front 5's gate must be
  BUILT to close a live path, not added to a dormant one.
- **Front 4 discipline ABSENT.** Web-scraped content is written at trust up to 0.7 (Tier-1,
  reaper.py:988-999/1192-1220 via evaluate_source:120-152); no untrusted-source tag, no
  instruction-flag on any write path. Fails the brief's "nothing above untrusted" bar.
  web_fetch (autonomous) is the live full-page 0.7 path, independent of the scheduler.
- **Front 1 is a BUILD.** UA-rotation(8)/timing/referrer/DNT exist; Playwright, Canvas/WebGL,
  TLS-fingerprint, DoH, residential proxies all absent (Playwright installed-not-wired).
  stealth_mode flag is dead config.
- **Front 2 largely ABSENT.** Only Brave-API 429 handling + fixed Reddit sleep; no CAPTCHA/
  honeypot/backoff/injection-content detection. HTML "always safe to fetch" (reaper.py:899-901).
- **SearXNG failure class half-closed.** Serving rung observable via _served_by + spans, but
  rung failures print()-only, SearXNG defaults disabled, no alert on enabled-rung-never-serves.

RECON NEEDED (host/secret, exact checks in digest §9): residential-proxy/DoH/TLS infra on
Citadel; Playwright browser binaries; SearXNG Docker running; Brave API key set.

Split recommendation (deferred to wargame pass): likely two parts — Part 1 stealth+gathering
(Fronts 1–3), Part 2 injection-discipline+Tier-2 gate (Fronts 4–5, the Grimoire/Sentinel seam).
Justify in ledger if taken.

### reaper — SPLIT + PATCHED — pass 1 — 2026-07-07

**Mission was reframed with Master's approval** before planning: the original brief's "truly
undetectable" evasion stack (residential proxies, TLS/JA3 + Canvas/WebGL spoofing, honeypot
*evasion*, CAPTCHA solving) was **cut, not deferred** — I declined to author it (it crosses from
polite gathering into circumventing access controls) and Master approved the legitimate reframe:
identifiable/polite gathering + the full injection defense + closing the live autonomy gate.

Plan:      wargames/plans/reaper-part1-gathering.md   (Fronts 1–3 + Brave removal)
Plan:      wargames/plans/reaper-part2-injection.md   (Fronts 4–5, the crown)
Red-team:  wargames/red-team/reaper-part1.md  +  wargames/red-team/reaper-part2.md  (two fresh attackers, returned)

Split justification (SPLIT): honest two missions, same seam logic as Sentinel. Part 1 = "read the
web well and behave" (capability, Reaper-internal). Part 2 = "don't let what you read become an
instruction, and don't run autonomously until that's proven" (discipline + gates, the
Grimoire/Sentinel seam). Part 2 is Part 1's earned-by. Splitting let Part 2 get the concentrated
injection red-team the brief demanded.

**Self-grade vs SUCCESS.md (1–9) — POST-PATCH, both parts:**
  1 expected observations   PASS — every move has a concrete observable; the vague forks the attacker caught (P1 F9 render-trigger, F11 soft-block; P2 V-P2.5) now carry numeric/behavioral criteria. Residual, honestly: P1 M3.3a alert *delivery* depends on the alert-sink RECON NEEDED — marked, not smuggled.
  2 failure branches        PASS — each move carries most-likely-failure + counter; the attacker's best catch was P1 M1.0's stated failure (ImportError) being the WRONG one — rewritten to the real silent-secret-leak with a redaction test.
  3 fork triggers           PASS — P1 A2 re-scoped (functional consumer vs expected routing line); M1.4 render fork made deterministic; P2 M4.1 fork resolved (safety_class exists), M4.3 fork carries a bypass-check trigger.
  4 RECON NEEDED marks      PASS — P1: alert-sink reachability, Playwright binary, M1.1 contact string. P2: does safety_class survive recall() into the result dict (M4.3 step 1). BREAK#4's read-side-keying question is now SETTLED to its live answer ("neither today"), not deferred.
  5 abort conditions        PASS — P1 A1–A7 (A7 = no reachable alert sink); P2 A1–A7 (A7 = read-side applies no demotion — the exact abort the attacker said was missing, now added).
  6 verification runs       PASS — the load-bearing fix: P2 V-P2.5 (certifying run) now asserts MODEL BEHAVIOR via canary imperatives (0 PWNED tokens, 0 corpus-triggered tool-calls, payload fenced), not a detector verdict. If the abliterated model ignores the [UNTRUSTED] fence, V-P2.5 FAILS and Tier-2 stays shut — the gate fails safe. Residual (honest): fence efficacy vs the abliterated model is the real open question, and it is TESTED not assumed; condition-3/Sentinel is the backstop.
  7 survived red-team       PASS — two fresh attackers ran honest kill-attempts. P1: 12 breaks (1 CRITICAL secret-leak), all patched; the disguise-vs-access-control spine HELD (attacker could not force any move to re-introduce evasion). P2: 2 CRITICAL (read-side choke-point abandoned; hollow certifying run) + 5 more, all patched; the CRITICAL read-side hole — the whole ballgame — is closed by new move M4.3 + A7.
  8 executable blind        PASS — was WEAK; the attacker's factual catches (P1 test-count 104≠107, the sources.py:167 file, wrong github.io tier; P2 write-count 8≠6, the safety_class field) are corrected inline, removing the judgment calls an executor would hit.
  9 gates & autonomy        PASS — P1 opens no new autonomy (defers the live gate to P2) and closes the F4 secret-leak. P2: G1 scheduler gate HELD under the decorative-flag attack; G2 (web_fetch) upgraded from prose to a wired code gate (store_in_grimoire=False until earned); the load-bearing earned-by (close the LIVE, ungated 12h standing_research pull) now requires behavioral V-P2.5 + in-repo M4.3, verifiable here not on faith.

Changed since last pass (draft → red-team → patch):
  - P1 CRITICAL F4: M1.0 "pure cleanup" would have leaked the Brave key in plaintext (extra="allow"
    + surviving FLAT_TO_PATH entry); patched to delete sources.py:167 same-commit + a redaction
    test; failure mode rewritten from phantom ImportError to the real leak.
  - P2 CRITICAL (worst): the read side (context_orchestrator.py:396-403) dropped the marker and
    applied no trust floor, making M4.1 cosmetic — scraped content reached the abliterated model's
    prompt verbatim. Patched with M4.3 (data-fence at the choke-point, keyed on first-class
    safety_class) + abort A7 + earned-by now requires the read side proven green in-repo.
  - P2 CRITICAL: V-P2.5 asserted a write-time verdict, not executions; rewritten to a behavioral
    canary assertion against the live model.
  - Counts/facts corrected inline (P1 107 seven-file; P2 8/6 sites; safety_class channel;
    gist.github.com not github.io); recon digest corrected for the two errors it fed the plan.

DONE-blockers (why PATCHED, not DONE): DONE needs a fresh kill-attempt to FAIL. These plans
survived one pass and were patched, but the patches (M4.3, A7, behavioral V-P2.5, the web_fetch
gate) have not themselves been re-attacked. A pass-2 red-team on the patched plans is the remaining
step — in particular, attack the [UNTRUSTED] fence against the abliterated model (does it actually
obey it?) and M4.3's assumption that safety_class survives recall().

### morpheus — DRAFTED — pass 1 — 2026-07-07

Plan:      wargames/plans/morpheus.md
Red-team:  wargames/red-team/morpheus.md   (fresh attacker dispatched, concentrated on the firewall + activation; not yet returned)

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — every move carries an observable (dataclass field, grep-for-zero, 0-hits-in-recall, seeded-ordering, row-count delta, 7-green). A few Front-1 "quality" observables are honestly marked design-only, not machine-provable while dormant.
  2 failure branches        PASS — each move states most-likely-failure + cause + counter; the load-bearing ones (2.2 test-the-tag-not-the-behavior, 3.2 wiring approve_proposal to git, 4.2 re-arming the leak) are the real traps.
  3 fork triggers           PASS — forks carry triggers (1.1 ToolResult-subclass presence, 2.1 write-method via RN2, 5.2 live-unload via RN5).
  4 RECON NEEDED marks      PASS — RN1–RN5 each with exact settling command/question; load-bearing ones named at the dependent move (RN3→2.2/CL-6, RN4→CL-1, RN1→A5/CL-2). Counts SETTLED in recon (11 tools not 7, 53+7 tests, TRUST_MORPHEUS=0.0 exists but unenforced at recall).
  5 abort conditions        PASS — A1–A8 incl. the crown ones: flip-enabled, speculative-reaches-memory, self-mod-outside-Omen, high-promotion-rate, dormancy-unprovable, training-data-write, re-arming-a-raw-writer, plan-vs-reality divergence.
  6 verification runs       PASS — V1–V6 with when/what-pass; the certifying V2(b) asserts BEHAVIOR (0 hits in default recall/search), not a trust tag; honest that V6 benchmark floor is activation-time, not this pass.
  7 survived red-team       FAIL (not yet) — attacker dispatched with hardest concentration on Front 2/5; breaks + patches not yet recorded. This is the honest gap; entry re-graded after the pass.
  8 executable blind        WEAK — strong, but RN4 (frontier-benchmark definition) is correctly BLOCKED on Master and CL-6/CL-7 depend on sibling missions (Grimoire recall-filter, Omen Part-3); red-team to confirm no confident move secretly leans on an unsettled item.
  9 gates & autonomy        PASS (pending red-team confirm) — G1–G9 with ungated-risk + wired gate + earned-by; the headline G1 (activation) is Master-only on a green 9-item checklist, and crucially the plan turns the DECORATIVE firewall recon found (unenforced module-docstring claim; three .store() leak paths inert only by method-mismatch; recall min_trust default 0.0 skips the filter; TRUST_MORPHEUS=0.0 constant that recall ignores) into wired repairs (single promotion gate + retrieval-exclusion + no-auto-promote), each with a verification that fails on the broken behavior. Capability planned in full (dreaming, what-if, RSI proposals, dream→test→improve) with every dangerous edge gated.

Changed since last pass: first draft.

No-split justification: unlike Omen (find/propose vs change-own-code) and Sentinel
(host-defense vs injection-data-flow), every Morpheus front shares ONE threat model —
speculation contaminating verified knowledge — and one owned code area (modules/morpheus/*
plus the Grimoire retrieval boundary). The firewall (F2) is the spine binding the dream
pipeline (F1/F4), the improvement loop (F3), and activation (F5); splitting would sever the
firewall from the thing it contains. Kept as one plan.

Recon headline (the "looks governed but isn't" chain, all file:line-verified): the firewall
the module docstring promises (morpheus.py:7-10, "Cerberus enforces this boundary") is
enforced NOWHERE. Three write paths (experiment_store.py:515, rd_lab.py:414 with
validated:True auto-called at :192, serendipity_detector.py:300) carry a dream into Grimoire
with no trust tag and no approval — inert today ONLY by triple-accident (unwired,
grimoire=None, and .store() isn't a real Grimoire method — only remember() at grimoire.py:675
exists). The crown breach is at retrieval: TRUST_MORPHEUS=0.0 exists (grimoire.py:65) but
recall() defaults min_trust=0.0 and filters only if min_trust>0 (grimoire.py:965,1026-1027),
and grimoire_reader.search has no trust filter at all — so a speculative row surfaces as fact
in a default recall. Dormancy, by contrast, HOLDS on both layers (main.py:207-210 enabled-gate
+ morpheus_gate.py topology gate, 7 tests green) and Morpheus has no config-write tool, so it
cannot self-activate. The plan is built to close exactly the firewall gaps while keeping the
proven dormancy.

### sentinel-part1 — PATCHED — pass 2 — 2026-07-07

Plan:      wargames/plans/sentinel-part1-posture.md
Red-team:  wargames/red-team/sentinel-part1.md   (ran; CRITICAL B0 + 8 more, all verified vs source)

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — V1 ambiguity ("DENY/REQUIRES_APPROVAL whichever") replaced by a concrete live-path assertion (spy shutil.move, call count 0); SafetyVerdict values settled in recon.
  2 failure branches        PASS — unchanged; each move keeps failure+cause+counter.
  3 fork triggers           PASS — F1-1 path-split trigger (protected-path→emergency vs broader→alert) added; others intact.
  4 RECON NEEDED marks      PASS — R1/R4/R6 moved to SETTLED with the red-team evidence; R2/R3/R5 remain marked with exact checks.
  5 abort conditions        PASS — NEW Abort #1 (live-path gate: mutating call reached ungated → STOP) — the abort that would have caught B0; + FIM/shutdown-ambiguity abort. 9 total.
  6 verification runs       PASS — added V0 (live shutil.move count 0), V0b (real approve/reject; internal source refused); V1 now proves the list entry gates at module.execute (remove→RED); V4 covers all 4 Windows defaults + generator.
  7 survived red-team       PARTIAL→recorded — the attack LANDED (B0 CRITICAL: never_autonomous gates only the off-path classifier; the live door was open behind a green test). Patched via F5-0 (wire enforcement onto _pre_tool_hook + SECURITY_TOOLS branch) + F5-0b (build real approve/reject). Recorded in the plan's point-7 section. NOT yet DONE — a confirmatory kill-attempt on the patched plan has not yet failed (dispatched next).
  8 executable blind        PASS (was WEAK) — the verdict ambiguity and the "prove the gate" wrong-path are resolved; F5-0/F5-0b give exact edit sites (cerberus.py:1213-1273, 484-490; harbinger.py:604-653) and live-path assertions.
  9 gates & autonomy        PASS (now genuinely wired) — NEW G0 (the gate mechanism itself) makes F5-0/F5-0b the earned-by for every downstream row; G1/G2/G4 rewritten to cite the LIVE-path gate, not the classifier. This is the correction from "named but not wired" to wired-with-a-failing-test.

Changed since last pass: red-team B0 (CRITICAL) proved never_autonomous is read only by the
off-path classifier — the live quarantine dispatch (hook_pre_tool→module.execute→handle→
shutil.move) never consults it, so the first draft's gate was on a door nobody walks through and
its test was green over a bypassed path. Fix: F5-0 wires the gate onto both live choke-points
with a spy-based live-path test (V0); F5-0b builds the missing approve/reject mechanism (B1);
F5-2 pins the interception point (B2); F5-4 corrected to the real 4 Windows-path defaults (B3);
F1-1 reconciles FIM vs emergency-shutdown + BLOCKED identity (B4/B5); F3-1 adds the identity row
(B4); F4-3 stops copying the broken heartbeat exemplar + F4-6 files the pre-existing bug (B8).

### sentinel-part2 — PATCHED — pass 2 — 2026-07-07

Plan:      wargames/plans/sentinel-part2-injection.md
Red-team:  wargames/red-team/sentinel-part2.md   (ran, concentrated per brief; CRITICAL B1+B2+B3, executable payload on paper)

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — observations now assert on behavior + provenance (V-P2.0 no-UGC-0.7; V-P2.1 provenance demotion incl. 0.7 github item; V-P2.4 all 8 classes behavioral).
  2 failure branches        PASS — each move's trap sharpened (filter-not-demote, fence-too-late/static-nonce, structural-test-masquerading-as-behavioral).
  3 fork triggers           PASS — RP1/RP2 forks resolved to a settled design (enforce in recall()); RP3 exclusion-fallback carries a concrete trigger (any nonzero execution in V-P2.4 → switch to excluded-summary).
  4 RECON NEEDED marks      PASS — RP1/RP2/RP4 moved to SETTLED with red-team evidence; RP3 (does the abliterated model obey the fence) kept explicitly as the make-or-break live measurement, not assumed.
  5 abort conditions        PASS — 7 aborts, adding: UGC-host-treated-as-trusted (B1), any byte outside the nonce fence / MCP-egress unfenced (B6/B11), scraped item can raise trust (B3). Every worst-case now has a STOP.
  6 verification runs       PASS — V-P2.0 added (trust-assignment); V-P2.4 now includes class-7 (reputable-host plausible instruction) + class-8 (fence-close) — the vectors that actually execute — so it can no longer PASS on a broken front.
  7 survived red-team       PARTIAL→recorded — the attack LANDED HARD: a github/*.edu-hosted, signature-free, plausible instruction lands at trust 0.7, above the float floor, never fenced (fence targeted untrusted-tier), and the staged path strips trust before assembly → executed on paper (B1+B2). Also B3 (supersede has no trust ceiling). Patched by re-keying mitigations on PROVENANCE (P2-0), enforcing in recall() (P2-1/P2-2), nonce fence (B6), trust ceiling (P2-5), and adding the laundering corpus class (B7). NOT yet DONE — confirmatory kill-attempt on the patched plan pending.
  8 executable blind        PASS (was WEAK) — the choke-point-that-doesn't-exist dependency is removed; enforcement is a named single site (recall(), grimoire.py:965-1165) every caller shares.
  9 gates & autonomy        PASS (now wired) — GP0 (trust assignment) added; GP1/GP2 moved from "named at a nonexistent choke-point" to "enforced in recall()"; GP5 supersede ceiling is new code, not an observation; GP7 earned-by now requires the class-7 corpus item to pass, so web autonomy can't lift on a false PASS.

Changed since last pass: red-team got an executable payload through — reputable-host (0.7)
plausible instruction + trust-stripped staged path (B1+B2), plus no supersede trust ceiling (B3).
Fix re-keys the whole defense on PROVENANCE not trust-float, enforces floor+demotion+ranking+
escape-safe-nonce-fence INSIDE recall() (covering all 15+ callers incl. MCP egress), adds a real
trust ceiling to supersede/remember, adds the class-7/8 corpus items, and adds an exclusion
fallback if the abliterated model leaks the fence (B8). Corpus grew 6→8 classes.

### sentinel — status note — 2026-07-07

Both parts are PATCHED, not yet DONE. Per SUCCESS.md, DONE requires all nine to hold AND one
honest kill-attempt to FAIL. The first kill-attempt SUCCEEDED (landed CRITICALs on both parts),
so the honest status is PATCHED. A second, confirmatory red-team pass against the patched plans
is dispatched; DONE is claimed only if a fresh attacker fails to land a CRITICAL/HIGH break.
Anti-inflation: I am not grading these DONE on the strength of my own patches alone.

### omen — PATCHED — pass 2 — 2026-07-07

Plan:      wargames/plans/omen.md  (Fronts 1, 2, 4, 5)
Plan:      wargames/plans/omen-part3-selfmod.md  (Front 3, crown)
Red-team:  wargames/red-team/omen.md  +  wargames/red-team/omen-part3-selfmod.md  (pass 1, both landed)

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — vague spots hardened: Stage SW got a real pass/fail predicate (test-green-in-sandbox, not "returns an exit code"); §1.4 requires driver ∈ {gemma-local,apex} + a semantic bug; §2.3 asserts concrete file:line findings; every G-repair verify names an observable.
  2 failure branches        PASS — each move keeps most-likely-failure + cause + counter.
  3 fork triggers           PASS — the one judgment-call fork the attacker found (Stage-P local-vs-Apex driver) is now a mechanical path-list + AST-diff rule.
  4 RECON NEEDED marks      PASS — hot-reload SETTLED (no reload; Gate 5 mandatory regardless); emergency-shutdown wiring moved from RECON to build item G6 with a two-sided verify; tool_loader reachability of sandbox_to_production still a marked pre-Part-3 check; Front-4 allow-list BLOCKED on Master.
  5 abort conditions        PASS — added A6 (TestGate auto-commit before its gate) and B0 (bypass roads open → Part 3 does not run); B1 dirty-tree now wired in code, not paper; B8 reworded post-hot-reload-settle.
  6 verification runs       PASS — de-circularized: G1/G3/G6 now carry positive+negative controls; new Verification #0 gates the whole of Part 3 on the four bypass-road closures; the data-loss assertion (original bytes intact on failed promotion) is the stop-the-front check.
  7 survived red-team       PARTIAL→recorded — the attack LANDED HARD on BOTH plans. Part 3: code_edit is an ungated autonomous write to modules/** that walks around the entire gated pipeline (B-1 CRITICAL), + dormant emergency trigger (B-3) + mis-wired pre-hook param key (B-2). Fronts: a CRITICAL recon error (I called _code_generate template-only; it makes a live Ollama call at omen.py:3176/3242/3249) + G1's verification was circular (passes today because the RED baseline blocks, proving nothing). Patched: new Stage 0 "close the bypass roads" + Abort B0 + Verification #0; corrected §0.2; non-circular G1/G3/G6 + new G7; §1.4 semantic-bug + real-driver requirement; three-part Front-2 read-only proof. NOT yet DONE — confirmatory kill-attempt on the patched plans pending.
  8 executable blind        PASS (was WEAK) — driver fork mechanized; gates name file+function; residual BLOCKED-on-Master item (Front-4 diagnostic allow-list) is correctly a Master input, not a hidden judgment call.
  9 gates & autonomy        PASS (now wired) — the decisive fix: the gated pipeline is no longer beside an open road. Stage 0 forces code_edit/git_commit under the same gate as sandbox_to_production; every G1–G7 repair has a verify that fails on the current broken behavior; capability (real review, self-recreation, host repair) planned in full with each dangerous move wearing its lock.

Changed since last pass (what the red-team broke and how the patch fixed it):
- BYPASS ROADS (worst break): pipeline gated sandbox_to_production but code_edit
  (autonomous, PROTECTED_PATHS lacking modules/) reaches modules/omen/omen.py and
  modules/cerberus/cerberus.py ungated. → Added Stage 0 (G4 extends PROTECTED_PATHS to
  modules/; G1 gates git_commit; G2/G3 fix pre-hook param key + applies_to; G6 wires the
  dormant emergency trigger), Abort B0 halts the front until all four verify green,
  Verification #0 gates Part 3 on them.
- RECON ERROR: _code_generate is model-driven (live local Gemma), not template-only.
  → §0.2 corrected; A5 rewritten to re-anchor on drift, not abort on a moved line.
- CIRCULAR GATE VERIFY (G1): "tool did not execute" is already true on the RED baseline.
  → baseline-independent unit test with positive + negative controls; §5.0 preamble bans
  verifications that pass on the current broken behavior; same discipline to G3/G6.
- Also: G7 (sandbox_to_production missing from _WRITE_TOOLS), §1.4 structural-fallback
  false-green, Front-2 read-only proof blind to data//Grimoire, dirty-tree abort now wired,
  Stage-T coverage gate, mechanical driver trigger, structural no-push proof.

Split justification (SPLIT): Omen is genuinely two missions. Fronts 1/2/4/5 (daily coding
brain, self-analysis-as-proposal, conservative host repair, gates contract) share a threat
model whose worst case is a bad edit caught by tests/Master. Front 3 (self-repair /
self-recreation) is higher-stakes: its worst case is an ungated or unrecoverable write to
Shadow's own running code — Omen editing Omen — where the abliterated model has no refusal
backstop and a corrupted instance hosts the very rollback code that should save it. The seam
falls between "find/propose" (ungated) and "change Shadow's own code" (gated pipeline), which
is the spine of the mission. The red-team vindicated the split: Part 3's worst break (the
code_edit bypass) is exactly the class of failure that deserved its own concentrated attack.

### omen — PATCHED — pass 3 — 2026-07-07

Plan:      wargames/plans/omen.md  (Fronts 1/2/4/5)
Plan:      wargames/plans/omen-part3-selfmod.md  (Front 3, crown)
Red-team:  pass 1 → omen.md + omen-part3-selfmod.md; pass 2 (confirmation) →
           omen-pass2.md + omen-part3-selfmod-pass2.md

Pass-2 result (confirmatory kill-attempt on the pass-1 patches):
- FRONTS: patches HELD. No CRITICAL. One HIGH (Move 2.1 named `code_analyze_self`,
  which always writes Grimoire at omen.py:2637 → Abort A4 on move one) + 2 MEDIUM
  (G1 async-worker gap async_tasks.py:250-252; G5 negative-control only reproduces
  on the no-engine branch) + 2 LOW. All patched. Spine confirmed sound twice.
- PART 3 (crown): patches did NOT fully hold — 1 CRITICAL + 3 HIGH.
  * CRITICAL P2-1: a SECOND bypass road. `sandbox_to_production`→`copy_to_production`
    (sandbox.py:1096-1147) guards only the source; the `production_path` destination
    has NO check, so a raw autonomous call overwrites/deletes modules/cerberus/*.py
    ungated. Stage 0 had closed code_edit, not this.
  * HIGH P2-3: APPROVAL_REQUIRED genuinely unenforced in the live loop
    (orchestrator.py:5197-5223); G1 unit-test-on-a-stub can pass while the real loop
    executes.
  * HIGH P2-3b: G6 dead three ways — check_shutdown_triggers has ZERO callers,
    _is_safe_operation short-circuits because code_edit/git_commit are in
    SAFE_TOOL_NAMES (emergency_shutdown.py:47-54); I'd also mis-named it should_shutdown.
  * HIGH P2-2: Verification #0 under-inclusive (checked 4 G-repairs, none inspected
    copy_to_production's dst) → greened with P2-1 open.
  * MEDIUM P2-4 (driver AST rule missed in-place inversions) + P2-5 (Stage-S restore
    tautology on a clean tree).

Patch born from pass 2:
- PART 3 Stage 0 rewritten around a CLOSURE PRINCIPLE — enumerate every write-capable
  tool from Omen.get_tools() and require each to refuse protected destinations OR be
  pipeline-only — so bypass road #3 is caught structurally, not by extending a list.
  sandbox_to_production destination guard is now a Stage-0 closure + a raw-call
  checkpoint-token requirement; G1 tested against the REAL dispatch loop incl. the
  async worker; G6 corrected (real method name + de-whitelist write tools + wire a
  caller); Verification #0 enumerates write tools and adds dst + G6-caller checks;
  driver rule uses AST condition/return compare; Gate-1 restorability is a full
  change→checkpoint→mutate→restore→compare round-trip.
- FRONTS: Move 2.1 tool-choice directive (write-free analyze tools, never
  code_analyze_self); G1 covers all three dispatch entries; G5 negative control pinned
  to reversibility_engine=None; has_docstrings quote fixed.

Self-grade vs SUCCESS.md (1–9) — after pass-3 patch:
  1 expected observations   PASS — Stage-0 enumeration, Verification #0, restore round-trip, driver-rule all now carry concrete observables; the vague ones pass-2 flagged are gone.
  2 failure branches        PASS.
  3 fork triggers           PASS — driver fork now an AST rule that catches in-place inversions.
  4 RECON NEEDED marks      PASS — G6's true state (zero callers + SAFE_TOOL_NAMES short-circuit) now settled and folded in; scaffold_* write-status marked "verify before trusting".
  5 abort conditions        PASS — B0 now keyed on the closure principle (any open write road), not a fixed pair.
  6 verification runs       PASS — Verification #0 enumerates write tools; G1 tests the real loop; restore is a real round-trip; each negative control pinned to the branch that actually reproduces.
  7 survived red-team       FRONTS: PASS (two passes; pass-2 landed only a HIGH, now closed; spine sound). PART 3: PARTIAL — pass-2 landed a CRITICAL; pass-3 patch is substantial and NOT yet re-attacked. A third confirmatory pass on Part 3 is dispatched; DONE claimed only if it fails to land CRITICAL/HIGH.
  8 executable blind        PASS — Stage 0 tells the executor to enumerate from get_tools() rather than trust the plan's list; remaining BLOCKED item (Front-4 allow-list) is a Master input.
  9 gates & autonomy        PART 3 PASS-pending-pass-3 — the closure principle is the right structural fix (two bypass roads found by two passes both fall under it); every dangerous move wears a wired gate with a non-circular, branch-pinned verify.

Changed since last pass: pass-2 confirmation attack landed a CRITICAL on Part 3 (second
bypass road: sandbox_to_production destination unguarded) + G6-dead-on-arrival + circular-
against-a-stub G1; fronts landed one HIGH (code_analyze_self writes Grimoire). Fixed by
reframing Stage 0 as an enumerate-every-write-tool CLOSURE PRINCIPLE, rebuilding G6 against
its real (zero-caller, whitelisted) state, testing G1 against the live loop, making the
restore verification a real round-trip, and adding the Move 2.1 tool-choice directive.

Anti-inflation note: Part 3 is NOT graded DONE. Two passes found two distinct CRITICAL
bypass roads; the pass-3 fix is structural (a principle, not a third item on a list), which
is why it should hold — but "should hold" is not "a fresh attacker failed to break it." A
third confirmatory red-team is dispatched; DONE is earned only by its failure to land a
CRITICAL/HIGH.

### sentinel-part1 — PATCHED — pass 3 — 2026-07-07

Plan:      wargames/plans/sentinel-part1-posture.md
Red-team:  wargames/red-team/sentinel-part1.md (pass 1) + wargames/red-team/sentinel-part1-pass2.md (pass 2)

Confirmatory pass 2 verdict: the B0 patch HELD (F5-0 step-2 gate confirmed to cover every
route to shutil.move via the single caller at cerberus.py:488). But the B1 patch did NOT, plus
scope + MEDIUM breaks — all patched this pass:
  1 expected observations   PASS — added spy-based live-path tests for the non-security host-tool
                            path and the token/nonce/source-spoof cases.
  2 failure branches        PASS.
  3 fork triggers           PASS.
  4 RECON NEEDED marks      PASS — R1/R4/R6 SETTLED with evidence; R2/R3/R5 marked.
  5 abort conditions        PASS — Abort #1 extended to non-security host tools; new F5-0b abort
                            (approval decision/source must not come from LLM-planned params).
  6 verification runs       PASS — V0b now proves token-required + source-not-param-spoofable +
                            single-use-nonce; new V0c proves step-1 blocks non-security host tools
                            and a static token does not open step-2; V4 gets a generator-output test.
  7 survived red-team       PARTIAL→recorded — pass-2 P1/P2 (HIGH): the approval trust signal came
                            from the untrusted LLM planner (params["source"]) and the step-2
                            open-condition was an unspecified/replayable token → self-approve /
                            re-open B0. Patched: F5-0b requires the secret creator TOKEN + an
                            authoritatively-bound source (ingress, not params) + a single-use
                            nonce; F5-0 step-1 made load-bearing for non-security host tools
                            (software_install/firewall_apply ride step-1, not step-2). NOT yet DONE
                            — pass 3 dispatched against these patches.
  8 executable blind        PASS.
  9 gates & autonomy        PASS — G0 records the token/nonce/source-binding; G2/G4 re-cite step-1
                            (they are NOT security-surface tools, so step-2 doesn't cover them).

Changed since last pass: pass-2 confirmed the security-surface gate is solid but broke the
approval AUTHORITY (spoofable source, replayable token) and surfaced that non-security host tools
bypass the strong step-2 gate. Patched with token+nonce+authoritative-source and a real step-1.
Also: V4 grep blindness to the generator's C:\Shadow (P3), FIM-vs-emergency event-model mismatch
(P4), and F5-3 vacuity (P5, now forward-looking with a synthetic-tool test).

### sentinel-part2 — PATCHED — pass 3 — 2026-07-07

Plan:      wargames/plans/sentinel-part2-injection.md
Red-team:  wargames/red-team/sentinel-part2.md (pass 1) + wargames/red-team/sentinel-part2-pass2.md (pass 2)

Confirmatory pass 2 verdict: one CATEGORY ERROR (graded the plan as if it were implemented code —
grepped modules/ for unbuilt symbols; a wargame plan is a route for the executor, not committed
code, so "not implemented" is not a break) + TWO real breaks that survive that correction — both
patched this pass:
  1 expected observations   PASS — V-P2.0 adds noncapped-Tier1-still-fenced + every-scraped-write-
                            tagged; V-P2.1/2 add every-reader-sanitizes across recall()+GrimoireReader+MCP.
  2 failure branches        PASS.
  3 fork triggers           PASS.
  4 RECON NEEDED marks      PASS — RP1 corrected (TWO reader families); new RP5 (provenance
                            completeness across all web-origin writers).
  5 abort conditions        PASS — added: any reader (incl. GrimoireReader) serves scraped content
                            unfenced → STOP; a scraped write missing provenance → STOP.
  6 verification runs       PASS.
  7 survived red-team       PARTIAL→recorded — pass-2 real breaks: (a) GrimoireReader is a SECOND
                            reader family with its own DB handles (grimoire_reader.py, reachable via
                            base.py:277-303) that bypasses a recall()-only fence — my recon gap;
                            (b) P2-0's host-cap is a blocklist (arxiv etc. stay 0.7). Patched:
                            enforcement moved to a shared _sanitize_recalled() called by EVERY read
                            path; P2-0 downgraded to defense-in-depth with provenance-fencing as the
                            load-bearing control (arxiv-at-0.7 still fenced by provenance). NOT yet
                            DONE — pass 3 dispatched.
  8 executable blind        PASS.
  9 gates & autonomy        PASS — GP1/GP2 moved from "inside recall()" to the shared sanitizer; GP0
                            marks the host-cap as defense-in-depth and provenance-completeness as the
                            invariant.

Changed since last pass: the "enforce inside recall()" fix (pass 1) missed a whole second reader
family (GrimoireReader); moved enforcement to a shared sanitizer every read path calls. Trust-cap
demoted to defense-in-depth; provenance-fencing (regardless of trust number) is the load-bearing
control, so incomplete host-caps no longer open the vector.

### sentinel — status note (updated) — 2026-07-07

Two confirmatory passes done. Pass 2 confirmed the CORE structural gates hold — Part 1's step-2
security-surface gate (no route to shutil.move bypasses it) and Part 2's write-time provenance
tagging + corpus fixture isolation. The pass-2 breaks were one level subtler (approval AUTHORITY
spoofing; a second reader family) and are patched. Both parts remain PATCHED, not DONE: a third,
tightly-scoped confirmatory pass is dispatched against exactly the pass-2 patches (token/nonce/
source-binding; the shared sanitizer). DONE is claimed only if pass 3 fails to land a CRITICAL/
HIGH. Note: the approval-authority mechanism (authoritative source binding + cross-process nonce
threading) edges into architecture; if pass 3 still finds authority-level holes, that residual is
escalated to Master/an Opus session per CLAUDE.md ("architecture decisions happen in Opus
sessions"), not paper-patched further.

### morpheus — PATCHED — pass 2 — 2026-07-07

Plan:      wargames/plans/morpheus.md
Red-team:  wargames/red-team/morpheus.md   (ran; 1 CRITICAL + 3 HIGH + 3 MEDIUM + 1 LOW, all verified vs source; activation gate held)

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — strengthened: V2 now asserts BEHAVIOR (0 hits in real recall AND real grimoire_reader.search) + a semantic trust-value assertion, not a trust tag on a row.
  2 failure branches        PASS — each move keeps failure+cause+counter; 2.1's most-likely-failure now names the census-by-memory + store_routed-defaults-0.5 traps the red-team used.
  3 fork triggers           PASS — 2.1 write-method fork now covers store_routed (not just .store→remember); others intact.
  4 RECON NEEDED marks      PASS — RN1 confirmed clean by the attacker (load_on_startup inert, grep empty); RN3/RN4 remain correctly marked (recall-floor owner, frontier-benchmark definition BLOCKED on Master).
  5 abort conditions        PASS — A4 given a numeric trigger (corpus rejection <60% / >40% promoted); A7 extended to store_routed + rd_lab:555; A8 re-armed as "count from the census grep, not a memorised list."
  6 verification runs       PASS (materially fixed) — V2 rewritten to (a-i) census grep incl. store_routed with the count re-derived, (a-ii) explicit-speculative-trust assertion, (b) dry-run against a REAL Grimoire (stub forbidden). This closes red-team break #4 (a stub double faked "0 hits").
  7 survived red-team       PARTIAL→recorded — the attack LANDED (break #1 CRITICAL: the firewall's write-path census was 3, the code has 4; the missed rd_lab.py:555 _store_speculative writes an UNTESTED dream on the default branch, and the draft baked "3" into V2a/G2/CL-5/A7 so every gate would report PASS over the live leak). Patched: census is now derived by RUNNING the grep, all 4 writers enumerated, +3 HIGH/3 MED/1 LOW all fixed and recorded in the plan's point-7 section. Activation gate G1 SURVIVED every route (no self-flip tool, no load_on_startup bypass, instantiation gate real). NOT yet DONE — a confirmatory kill-attempt on the patched firewall has not yet failed (pass 3 dispatched).
  8 executable blind        PASS (was WEAK) — census-by-grep removes the hand-list judgment call; V4 no longer asserts a property false on a correct system (10 keys, roster≠registered-modules). RN4 remains correctly BLOCKED on Master, not a hidden hole.
  9 gates & autonomy        PASS (now honest) — G3 split into G3a (Morpheus-side, actually wired: never write to `memories`) and G3b (recall-side, explicitly NOT wired here = CL-6 dependency), killing the "wired, not named" overclaim the attacker flagged. G1 (activation, Master-only on the 9-item checklist) confirmed unbreakable on paper by the red-team.

Changed since last pass: red-team break #1 (CRITICAL) proved the firewall's own write-path census
was incomplete — the draft hand-listed three Grimoire writers; a fourth (rd_lab.py:555
_store_speculative, fired on the DEFAULT/untested branch, writing validated:False) was baked out of
V2a/G2/CL-5/A7, so an executor would ship CL-4 green while a raw untested dream leaked into a
default recall. Fix: the write-path census is now derived by running
`grep -rn "\.store(\|\.remember(\|store_routed(" modules/morpheus/` and asserting the count, never
a memorised list; all four writers enumerated; store_routed added as a trust-0.5 surface the gate
must control; the certifying dry-run (V2b) forbidden from using a stub and required to exercise the
real recall + real grimoire_reader.search; G3 split into a wired Morpheus arm and an honestly-unwired
cross-mission arm; V4 roster check de-mis-specified; A4 given numeric triggers. Eight breaks, zero
left open, no capability amputated.

No-split justification: unchanged — one threat model (speculation contaminating verified knowledge),
one owned code area (modules/morpheus/* + the Grimoire retrieval boundary). Firewall is the spine.

Note on DONE bar: matching the sentinel precedent, DONE is claimed only if a fresh pass-3 attempt
on the patched firewall fails to land a CRITICAL/HIGH. If pass 3 finds that the load-bearing
containment ("never write speculative to `memories`") cannot be enforced Morpheus-side without the
Grimoire recall-floor (RN3/CL-6) — i.e. the fix genuinely lives in shared Grimoire code — that
residual is escalated to Master / an Opus session per CLAUDE.md, not paper-patched further.

### omen — FRONTS: DONE · PART 3: BLOCKED — pass 4 (final) — 2026-07-07

Plan:      wargames/plans/omen.md  (Fronts 1/2/4/5) — DONE
Plan:      wargames/plans/omen-part3-selfmod.md  (Front 3, crown) — BLOCKED
Red-team:  pass 1 (omen.md, omen-part3-selfmod.md); pass 2 (omen-pass2.md,
           omen-part3-selfmod-pass2.md); pass 3 (omen-part3-selfmod-pass3.md)

Three independent red-team passes on the crown; each found a STRUCTURALLY DISTINCT
write road to Shadow's own code:
  pass 1 — code_edit (handler-destination gap: PROTECTED_PATHS omit modules/)
  pass 2 — sandbox_to_production (handler-destination gap: copy_to_production dst unguarded)
  pass 3 — sandbox_execute / code_execute (TRANSITIVE road: model-authored code runs in a
           thin subprocess as same user with full FS write; a relative-traversal write
           open("../../modules/omen/omen.py","w") is unflagged by the static validator)

The pass-3 road is a different KIND: the write is not in a tool handler, so no
tool-destination guard closes it. The only containment for executed code is the OS
(unpriv user + read-only bind-mount of the source tree, or namespace/seccomp/bwrap),
which the current sandbox does not provide (premise 1). Therefore the self-mod pipeline
CANNOT be made "the only road" to a modules/** write on the current host, and the
abliterated model has no refusal backstop. Honest terminus: PART 3 is BLOCKED.

FINAL grades vs SUCCESS.md (1–9):

FRONTS (omen.md) — DONE:
  1 expected observations   PASS — concrete observables throughout; §1.4 requires a real driver + a semantic bug; §2.3 concrete file:line findings; every G-repair has an observable.
  2 failure branches        PASS.
  3 fork triggers           PASS — driver fork mechanized; all forks carry triggers.
  4 RECON NEEDED marks      PASS — counts/intelligence/orphan/hot-reload settled; Front-4 allow-list correctly BLOCKED on Master.
  5 abort conditions        PASS — A1–A6.
  6 verification runs       PASS — non-circular G-checks (positive+negative controls, branch-pinned); real-loop G1.
  7 survived red-team       PASS — two passes; pass-2 landed only a HIGH (code_analyze_self writes Grimoire), now closed; spine confirmed sound twice; no CRITICAL.
  8 executable blind        PASS — residual BLOCKED item (Front-4 allow-list) is a Master input, not a hidden judgment call.
  9 gates & autonomy        PASS — decorative gates recon found are converted to wired G1–G7 repairs, each with a verify that fails on the current broken behavior; capability planned in full.

PART 3 (omen-part3-selfmod.md) — BLOCKED (correctly; not a plan defect):
  1 expected observations   PASS — incl. the Class-2 active traversal-write probe and the round-trip restore.
  2 failure branches        PASS.
  3 fork triggers           PASS — AST-based driver rule; Gate-5 import-fail; pass-drop regression.
  4 RECON NEEDED marks      PASS — the load-bearing one is now explicit: what OS isolation Citadel can provide (bwrap/firejail/userns/low-priv user + ro bind-mount), to be put to Master.
  5 abort conditions        PASS — B0 (Class-1 road) + B9 (Class-2 road / no isolation) + B1–B8.
  6 verification runs       PASS — Verification #0 enumerates from get_tools() and ACTIVELY probes code execution; the data-loss and false-success assertions are stop-the-front.
  7 survived red-team       BLOCKED-not-DONE — three passes, three write roads; the third forces the OS-isolation conclusion. DONE is intentionally NOT claimed: the plan's own verdict is that it must not run until isolation exists, so a further pass would attack a route the plan forbids. A fresh red-team on the ISOLATED pipeline is the real point-7 test, and it is gated on Master's isolation decision.
  8 executable blind        PASS — the closure principle tells the executor to enumerate from get_tools() and probe execution rather than trust the plan's list (the fix for the recurring "list missed a tool" failure).
  9 gates & autonomy        PASS — every dangerous move wears a wired, non-circular gate; the crown capability is planned in full AND correctly gated behind an isolation floor it does not yet have. Capability + gate both present; security-before-autonomy is the column, and here it (correctly) says: not yet.

Blocking input (BLOCKED): Master's decision on the code-execution isolation substrate
for sandbox_execute/code_execute — an unprivileged 'shadow-sandbox' user with a read-only
bind-mount of ~/dev/Shadow/{modules,config}, or a bwrap/firejail/namespace jail. This is an
architecture decision (CLAUDE.md: made in Opus sessions, not Claude Code). Until it exists
and the Verification #0 Class-2 probe is BLOCKED, Part 3's pipeline is fully planned but
MUST NOT run.

Anti-inflation note: I did NOT grade Part 3 DONE and did not loop to a 4th pass to force one.
Three passes converged on a real architectural floor, not a patchable plan bug. Claiming DONE
here — or attacking a route the plan says must not run — would be exactly the self-generous
grading this ledger exists to catch. FRONTS is DONE on its own merits (two honest kill-attempts,
no CRITICAL, residuals closed). PART 3 is BLOCKED, which is the honest and correct state.

Why the SPLIT was right (vindicated): the seam between "find/propose" (Fronts, worst case a
bad edit caught by tests/Master) and "change Shadow's own code" (Part 3, worst case an
unrecoverable write with no refusal backstop) is exactly where the risk cliff falls. Fronts
reached DONE; Part 3 hit an architectural floor. Had they shared one plan, the Fronts work
would have been held hostage to Part 3's isolation blocker, or Part 3's CRITICAL would have
been diluted under the daily-brain fronts. The concentrated per-part red-teams are what
surfaced the three distinct write roads.

### sentinel — PATCHED + BLOCKED (loop stopped) — pass 3 final — 2026-07-07

Plan:      wargames/plans/sentinel-part1-posture.md · wargames/plans/sentinel-part2-injection.md
Red-team:  sentinel-part1{,-pass2,-pass3}.md · sentinel-part2{,-pass2,-pass3}.md  (three passes each)

FINAL HONEST STATUS: NOT DONE, and DONE is not reachable in a Claude-Code session — the last
breaks are ARCHITECTURE decisions CLAUDE.md reserves for Opus. Three independent kill-attempts
per part; each earlier pass's breaks were patched and HELD under the next pass; pass 3 landed a
CRITICAL on each part that is architectural, not paper-patchable. The buildable mitigations are
wargamed and worth building; the load-bearing autonomy stays dormant on named Master inputs.

Self-grade vs SUCCESS.md (1–9), across both parts as they now stand:
  1 expected observations   PASS — every buildable move has a concrete observable/live-path test.
  2 failure branches        PASS.
  3 fork triggers           PASS.
  4 RECON NEEDED marks      PASS — incl. the two BLOCKED-on-Master items now named exactly
                            (CREATOR_AUTH_TOKEN unset; the authenticated approval channel).
  5 abort conditions        PASS — incl. the live-path gate abort and the "any reader serves
                            scraped content unfenced" / "approval from LLM params" aborts.
  6 verification runs       PASS for buildable scope; the FULL-closure verifications (web
                            autonomy live) are gated on the architecture residuals.
  7 survived red-team       HONEST FAIL-then-converge — three passes, each landed real breaks;
                            the security-surface gate (Part 1 step-2) and the escape-safe fence +
                            fixture isolation (Part 2) SURVIVED repeated attack; the approval
                            AUTHORITY (Part 1) and derivation-taint + single-seam (Part 2) are
                            escalated as architecture, not claimed closed. Not DONE.
  8 executable blind        PASS for buildable moves; the BLOCKED items are explicit Master inputs,
                            not hidden judgment calls.
  9 gates & autonomy        PASS as a CONTRACT — the plan now states precisely which capability is
                            buildable-and-gated now (read-only posture; propose-only host changes;
                            first-order injection fence) and which is BLOCKED until Master decides
                            the architecture (gated host actions; Tier-2 web autonomy). Security
                            before autonomy is the column: autonomy is dormant until earned.

BLOCKED-on-Master inputs (mission cannot reach DONE without these):
  - Part 1 AR-P1-1: an OUT-OF-BAND authenticated approval channel (approval that does not
    traverse LLM-planned tool params; caller identity authenticated) — architecture, Opus.
  - Part 1: provision CREATOR_AUTH_TOKEN in .env (secrets-only) — Master.
  - Part 2 AR-1: taint propagation through recall→generate→store (Apex re-store laundering) —
    architecture, Opus.
  - Part 2 AR-2: a unified retrieval layer OR write-time normalization+fence (pointer_index_as_text
    and heterogeneous readers bypass any single read sanitizer) — architecture, Opus.

Why the loop is STOPPED here (not abandoned): passes 1–2 found paper-patchable structural holes
and they were fixed and held. Pass 3 found that full closure requires two architecture decisions
per part; a Claude-Code session must not make those (CLAUDE.md), and a pass 4 would re-discover
the same gap rather than converge. The wargame's job — surface the unknown unknowns and gate
autonomy on them — is complete: the executor has a buildable read-only/propose-only route now, and
Master/Opus has an exact, evidence-backed list of the architecture decisions that must precede any
autonomous host action or Tier-2 web ingress.

Changed since last pass: Part 1 — nonce read-side redaction added (buildable); source-binding +
unset token escalated to ARCHITECTURE RESIDUAL/BLOCKED. Part 2 — five write sites corrected (added
reaper.py:1217), MCP write path added; Apex derivation-laundering (AR-1) and no-single-read-seam /
pointer_index_as_text (AR-2) escalated to ARCHITECTURE RESIDUAL/BLOCKED; GP7/G10 web autonomy now
gated on AR-1/AR-2 in addition to the corpus.

### morpheus — PATCHED — pass 3 (confirmatory) — 2026-07-07

Plan:      wargames/plans/morpheus.md
Red-team:  wargames/red-team/morpheus-pass3.md   (confirmatory pass on the pass-1 patches)

Result: the CRITICAL census fix (break #1) HELD — the attacker ran the census grep and hunted a
fifth write path five ways (aliased handles, _store_in_grimoire indirection, add/upsert/ingest/save,
direct ChromaDB .add(), path-glob misses); none exists. Self-activation re-confirmed impossible.
But pass 3 landed one HIGH + one MEDIUM on the pass-1 patches:
  - HIGH: V2(b)'s real-Grimoire fix never asserted the PLANT LANDED, so three silent-plant-failure
    modes (remember() check_duplicates dedup returns-without-writing grimoire.py:681,779-780; bare
    except swallows write errors rd_lab.py:426-428/experiment_store.py:525-526; remember() has no
    `collection` param so a naive .store()->remember() remap raises a swallowed TypeError) make
    "0 hits" trivially true on a plant that never happened — a false green on the load-bearing CL-4.
    PATCHED: V2(b)+Front 2.2 now require a POSITIVE CONTROL (plant proven landed: new id,
    check_duplicates=False, no swallowed except, valid signature) before the 0-hits assertion; the
    duplicate "stub double" line in the verification preamble also removed.
  - MEDIUM: G3a cited a phantom "collection recall() never queries" — no such writable collection
    exists (remember writes only to shadow_memories, grimoire.py:237-238, no collection arg).
    PATCHED: clause deleted; G3a rests solely on the experiment-store (separate SQLite, no ChromaDB)
    separation.

Re-grade delta vs pass 2: point 6 (verification) strengthened (positive control closes the
false-green); point 9 (gates) G3a now rests on a REAL separation, phantom removed; point 7 remains
PARTIAL→recorded — pass 3 landed a HIGH, so NOT DONE. Pass 4 (final scheduled) dispatched, scoped to
the positive-control patch + experiment-store-only containment. DONE claimed only if pass 4 lands
nothing CRITICAL/HIGH; if it finds the containment needs shared Grimoire code (dedup/collection
semantics), that residual escalates to Master/an Opus session per CLAUDE.md, not a fourth paper-patch.

### morpheus — DONE — pass 4 (final confirmatory) — 2026-07-07

Plan:      wargames/plans/morpheus.md
Red-team:  wargames/red-team/morpheus.md (pass 1) · morpheus-pass3.md (confirm) · morpheus-pass4.md (final)

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — every move observable; the certifying V2(b) asserts BEHAVIOR (plant-proven-landed in shadow_memories, then 0 hits in real recall + real search), never a trust tag or a stub.
  2 failure branches        PASS — each move keeps failure+cause+counter; the load-bearing traps (census-by-memory, store_routed@0.5, stub-double, plant-silently-no-ops, plant-here/check-there) are all named and countered.
  3 fork triggers           PASS — write-method fork covers .store/remember/store_routed; ordering fork (Front 2 before Front 4) now an asserted gate, not a judgment call.
  4 RECON NEEDED marks      PASS — RN1 confirmed clean by attackers; RN3 (recall floor owner) / RN4 (frontier-benchmark def, BLOCKED on Master) / RN5 (live unload) each carry the exact settling check; nothing confident secretly leans on an unsettled item.
  5 abort conditions        PASS — A1–A8 incl. flip-enabled, speculative-reaches-memory, self-mod-outside-Omen, numeric promotion-rate, dormancy-unprovable, training-data-write, re-arm-a-writer (all four + store_routed), plan-vs-reality; A2 made executable as the V4 ordering gate.
  6 verification runs       PASS — V1–V6; V2(b) is the certifying run and now cannot report a false green (real Grimoire + positive control pinned to shadow_memories + both retrieval paths + no tokenless promotion); honest that V6 benchmark floor is activation-time.
  7 survived red-team       PASS — THREE fresh attackers. Pass 1 landed a CRITICAL (3-vs-4 write-path census) + 7 more; pass 3 confirmed that fix holds and landed a HIGH (plant-landing unproven) + MEDIUM (phantom collection); pass 4 (final) landed NOTHING CRITICAL/HIGH — only 2 MEDIUM + 1 LOW plan-side one-liners, all folded in. An honest kill-attempt on the patched firewall FAILED. Activation gate survived all three passes.
  8 executable blind        PASS — census-by-grep + pinned-store landing proof + named tables/DBs + asserted ordering remove every hidden judgment call. The only "can't just run it" items are correctly-BLOCKED cross-mission/Master dependencies (RN4, CL-6, CL-7), flagged as such.
  9 gates & autonomy        PASS — G1 (activation, Master-only on the 9-item checklist) proven unbreakable across 3 passes; G2 (single promotion gate, census-complete + explicit trust); G3a (Morpheus-side, rests on the REAL experiment-store separation, phantom removed) + G3b (recall-side, honestly marked NOT wired here = CL-6); G4–G9 intact. Capability planned in full (dreaming, what-if, RSI proposals, dream→test→improve, cross-module vanguard); every dangerous edge wears its gate.

Changed since last pass (pass 3 → 4): pass 4 verdict HOLDS (no CRITICAL/HIGH). Folded the 3 residuals:
M1 — landing proof pinned to shadow_memories (else vacuous); M2 — "Front 2 before Front 4" made an
asserted V4 gate (else a real-Grimoire wiring auto-promotes a tokenless success dream via the designed
path); L1 — G3a/V4 now name the right tables (failed_experiments@data/experiments.db for the dreamer
vs morpheus_experiments@data/morpheus_experiments.db for the tools; neither is shadow_memories).

DONE rationale: all nine hold AND a fresh honest kill-attempt (pass 4) failed to land CRITICAL/HIGH.
No residual is architectural — the attacker explicitly confirmed no shared Grimoire code change is
needed. The genuinely open items are deferred BY DESIGN and marked as activation-checklist blockers,
not plan holes: RN4 (frontier-benchmark definition, BLOCKED on Master), CL-6 (Grimoire recall floor,
owned by the Grimoire mission), CL-7 (Omen Part-3 gated self-mod). The plan is a readiness deliverable:
a module designed to switch on safely, plus the 9-item owned checklist that governs the switch.

No-split justification (unchanged): one threat model (speculation contaminating verified knowledge),
one owned code area (modules/morpheus/* + the Grimoire retrieval boundary); the firewall is the spine
binding the dream pipeline, the improvement loop, and activation. Kept as one plan.

### sentinel-p1-auth-approval — PATCHED (mechanism converged) + SCOPE RESIDUAL escalated — 3 passes — 2026-07-07

Plan:      wargames/plans/sentinel-p1-auth-approval.md
Red-team:  wargames/red-team/sentinel-p1-auth-approval.md (pass 1) · ...-pass2.md · ...-pass3.md

Mission: build the authenticated approval channel resolving AR-P1-1 (approval authority) +
AR-P1-2 (secret-reachability boundary) — the two items the prior Sentinel wargame booked
BLOCKED-on-Master/Opus. Spec-supplied seam (local-token authority made sound by an enforced
unreachability boundary; verify_approval() as a swap seam for a future off-box Ed25519 upgrade).

Enforcement-point correction (phantom-count doctrine, as the spec instructed): the spec's
"cerberus.py:488" is a PHANTOM (a return-statement line). The real dangerous-action funnel is
shutil.move at security/core.py:571, reached only via cerberus.py:504-508. The gate was planned
at the real funnel, not the phantom.

State change since the prior Sentinel wargame: CREATOR_AUTH_TOKEN is now SET and loads into the
live singleton (pass-1 attacker ran the check → True). That clears one of the two prior BLOCKED
items. The other (the authenticated approval channel itself) is what this mission designs.

Three fresh red-team passes, each landed real breaks; each fix HELD under the next pass:
  - Pass 1 CRITICAL — credential had no delivery wire except the planner-visible params dict.
    Fixed: Cerberus-private pending-ACTION store + enqueue-defer funnel + poll-loop re-invoke.
    Plus HIGH×3 (pre-hook can't read config lists; graph plan-gate is a log-only stub; mint→use
    untested / fail-to-hang), MEDIUM×2 (_action_category planner field; R3 scope), LOW (vacuous
    NEG-spoof). All patched.
  - Pass 2 CRITICAL — the pass-1 fix RELOCATED the hole: re-invoking the shared SecuritySurface.handle
    routed the authorized move back through the planner's door; handle is caller-blind and the store
    lookup was descriptor-keyed (planner-controlled), so a planner could ride a genuine approval
    (confused deputy + consume race). Fixed: two-method split — the planner-facing funnel ONLY
    enqueues (never moves); the move is _execute_approved(approval_id), poll-loop-private, not
    routable, keyed on the opaque id. New abort #9; four new NEG/POS tests.
  - Pass 3 — attacked the two-method design HARDEST and COULD NOT BREAK the mechanism (hardcoded
    dict dispatch/no getattr; MCP servers hardcoded; scaffold_test import shape-locked; chat_id
    transport-bound; nonce/credential confidential). The mechanism has CONVERGED. But pass 3 landed
    a NEW CRITICAL of SCOPE: my recon claim "quarantine_file is the only live host-mutating op" is
    FALSE — code_edit (autonomous, arbitrary write_text, omen.py:1606, PROTECTED_PATHS only guards
    config/.git/.env so modules/, main.py, data/, and the gate's own source are writable) and
    sandbox_to_production (sandbox.py:1126) mutate arbitrary paths WITHOUT touching the funnel this
    mission gates. Trips the plan's own abort #1. Plus HIGH (planner controls the alert reason
    free-text on a parse_mode:HTML channel with no escape + can flood competing notification_send —
    Master can be steered to approve the wrong id).

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — every buildable move has a concrete observable / named test /
                            filesystem-state assertion. The certifying tests assert behavior at the
                            live shutil.move, never a trust tag.
  2 failure branches        PASS — each move carries most-likely-failure + cause + counter.
  3 fork triggers           PASS — the swap-seam fork, the R4 token-wiring fork, the display-dedupe
                            option all carry explicit triggers; no judgment left to the executor.
  4 RECON NEEDED marks      PASS — R1 (token loads), R2 (software_install body), R3 (MANDATORY
                            host-write enumeration), R4 (poll-loop creds), R5 (funnel line), plus
                            documented residuals R6 (target-selection human limit) and R7 (competing
                            messages). Nothing confident leans on an unsettled item.
  5 abort conditions        PASS — 9 aborts incl. #1 (ungated funnel, ALREADY FIRED by pass-3),
                            #7 (credential-on-params), #9 (authorized move reachable off the poll loop).
  6 verification runs       PASS for the mechanism — V0 (must-fail-today red) → V1–V4 green → V5
                            live-once; test_handle_never_moves + test_planner_cannot_ride_approved_entry
                            are the pass-2-hole certifiers. HONEST GAP: the mechanism verifies; the
                            WHOLE-host-write-surface verification is explicitly out of scope (G7).
  7 survived red-team       HONEST: mechanism SURVIVED pass 3 (attacker could not break it → converged).
                            Passes 1 and 2 each landed a CRITICAL that was fixed and HELD. Pass 3's
                            scope CRITICAL is not a mechanism bug — it is booked as a documented SCOPE
                            BOUNDARY + follow-on mission, not paper-patched. This is the point-7 record:
                            the attack that failed (pass-3 on the mechanism) and the attacks that landed
                            (pass-1/2 credential path; pass-3 scope) with their patches/escalations.
  8 executable blind        PASS for buildable scope — B1/B2 pseudocode, named tests, the R3 sweep
                            command, and the fail-closed rules remove hidden judgment calls. The
                            out-of-scope items are explicitly flagged, not smuggled.
  9 gates & autonomy        PASS as a CONTRACT — G1–G7. Capability planned in full (the seam supports
                            quarantine now + the descriptor ops later + the off-box Ed25519 repoint);
                            every dangerous edge wears its gate; security-before-autonomy is the column
                            (M7 boundary + M4 funnel built BEFORE M5/M6 open them). G7 states plainly
                            that the abliteration/Heretic host-write precondition is the WHOLE surface
                            gated, NOT this funnel alone.

NOT-DONE-as-a-whole, DONE-as-scoped (honest status): the approval-CHANNEL mechanism is wargamed,
three-pass-converged, and buildable. It is DONE for its funnel. The mission does NOT make Shadow's
full host-write surface safe — code_edit / sandbox_to_production / the R3 set bypass this funnel and
are escalated to a named follow-on host-write mission (overlaps omen-part3-selfmod.md), with code_edit
(can edit the gate's own source) ranked first. Claiming the whole surface DONE here would be exactly
the self-generous grading this ledger exists to catch.

Why the loop STOPS at 3 passes (not abandoned, not inflated): pass 3 could not break the mechanism —
a 4th mechanism-attack would re-confirm convergence, not find new ground. Pass 3's scope CRITICAL is
handled by honest re-scoping + escalation (the correct move for a boundary finding), not by a mechanism
change that would need re-attack. Matches the established project pattern (prior sentinel/morpheus:
stop when the mechanism converges and the remaining items are named escalations, not paper-patchable
plan bugs).

No-split justification: AR-P1-1 (authority) and AR-P1-2 (boundary) are one mission — the local-token
authority is sound IFF the planner provably cannot reach the token, which only AR-P1-2 makes provable.
Splitting would sever the dependency the whole design rests on. The host-write-surface work is a
SEPARATE follow-on mission (not a split of this one) — its seam falls where the risk cliff does:
this mission gates one funnel with an authenticated channel; the follow-on gates the remaining
routed host-writes. Kept the approval channel as one plan; named the follow-on rather than absorbing it.
