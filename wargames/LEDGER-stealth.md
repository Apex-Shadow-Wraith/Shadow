# LEDGER — "stealth" instance (Reaper mission)

Separate ledger for the isolated **"stealth"** Reaper wargame instance, per
Master (2026-07-07). Kept apart from the shared `wargames/LEDGER.md` so the two
concurrent Reaper runs do not contaminate each other. Append-only within a
session; grades are honest — a softened grade hides the plan that dies at first
contact, which is the one failure this loop exists to catch.

**Status vocabulary:** `DRAFTED` · `RED-TEAMED` · `PATCHED` (breaks fixed,
re-graded) · `DONE` (all nine hold AND one honest kill-attempt FAILED) ·
`BLOCKED` · `SPLIT`.

**Isolation note:** one file of the other instance's work
(`wargames/recon/reaper.md`) was read once before Master's isolation instruction;
nothing else from that instance was read (no plans, no red-team, no shared
ledger). All `stealth*` recon/plans were traced independently from the code with
`file:line`. The two red-team subagents were barred from the other instance's
artifacts.

**Split justification (SPLIT):** Reaper is two missions. Seam: a move belongs to
**Part 2** if it changes *what enters Grimoire* or *when Reaper acts
autonomously*; otherwise (how well/safely Reaper reads the public web) it is
**Part 1**. The instruction-like-content DETECTOR sits in Part 2 (the injection
seam) though the brief lists it under Front 2; Part 1's Front 2 wires the
operational responses (backoff/rung-switch/disengage) and calls the Part-2
detector. This mirrors the recon digest §12 split and is decided independently
here.

---

## Recon — DONE — 2026-07-07
`wargames/recon/stealth.md`. Independent, `file:line` throughout, six host
RECON-NEEDED items settled by running read-only checks. Headline: the Front-5
Tier-2 gate ships OPEN at boot (`main.py:674-675`) with TWO ungated high-trust
injection write paths (12h scheduler @0.3 + autonomous `web_fetch` @≤0.7);
scheduler bypasses orchestrator/Cerberus/injection-screen entirely; Cerberus
`APPROVAL_REQUIRED` is decorative (only `DENY` blocks); `stealth_mode` is a dead
flag; SearXNG is actually live+enabled on Citadel (diverges from schema default).

---

### stealth-part1-gathering — PATCHED — pass 1 — 2026-07-07

Plan:      wargames/plans/stealth-part1-gathering.md
Red-team:  wargames/red-team/stealth-part1.md

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — every move has a named test / concrete string; the two vague spots the attacker found (V3 unfalsifiable, backoff sleep-count) were replaced with mechanical thresholds and a loop-liveness assertion.
  2 failure branches        PASS — each move carries a most-likely-failure + counter; M2.1's counter was WRONG on pass 1 (F1) and is now corrected to the true threading model.
  3 fork triggers           PASS — forks read observable values; F2's dead `status_code` fork and F3's false async/sync dichotomy were the two broken triggers, both re-grounded on values the code exposes.
  4 RECON NEEDED marks      PASS — DoH provider, V3 reflector, proxy account, Whisper/finance APIs each marked with an exact check; none smuggled into a confident move.
  5 abort conditions        PASS — A1–A5 present; A1 (stealth-vs-access-control) held under attack (F9).
  6 verification runs       PASS (post-patch) — the F4 gap (green unit tests certify no real TLS/anti-bot) is now explicit: only live V3 certifies Front 1, unit tests don't.
  7 survived red-team       WEAK→addressed — pass 1 landed 1 CRITICAL + 3 HIGH; all patched with catch-tests. NOT yet a clean pass → status PATCHED, not DONE. A confirming pass 2 is required.
  8 executable blind        PASS (post-patch) — the load-bearing false fact (sync-runs-in-thread) that would have misled a blind executor is removed; Move 0 makes the threading model explicit.
  9 gates & autonomy        PASS (post-patch) — G1 reframed to the ACTUALLY-enforced control (push deny-list = Master's checkpoint; auto-commit means "review before commit" was unenforceable, F6); G2 is now a real allowlist mechanism (F7), not a comment.

Changed since last pass (pass 1 red-team → patch):
  - F1 (CRITICAL): added foundational **Move 0** (`asyncio.to_thread` at the adapter choke point) + PF-4; corrected M2.1's false "executor thread" claim; replaced sleep-count test with loop-liveness heartbeat test.
  - F2 (HIGH): M1.2 fork now captures status in the `except HTTPError` block instead of branching on a discarded `status_code`.
  - F3 (HIGH): removed the false "sync scheduler" branch; sync Playwright runs inside Move 0's loop-less worker uniformly.
  - F4 (HIGH): unit tests explicitly do NOT certify Front 1; only live V3 does.
  - F5 (MED): source-eval demotion moved to a NEW `ranking_tier` field; `tier`/`trust_score` untouched; added `test_download_safety_gate_unaffected`.
  - F6 (MED): G1 reframed around push-deny-list + rollback + tests-green.
  - F7 (MED): fingerprint script carries a hardcoded host allowlist (the gate mechanism); V3 gets five falsifiable thresholds.
  - F8 (LOW): PF-1 fork corrected to `config.yaml:98` as the source of `searxng_enabled=True`.
  - F9 held: the stealth-vs-access-control line survived the attacker's hardest push.

---

### stealth-part2-injection-gate — PATCHED — pass 1 — 2026-07-07

Plan:      wargames/plans/stealth-part2-injection-gate.md
Red-team:  wargames/red-team/stealth-part2.md

Self-grade vs SUCCESS.md (1–9):
  1 expected observations   PASS — spy-based row/count assertions throughout; the corpus-quality and evasion gaps got concrete regression tests (zero-width, split-boundary).
  2 failure branches        PASS — each move has a failure + counter; the M4.3 "most likely failure" now names the exact back-door class.
  3 fork triggers           PASS — PF-0/PF-1 forks read grep results; the flag-already-exists fork guards against double-add.
  4 RECON NEEDED marks      PASS — `UNTRUSTED_WEB_TRUST` value, payload corpus, Sentinel suite existence each marked with an exact check.
  5 abort conditions        PASS — A1–A5; A2 (read-side over-claim) and A4 (gate named-not-wired) directly encode the two failure classes the attacker probed.
  6 verification runs       PASS — V-tag inspects the actual stored row; V-gate proves absent-by-default AND refused-on-manual; V-seam honestly records the read-side is invisible, not just unhonored.
  7 survived red-team       WEAK→addressed — pass 1 landed 1 CRITICAL + 1 HIGH + 3 MED; all patched with catch-tests. NOT a clean pass → PATCHED, not DONE.
  8 executable blind        PASS (post-patch) — the gate now has a single firing-guard that closes every entry point; the detector reuses a named existing module rather than an under-specified new build.
  9 gates & autonomy        PASS (post-patch) — G1 enforcement is now DOUBLE (registration + firing guard), each with a test; the earned-by is honestly labeled (only #3 deliverable in this plan; #1 Grimoire, #2 Sentinel, #2 un-runnable today = fail-closed).

Changed since last pass (pass 1 red-team → patch):
  - CRITICAL (gate back door): the gate now wraps the FIRING (early-return in `_run_standing_research` + `run_task` refusal), closing the `/schedule run standing_research` path the pass-1 plan named and walked past; added `test_run_task_refuses_standing_research_when_flag_false`.
  - HIGH (choke guard mis-scoped): tagging extracted to module-level `modules/reaper/tagging.py` imported by both `reaper.py` and `standing_tasks.py`; guard test now spans both files.
  - MED (read side): corrected — recall never returns `safety_class`; earned-by #1 now requires Grimoire to surface AND demote.
  - MED (divergent detector): M4.1 reuses/extends the existing Cerberus `PromptInjectionDetector` instead of building a second one.
  - MED (evasion boundary): normalize zero-width/bidi before matching; inspect full pre-truncation text; two evasion regression tests added.
  - LOW (redirect): mis-framing corrected (`evaluate_source` runs pre-redirect).
  - LOW (Sentinel suite): earned-by #2 marked un-runnable-today / fail-closed.

---

### stealth-part1-gathering — PATCHED — pass 2 — 2026-07-07

Red-team: wargames/red-team/stealth-part1-pass2.md

Pass-2 result: Move 0's core `to_thread` fix HELD (the pass-1 CRITICAL is closed —
verified: the wrap sits at the one `execute` choke point all four dispatch paths
funnel through, Grimoire's RLock serializes concurrent writers, no deadlock). The
stealth-vs-access-control line (F9) survived a second, harder attack. But the
**verification spine took two HIGHs:** P2 — V3's central TLS/JA3 check was
undecidable blind (local Flask sees no handshake, mitmproxy absent, curl_cffi has
no JA3 self-report) → reproduced the "green over a dead path" failure; P1 —
`ConnectionError`/`Timeout` had no browser fork. Plus MED (jitter-fragile liveness
bar, conditional Brave lock) and LOW (ThreadPool invariant).
Patched: JA3 observer named (self-hosted ClientHello capture or approved public
reflector; dormant-not-claimed if neither stood up); ConnectionError/Timeout now
route to browser; two-sided robust liveness bar; unconditional Brave lock;
ThreadPool invariant documented.
Grade delta: 3/6/8 were WEAK pre-patch (V3 undecidable, missing fork, blind-exec
hole); now PASS post-patch. **Still PATCHED, not DONE** — pass 2 landed HIGHs, so
point 7 not yet satisfied.

### stealth-part2-injection-gate — PATCHED — pass 2 — 2026-07-07

Red-team: wargames/red-team/stealth-part2-pass2.md

Pass-2 result: the pass-1 fixes HELD (the `run_task`/`/schedule run` back door is
genuinely dead; the write-side trust cap held under the hardest attack). But a
**NEW CRITICAL:** the gate was anchored to `_run_standing_research` (snippets @0.3)
and left the higher-severity `web_fetch` autonomous full-page write (up to 0.7,
dispatched ungated at `orchestrator.py:5254`) outside Front 5 — "supervised
on-demand" asserted, not wired. Plus HIGH (shared helper dropped `confidence`),
MED×3 (gate breaks 3 real `test_standing_tasks.py` tests with no fork; detector
wrapper didn't compose with `InjectionResult`; normalization could regress
Cerberus's shared path), LOW (read-side invisibility prose-only).
Patched: **Move 4.3b** gates the autonomous `web_fetch` persistence via an
`_autonomous` param flag (G1 enforcement now TRIPLE across all three autonomous
write paths); helper preserves `confidence`/`check_duplicates`; fork added to
update the 3 standing-tasks tests; M4.1 adapts `InjectionResult` + passes
`source="reaper_scrape"`; normalization-safety test for Cerberus; read-side
characterization test.
Grade delta: 9 (gates) was the repeat failure — anchored to the wrong write path
twice. Now TRIPLE-guarded. **Still PATCHED, not DONE** — pass 2 landed a CRITICAL,
so a pass 3 must confirm the gate is finally complete before any DONE claim.

---

### stealth-part1-gathering — DONE — pass 3 — 2026-07-07

Red-team: wargames/red-team/stealth-part1-pass3.md — **verdict: SOUND, no BREAKS
REMAIN.**

Pass-3 was an honest kill-attempt that FAILED on the load-bearing spine (the
attacker used live socket/JA3 probes to try to prove the V3 TLS check was paper —
and proved instead that a non-root stdlib socket certifies a real JA3 fully
locally; loopback JA3 == internet JA3). No new CRITICAL/HIGH. Move 0 (the pass-1
CRITICAL fix) confirmed deadlock-free; F9 (stealth-vs-access-control) held a third
time. Residual MED/LOW patched post-pass-3: T1 dead-vs-tarpit browser fork +
20s cap; T2/T3 JA3 signpost corrected to the stdlib-socket mechanism.

Self-grade vs SUCCESS.md (1–9): **all PASS.**
  1 expected obs PASS · 2 failure branches PASS · 3 fork triggers PASS ·
  4 RECON NEEDED PASS · 5 abort conditions PASS · 6 verification PASS (V3 now
  decidable fully local) · 7 survived red-team **PASS — three passes, the third
  failed to break the spine** · 8 executable blind PASS · 9 gates & autonomy PASS
  (Part 1 changes no autonomy posture; every network layer dormant-or-supervised
  behind wired gates).
**Status: DONE** — all nine hold AND an honest kill-attempt (pass 3) failed.

### stealth-part2-injection-gate — PATCHED (converging) — pass 3 — 2026-07-07

Red-team: wargames/red-team/stealth-part2-pass3.md — **verdict: HOLE FOUND
(CRITICAL).**

Pass 3 found a FOURTH autonomous write path: the async task queue's
`_store_result_in_grimoire` (`async_tasks.py:355`) persists every backgrounded task
result at **0.8**, `source_module="shadow"`, untagged, ungated —
`web_search`/`youtube_transcribe` route async by default and fire from autonomous
sources; `submit_task` strips underscore params so the pass-2 `_autonomous` flag
never survives (fail-open). Verified against code.

**The gate took a CRITICAL on all three passes — a different write path one layer
further out each time. That recurring pattern is itself the finding: path-by-path
gating is the wrong architecture.** Redesign (M4.3b): enumerate ALL SEVEN
Reaper-content write sites (grep-verified across 3 files); funnel through ONE
shared `untrusted_memory_kwargs` (tag) + `reaper_web_persist_allowed` predicate
(gate); make the predicate **fail-CLOSED** (unknown provenance for a Reaper web
tool → not persisted); thread real `source` into `submit_task` (it hardcoded
"user"); route the async-queue Reaper-tool write through the cap (≤0.3 + tag) not
0.8; add a **completeness meta-test** so a pass-4 eighth path fails a test, not an
attacker. Pass-2 fixes all confirmed held.

Self-grade vs SUCCESS.md (1–9):
  1 PASS · 2 PASS · 3 PASS · 4 PASS · 5 PASS · 6 PASS · 7 **WEAK — the gate has
  not yet survived a clean pass (3-for-3 CRITICALs)** · 8 PASS · 9 **WEAK→PASS-by-
  construction — the enumerate-all + fail-closed + completeness-meta-test redesign
  closes the class, but it has not been re-attacked.**
**Status: PATCHED, converging — NOT DONE.** The redesign closes the write class by
construction, but given the 3-for-3 record, point 7 is not satisfied until a
pass-4 confirms no eighth path. Pass-4 dispatched.

---

### stealth-part2-injection-gate — PATCHED (write-class CLOSED, plumbing re-fixed) — pass 4 — 2026-07-07

Red-team: wargames/red-team/stealth-part2-pass4.md — **verdict: GATE CLASS CLOSED
on the write-path axis (no 8th path found); path-7 FIX had 1 HIGH + 2 MED.**

The decisive result: the attacker ran the FULL enumeration (`grep -rn ".remember("
modules/` → 41 sites, every one traced) and confirmed the SEVEN the plan names are
the **complete** set of Reaper-scraped-content writes. **The recurring "one more
door" pattern (a new autonomous write path each of passes 1–3) is retired** — the
enumerate-all redesign achieved its purpose. But the path-7 fix itself was buggy:
- **B-1 (HIGH):** threading `source` into `create_task` throws `ValueError` on
  autonomous sources (`TaskSource` 4-value enum, coerced at `task_queue.py:406`),
  swallowed → silent sync fallback where the gate never runs. My fix disabled the
  gate. **Re-fixed:** provenance rides in the task PAYLOAD (`origin_autonomous`,
  default True = fail-closed), not the enum.
- **B-2/B-3 (MED):** production re-plans through the graph storing `tool_name=
  "graph"`, so the submitted-tool predicate misses it and the plan's test only
  passed on the dead no-orchestrator branch. **Re-fixed:** graph branch inspects
  `state["tool_results"]` for `.module=="reaper"`; tests drive the production
  branch; meta-test asserts the dual-purpose `355` write is gated.

Self-grade vs SUCCESS.md (1–9):
  1 PASS · 2 PASS · 3 PASS · 4 PASS · 5 PASS · 6 PASS · 7 **WEAK — write-CLASS
  survived pass 4 (no 8th path), but the B-1/B-2/B-3 plumbing re-fix is itself
  un-red-teamed** · 8 PASS · 9 **PASS-by-construction, plumbing un-confirmed** —
  the enumerate-all + fail-closed + graph-branch-module-check + completeness
  meta-test closes the class; the corrected wiring has not been re-attacked.
**Status: PATCHED — write-class CLOSED, final plumbing un-confirmed. NOT DONE.**

---

## Final standing — after 4 red-team passes (7 attacker runs)

- **Part 1 (stealth + gathering): DONE.** Survived a clean pass-3 kill-attempt on
  its load-bearing spine (verified with live probes); MED/LOW polish patched. All
  nine hold.
- **Part 2 (injection + gate): PATCHED, write-class CLOSED, NOT DONE.** Pass-4
  retired the recurring risk — the seven Reaper→Grimoire write paths are now
  enumerated-complete and each tag+gated behind one fail-closed choke with a
  completeness meta-test. The only residual is that the final B-1/B-2/B-3 plumbing
  re-fix has not itself been re-attacked. **One pass-5 (Part 2 only) would confirm
  it; that is Master's call — the discovery risk is retired, only wiring
  confirmation remains.**

**Strategic finding for Master (Opus-session decision, not a Claude Code patch):**
the injection gate needing FOUR passes to enumerate every autonomous
Reaper→Grimoire write path proves Reaper-side gating is inherently fragile — it
must track seven scattered write sites across three files, and any new write path
re-opens the hole (the completeness meta-test mitigates but cannot prevent this at
review time). The durable fix is a **single enforced Grimoire-write boundary**:
all Reaper-originated content passes one choke that tags untrusted + honors the
Tier-2 gate, so no future write site can bypass it. That belongs to the Grimoire
mission's write-side, and composes with its read-side demotion (earned-by #1). The
"stealth" instance recommends the Reaper-side gate (this plan) as the interim, and
the write-boundary consolidation as the durable architecture.
