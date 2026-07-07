# BATTLE PLAN — Reaper Part 2: Injection-Source Discipline + Tier-2 Gate (Fronts 4–5 + Front-2 detector)

**Instance:** "stealth" (isolated run). **Executor:** Opus 4.8, max effort.
**Recon base:** `wargames/recon/stealth.md` (spot-verify `file:line`; treat every
`RECON NEEDED` as unsettled until its check runs).
**Scope:** The injection seam and the autonomy gate — the highest-severity half.
- **Front-2 detector:** the instruction-like-content inspector (recon §5: the
  subtle "this page is trying to instruct me" recognition is unbuilt).
- **Front 4:** every Reaper write to Grimoire tagged untrusted-at-source, capped
  at the trust it earned, with the instruction flag riding along — on BOTH the
  `web_fetch` path and the scheduler path.
- **Front 5:** close the currently-OPEN scheduler gate (recon §0) with a concrete
  earned-by condition; keep supervised on-demand research available.

**Depends on Part 1** only at the seam stub `_inspect_content` (Part 1 M2.4
leaves an inert stub; Part 2 replaces it with the real detector and wires it to
the write). If Part 1 has not run, Part 2 creates `_inspect_content` itself —
**Fork PF-0 below.**

**The bar (binds every move):** "A plan where Reaper writes scraped content at
anything above untrusted has failed this front" (brief, Front 4). Web-scraped
content is attacker-controllable; its earned trust is **untrusted**, regardless
of domain reputation. Domain reputation (Tier-1 = 0.7, recon §6) survives only
as *ranking metadata*, never as stored `trust_level`.

---

## Pre-flight (read-only)

**PF-0. Detect whether Part 1's seam stub exists.**
Run: `grep -n "_inspect_content" modules/reaper/reaper.py`
- **Expected observation (Part 1 ran):** one def + one call site in `fetch_page`.
  Part 2 replaces the def body (M4.1) and adds the tag wiring (M4.2).
- **Fork trigger:** **if** grep returns nothing (Part 1 did not run) → Part 2
  **creates** `_inspect_content` and inserts the single call site in `fetch_page`
  itself as part of M4.1. Do not assume the stub exists.

**PF-1. Confirm the open-gate finding is still true (recon §0).**
Run:
```
grep -n "StandingTaskScheduler(" main.py
grep -n "add_job\|autonomous_research_enabled\|_run_standing_research" modules/shadow/standing_tasks.py
python -c "from shadow.config import config as c; print('flag_exists', hasattr(c.reaper,'autonomous_research_enabled'))"
```
- **Expected observation:** scheduler constructed at `main.py:674`;
  `add_job(self._run_standing_research, "interval", hours=12, …)` present in
  `standing_tasks.py:77-84`; `flag_exists False` (the gate flag does NOT exist
  yet — this plan adds it).
- **Fork trigger:** **if** `flag_exists True` already → the gate was added by
  another instance; re-read `reaper_settings.py` and **do not double-add**;
  verify the existing flag actually gates `add_job` (the "looks governed but
  isn't" trap — a flag that exists but doesn't gate the job is worse than none).
- **Abort trigger (A1):** if the scheduler is found to have ALREADY written
  autonomous scraped content to Grimoire at trust > 0.3 during this session's
  uptime, note it — the mission is closing a live hole, handle with care
  (no data deletion without Master + backup, per policy).

**PF-2. Baseline green + rollback point.**
`python -m pytest tests/test_reaper*.py tests/test_*standing* -q` (record counts;
recon §8 = 107 for reaper) and `git rev-parse HEAD` (verified rollback = the
earned-by for every code-write gate). Do not build on a red baseline (Abort A5).

---

## FRONT 2 (detector) — Move 4.1: the instruction-like-content inspector

**Do — REUSE, don't rebuild (red-team MED).** A full `PromptInjectionDetector`
already exists at `modules/cerberus/injection_detector.py:28` with an `analyze()`
pipeline (`:94`) and a regex set (`ignore previous instructions`, `disregard …
instructions`, `new instructions:`, role-hijack). It is used on `user_input` at
orchestrator Step 1.5. **First** `grep -n "class PromptInjectionDetector\|def
analyze" modules/cerberus/injection_detector.py` and **adapt that detector to
scraped content** rather than building a divergent second one (the plan's own
"do not invent divergent payload sets" rule applies to Cerberus too). **The wrapper must ADAPT, not assume the shape (pass-2 MED).** `analyze` has
signature `analyze(input_text, source, request_history=None) -> InjectionResult`
(`injection_detector.py:94`) and returns an `InjectionResult(score, flags,
action)` — NOT the plan's dict. Implement:
```
def _inspect_content(self, text, url):
    r = self._injection_detector.analyze(normalize(text), source="reaper_scrape")
    return {"instruction_like": r.action in ("block","warn") or r.score >= 0.5,
            "injection_score": r.score, "matched": r.flags}
```
Pass the required `source="reaper_scrape"` (the detector already documents this
value, `:104`). Extend the shared detector (in `injection_detector.py`) with
scraped-content patterns (tool-call-shaped blocks, base64/hex blobs,
HTML-comment/`display:none` imperatives) so Cerberus, Reaper, and Sentinel key off
ONE pattern set.

**Normalization must not break Cerberus's live path (pass-2 MED).** `analyze` is
already on the orchestrator Step 1.5 `user_input` path. Add the
zero-width/bidi/NFKC `normalize()` INSIDE `analyze` (so all callers benefit) but
add `tests/test_injection_detector.py::test_normalization_preserves_existing_verdicts`
— run the detector's existing user-input fixtures before/after adding
`normalize()` and assert identical `(score, flags, action)` on every one, so the
scraped-content hardening cannot regress Cerberus's user-input screening.

**Two layers (in the shared detector):**
1. **Deterministic patterns** (fast, always on) — the existing set + the
   scraped-content additions above.
2. **Optional phi4-mini tiebreak** (already the Reaper scoring model,
   `config.py:273` — no new dep): invoked ONLY when the deterministic score is in
   a mid band, so a hostile page can't force a model-call storm; phi4 outage falls
   back to the deterministic verdict, failing TOWARD flagging on ambiguity.

**Normalization + inspection boundary (red-team MED — the evasion gaps):**
- **Normalize BEFORE matching:** strip zero-width (`​`–`‍`,`﻿`) and
  Unicode bidi controls, and NFKC-fold, so `"sy​tem:"` matches `system:`.
  Matching raw text lets the plan's own example payload slip through.
- **Inspect the FULL extracted text, pre-truncation** — `fetch_page` stores
  `text[:WEB_MAX_ARTICLE_CHARS]` (`reaper.py:973`, 8000 chars, `config.py:219`),
  but `_inspect_content` must receive the **full `text`**, so a payload beyond the
  8000-char boundary is still detected and its flag rides on the stored slice.
  Pass `text` (not `content`) to the inspector at every call site.

**Expected observation:**
`tests/test_reaper_injection.py::test_injection_payloads_flagged` — a table of
≥12 known payloads each returns `instruction_like=True`, `injection_score >= 0.5`;
`test_benign_content_not_flagged` — benign article/doc/reddit samples return
`instruction_like=False`; plus the two red-team evasion regressions:
`test_zero_width_obfuscation_stripped` (a `"sy​stem:"` payload with an embedded
zero-width char is flagged after normalization) and
`test_split_payload_across_8000_boundary_flagged` (a payload whose trigger sits
at char 9000 of a 12000-char page is flagged because `_inspect_content` saw the
full text, even though only `text[:8000]` is stored). All green.

**Most likely failure:** false positives on legitimate content that *discusses*
prompt injection (a security blog, an LLM tutorial). **Cause:** keyword matching
can't tell mention from use. **Counter:** require structural corroboration for
the borderline patterns (position: leading/trailing imperative aimed at "you";
delimiter abuse; hidden-element origin) before flagging; route mentions-only to
the phi4 tiebreak; add `test_security_article_about_injection_not_flagged` as a
first-class regression (this is THE false-positive that erodes trust in the
flag).

**Fork with trigger:** **if** phi4-mini is unreachable at call time (Ollama down)
→ use the deterministic verdict only and log `logger.warning("injection tiebreak
unavailable — deterministic verdict")`. Never block the fetch on a scoring-model
outage; never silently upgrade an ambiguous verdict to "safe" because the model
was down (fail toward flagging on ambiguity).

**RECON NEEDED:** the canonical payload corpus. **Check:** if Sentinel's mission
ships an adversarial injection corpus (`grep -rn "injection" tests/ | grep -i
sentinel`), reuse it so Reaper's detector and Sentinel's suite test the same
payloads (the seam, recon §12). If absent, build the corpus here and note it for
Sentinel to adopt. Do not invent divergent payload sets across the two missions.

---

## FRONT 4 — Move 4.2: untrusted tagging at every write

**Do:** Introduce the tagging as a **module-level function importable by BOTH
`reaper.py` and `standing_tasks.py`** (red-team HIGH: a `self.`-method on Reaper
cannot cover the sixth write path, which lives in `StandingTaskScheduler` with no
Reaper instance). Put it in a new `modules/reaper/tagging.py`:
```
UNTRUSTED_WEB_TRUST = 0.2  # RECON NEEDED: align to grimoire's lowest external constant; must be <= 0.3

def untrusted_memory_kwargs(*, content, source, category, tags, url, reputation,
                            inspection_text, extra_meta, inspect_fn,
                            confidence, check_duplicates=True, **passthrough):
    # pass-2 HIGH: PRESERVE every field the original call sites set (confidence,
    # check_duplicates, parent_id, …) — only OVERRIDE trust_level + safety_class
    # + the injected metadata. Dropping confidence silently erased the
    # relevance-derived score the pipeline exists to compute.
    inspection = inspect_fn(inspection_text, url)   # FULL pre-truncation text (M4.1 boundary)
    return dict(
        content=content, source=source, source_module="reaper",
        category=category, tags=tags,
        confidence=confidence,                               # PRESERVED (0.5 / score-10 / upvote / 0.6)
        check_duplicates=check_duplicates,                   # PRESERVED per call site
        trust_level=min(reputation, UNTRUSTED_WEB_TRUST),    # cap: never above untrusted
        safety_class="untrusted_web",                        # the load-bearing marker
        metadata={**extra_meta,
                  "source_trust_reputation": reputation,     # 0.7 survives as RANKING metadata only
                  "instruction_like": inspection["instruction_like"],
                  "injection_score": inspection["injection_score"]},
        **passthrough,                                       # parent_id, model_used, etc.
    )
```
The five call sites keep passing their existing `confidence` (fetch_page 0.5,
research `score/10.0`, Reddit `min(score/100,1)`, YouTube 0.6) and their
`check_duplicates` value; the helper only re-writes trust + safety_class + meta.
Add `test_helper_preserves_confidence_and_dedup` asserting a call with
`confidence=0.9, check_duplicates=False` round-trips both into the `remember`
kwargs — the exact pass-2 regression.
`reaper.py` calls `self.grimoire.remember(**untrusted_memory_kwargs(...,
inspect_fn=self._inspect_content))`; `standing_tasks.py:236` and
`async_tasks.py:355` use the shared module-level function likewise. **Route ALL
SEVEN Reaper-content write paths through it** (the exhaustive set is enumerated in
M4.3b's table — grep-verified across three files): `fetch_page` (`reaper.py:988`),
research full/summary (`:1192`, `:1217`), Reddit (`:1377`), YouTube (`:1625`), the
scheduler write (`standing_tasks.py:236`), AND **the async task queue's
`_store_result_in_grimoire` (`async_tasks.py:355`) when the completed task's tool
is a Reaper web tool** (pass-3 CRITICAL — writes at 0.8 today, `source_module=
"shadow"`, so a `reaper`-scoped guard misses it). The change everywhere:
**`safety_class` marker + instruction flag**, and — critically — capping web-scrape
trust (0.7, and the queue's 0.8) down to `UNTRUSTED_WEB_TRUST`.

**`UNTRUSTED_WEB_TRUST` value — RECON NEEDED, with a safe default.** **Check:**
`grep -n "TRUST_" modules/grimoire/grimoire.py` for the project's trust taxonomy;
set `UNTRUSTED_WEB_TRUST` to Grimoire's lowest "external unverified" constant. If
no such constant, default **0.2** (below the 0.3 community floor, above the 0.1
tier-4). The exact number is less important than: (a) it is ≤ 0.3, and (b)
`safety_class="untrusted_web"` is set unconditionally — the marker, not the
number, is what the read side keys on.

**Expected observation:**
- `tests/test_reaper_injection.py::test_all_write_paths_tag_untrusted` — a spy
  Grimoire captures every `remember` call from `fetch_page`, `research`,
  `_store_reddit_post`, `youtube_transcribe`, and `_run_standing_research`; each
  call has `safety_class == "untrusted_web"`, `trust_level <= 0.3`, and
  `metadata` carrying `instruction_like` + `source_trust_reputation`. Green.
- `tests/test_reaper_injection.py::test_tier1_domain_no_longer_writes_0_7` — a
  `docs.python.org` page (Tier-1, reputation 0.7) is stored with `trust_level <=
  UNTRUSTED_WEB_TRUST`, and `metadata["source_trust_reputation"] == 0.7`. Green.
  **This is the exact bar the brief sets** ("scraped content above untrusted =
  failed"): the test would fail on today's code (writes 0.7), passes after M4.2.

**Most likely failure:** a write path bypasses the helper (red-team HIGH: the
sixth path lives in `standing_tasks.py`, which a `reaper.py`-scoped guard cannot
see). **Cause:** the choke point is a convention; a single-file guard misses the
scheduler write. **Counter:** the guard must span THREE files (pass-1 found the 2nd file, pass-3
the 3rd): `test_no_untagged_reaper_remember` asserts every Reaper-content
`remember(` site — in `reaper.py`, `standing_tasks.py`, AND `async_tasks.py` — is
built via `untrusted_memory_kwargs`. Concretely: `reaper.py` has zero
`self.grimoire.remember(` outside the helper; `standing_tasks.py`'s
`_run_standing_research` spreads it; `async_tasks.py`'s `_store_result_in_grimoire`
routes Reaper-tool results through it. This is the same guard as the M4.3b
**completeness meta-test** (`test_no_reaper_write_bypasses_tag_or_gate`) — a guard
scoped to fewer files is exactly the hole three passes kept finding.

**Fork with trigger:** **if** capping web-scrape trust to 0.2 breaks an existing
test that asserts 0.7 (e.g. a research-pipeline test) → that test encoded the
*old* insecure behavior; update it to assert the capped value + the reputation
metadata, and note the change in the commit. Do NOT keep 0.7 to make an old test
pass (that would re-open the hole to satisfy a stale assertion — the exact
anti-pattern SUCCESS warns of).

**Abort trigger (A2):** `safety_class` is a real Grimoire column (recon §6:
`grimoire.py:381`) but nothing reads it yet. Part 2 makes Reaper WRITE the
marker; it must NOT also claim the read-side demotion works. If verification
tempts a claim that untrusted content is demoted at recall → STOP: that is the
Grimoire mission (Front 5 earned-by condition 1). Reaper's half is the write; say
so.

---

## FRONT 5 — Move 4.3: close the open scheduler gate (THE deliverable)

**Do:** Add `autonomous_research_enabled: bool = False` to `ReaperSettings`
(`reaper_settings.py`) and a mirror default in `config.yaml`. In
`StandingTaskScheduler.start()` (`standing_tasks.py:65-100`), **guard the
`add_job` for `standing_research`**:
```
from shadow.config import config
if config.reaper.autonomous_research_enabled:
    self._scheduler.add_job(self._run_standing_research, "interval", hours=12, id="standing_research", …)
else:
    self._logger.info("standing_research DORMANT — autonomous_research_enabled=False (Tier-2 gate closed)")
```
**CRITICAL fix — red-team found the gate had a back door.** Gating only `add_job`
leaves `run_task("standing_research")` (`standing_tasks.py:110-124`) — which calls
`_run_standing_research()` DIRECTLY and is live on the CLI at `main.py:577` via
`/schedule run standing_research` — firing the autonomous write with the flag
False. **The gate must wrap the FIRING, not the registration.** Two enforcement
points, both required:

1. **Guard `add_job` (registration)** — as above, so the 12h timer is dormant.
2. **Guard the firing function itself** — add to the top of `_run_standing_research`
   (`standing_tasks.py:209`):
   ```
   from shadow.config import config
   if not config.reaper.autonomous_research_enabled:
       self._last_status["standing_research"] = "refused: Tier-2 gate closed"
       self._logger.warning("standing_research REFUSED — autonomous_research_enabled=False")
       return
   ```
   This closes BOTH the timer AND the `run_task`/`/schedule run` manual path in one
   place — the firing cannot happen through any entry point while the flag is
   False. (Also add an early guard in `run_task` so the CLI returns a clear
   "gate closed" message rather than silently no-op'ing.)

Default False → the job is never registered AND cannot be fired manually.
`self_analysis` (Omen) and `grimoire_stats` are unaffected. Supervised on-demand
`web_fetch`/`web_search` remain available (a real Master request drives them) and
write untrusted-tagged (M4.2).

**Expected observation:**
- `tests/test_standing_tasks_gate.py::test_research_job_absent_when_flag_false` —
  `start()` with `autonomous_research_enabled=False`; assert
  `"standing_research" not in {j.id for j in scheduler._scheduler.get_jobs()}`
  and a `logger.info`/`warning` containing `"DORMANT"`/`"REFUSED"`. Green.
- **`tests/test_standing_tasks_gate.py::test_run_task_refuses_standing_research_when_flag_false`
  (the back-door test)** — with the flag False, call
  `scheduler.run_task("standing_research")`; assert a **spy Reaper's `execute`
  was called 0 times** AND a **spy Grimoire's `remember` was called 0 times** AND
  the return string contains `"gate closed"`/`"refused"`. This is the test that
  proves the manual path is truly gated — the exact break the red-team hit.
- `test_research_job_present_and_fires_when_flag_true` — flag True: the job IS
  registered AND `run_task("standing_research")` reaches `reaper.execute`. Green.
- **Live boot check (V-gate):** start Shadow with default config; startup line
  must NOT claim research is scheduled; then `/schedule run standing_research` at
  the CLI must return the "gate closed" message and write nothing.

**Most likely failure:** the executor gates `add_job` (registration) but forgets
the firing guard — the exact red-team back door. **Cause:** treating "dormant at
boot" as the whole gate. **Counter:**
`test_run_task_refuses_standing_research_when_flag_false` fails loudly if the
firing guard is missing. Do NOT mark Front 5 done until BOTH gate tests are green
(Abort A4).

**Fork with trigger — the gate breaks existing tests (pass-2 MED):** the default
`autonomous_research_enabled=False` will FAIL three real tests in
`tests/test_standing_tasks.py` that encode the OLD ungated behavior:
`:130` asserts `job_ids == {"self_analysis","standing_research","grimoire_stats"}`
(now `standing_research` is absent by default) and `:187-205` assert
`run_task("standing_research")` succeeds and writes. **These tests encoded the
open gate — update them, do not keep the gate open to satisfy them** (the same
anti-pattern as the trust-cap fork). Rewrite them to the gated contract: with the
flag False, `standing_research` is absent from `get_jobs()` and `run_task` refuses
with zero writes; with the flag True (a `monkeypatch.setattr(config.reaper,
"autonomous_research_enabled", True)` fixture), the job registers and `run_task`
fires. Do NOT special-case only the reaper tests — grep first:
`grep -rn "standing_research" tests/` and update every assertion of the old
behavior.

**Fork with trigger:** **if** Master wants autonomous research ON now →
enabling requires the **earned-by** below to be TRUE first. The executor does NOT
flip the flag to True as part of this build; it ships False. Flipping to True is
a separate, gated Master action (Gate G1).

### Front-5 earned-by condition (concrete — what must be TRUE before the flag may go True)
All three, each with the exact check the executor/Master runs at flip time:
1. **Grimoire read-side demotion enforced.** Precise status (red-team MED):
   `recall()` today does not merely ignore `safety_class` for filtering — the
   returned memory dict (`grimoire.py:1142-1161`) **does not include
   `safety_class` at all**, so a consumer cannot even SEE Reaper's marker. So the
   Grimoire mission must do TWO things: (a) surface `safety_class` in the recall
   result dict, AND (b) demote/wrap-as-data on it by default. **Check:**
   `python -c "…m=grimoire.recall(<query hitting an untrusted_web memory>)[0]; print('safety_class' in m, m.get('trust_level'))"` returns `True` and a demoted
   trust, OR `grep -rn "safety_class" modules/grimoire/grimoire.py` shows it read
   at recall. Today: neither → **NOT met** (this is the Grimoire mission's
   deliverable, not Reaper's — Reaper writes the marker; it cannot make recall
   honor it).
2. **Sentinel adversarial injection suite green.** **Un-runnable today (red-team
   LOW):** `grep -rln injection tests/ | grep -i sentinel` returns nothing — no
   Sentinel injection suite exists in the tree. So this condition CANNOT be
   satisfied until the Sentinel mission ships that suite; the gate stays
   fail-closed (correct). **Check when it exists:** `pytest tests/ -k "sentinel
   and injection" -q` passes end to end, proving a stored payload does not
   execute, AND its corpus is the SAME shared set as M4.1's detector. **Master
   must read this as: of the three flip conditions, only #3 is deliverable inside
   this plan; #1 needs the Grimoire mission and #2 needs the Sentinel mission.**
3. **Reaper source-tagging verified.** Check: V-tag (below) green AND a live
   hostile-page fetch lands `safety_class="untrusted_web"` + `instruction_like`
   flagged. This one is delivered BY this plan (M4.1+M4.2).

Until all three hold, `autonomous_research_enabled=False`; Reaper runs supervised
on demand only.

---

## FRONT 5 — Move 4.3b: close the WRITE CLASS, not one door at a time (passes 1–3 each found one more)

**The pattern that IS the finding.** Three red-team passes each found a different
autonomous Reaper→Grimoire write path one layer further out: pass 1 the
`run_task`/`/schedule run` firing; pass 2 the `web_fetch` full-page persist; pass
3 the async task queue's post-completion write. Gating path-by-path has failed
three times. **The root cause is architectural: Reaper-originated content reaches
Grimoire through SEVEN scattered `remember()` sites across THREE files, each with
its own trust and its own (missing) gate.** The fix enumerates all seven, funnels
them through ONE shared tag+gate, and defaults **fail-closed** so an unenumerated
eighth path is gated by default rather than open by default.

**The exhaustive write set (verified by grep, `source_module` in code):**
| # | Site | trust today | src_module | reachable autonomously via |
|---|---|---|---|---|
| 1 | `reaper.py:988` fetch_page | ≤0.7 | reaper | web_fetch tool (sync) |
| 2 | `reaper.py:1192` research full | ≤0.7 | reaper | deferred graph → research() |
| 3 | `reaper.py:1217` research summary | ≤0.7 | reaper | deferred graph → research() |
| 4 | `reaper.py:1377` Reddit | 0.3 | reaper | reddit tools |
| 5 | `reaper.py:1625` YouTube | 0.3 | reaper | youtube_transcribe (async by default) |
| 6 | `standing_tasks.py:236` scheduler | 0.3 | reaper | 12h timer + run_task |
| 7 | `async_tasks.py:355` queue result | **0.8** | **shadow** | ANY backgrounded task incl. web_search/youtube (`_LONG_RUNNING_TOOLS`, `orchestrator.py:848`); deferred graph (`source="autonomous"`, `async_tasks.py:246`) |

Path 7 is the pass-3 CRITICAL: it writes **every** backgrounded task result at
**0.8**, `source_module="shadow"` (so a `reaper`-scoped guard can't see it),
untagged, ungated. And `submit_task` **strips underscore params**
(`orchestrator.py:5232`), so the pass-2 `_autonomous` flag never reaches a
backgrounded tool — the flag approach is fail-OPEN for async.

**Do — one shared tag+gate, three files, fail-closed:**
1. **Shared predicate** in `modules/reaper/tagging.py`:
   `reaper_web_persist_allowed(source, tool_name, gate_open) -> bool` — returns
   True only when `tool_name` is NOT a Reaper web tool, OR `gate_open`, OR
   `source in USER_SOURCES = {"user","telegram","discord"}`. **Unknown/absent
   source for a Reaper web tool → False (fail-closed).** `REAPER_WEB_TOOLS =
   {"web_search","web_fetch","youtube_transcribe","reddit_search_json","reddit_monitor"}`.
2. **Provenance must SURVIVE to the async store — via the PAYLOAD, not the
   `TaskSource` enum (pass-4 B-1).** Do NOT thread the orchestrator's `source`
   into `create_task(source=…)`: `TaskSource` is a 4-value enum
   (`user/module/scheduled/event`, `task_queue.py:35-40`) and `create_task`
   coerces via `TaskSource(source)` (`:406`), so `source="autonomous"` raises
   `ValueError` — swallowed by the async-submit `try/except`
   (`orchestrator.py:5246`), silently falling the task back to **sync dispatch
   where the path-7 gate never runs.** The enum-thread fix would DISABLE the gate.
   Instead, carry autonomy provenance in the task **payload**: at the orchestrator
   submit site, set `params["_origin_autonomous"] = is_autonomous` — but note
   underscore params are stripped (`orchestrator.py:5232`), so add a dedicated
   non-stripped submit argument (extend `submit_task(..., origin_autonomous: bool
   = True)` defaulting **True = fail-closed**, stored in the task payload). The
   graph branch (`async_tasks.py:245-246`) is **definitionally autonomous**
   (hardcoded `source="autonomous"`), so its `origin_autonomous` is always True.
   `_store_result_in_grimoire` reads `task.payload["origin_autonomous"]` (absent →
   True → gated).
3. **Gate every persist site on the predicate:**
   - Sync `web_fetch` (path 1): adapter passes `store_in_grimoire=reaper_web_persist_allowed(source, "web_fetch", gate_open)`. Source reaches the adapter via a NON-underscore param (underscore is stripped for async; for sync it survives, but use a stable key the async path also sets).
   - Scheduler (path 6): already guarded by M4.3's `_run_standing_research`
     early-return (source is implicitly autonomous).
   - Async queue (path 7): `_store_result_in_grimoire` must handle BOTH worker
     branches (`async_tasks.py:241-261`) — the plan's earlier single-branch test
     was green only on the no-orchestrator `else` branch that never runs in
     production (pass-4 B-3). **Discriminate Reaper content per branch (pass-4
     B-2):**
     - *direct branch* (`else`, no orchestrator): key on the submitted
       `task.tool_name in REAPER_WEB_TOOLS`.
     - *graph branch* (production, orchestrator wired): the result is stored as
       `tool_name="graph"`, so the submitted tool is lost — instead inspect the
       graph `state["tool_results"]` (each is a `ToolResult` with `.module`,
       reachable in `_result_from_graph_state`, `async_tasks.py:297`) and treat the
       result as Reaper content if `any(getattr(tr,"module",None) == "reaper" for
       tr in state["tool_results"])`.
     Then apply the predicate with `origin_autonomous` + the Reaper-content flag:
     when disallowed (autonomous + gate closed) → do NOT persist the Reaper
     content; when allowed but Reaper content → route through
     `untrusted_memory_kwargs` (cap ≤0.3, tag, inspect) NOT the blanket 0.8;
     non-Reaper results persist unchanged (protects Omen self-analysis @0.9).
     **RECON NEEDED:** confirm `_result_from_graph_state` still has `state` in
     scope to read `tool_results` — `grep -n "tool_results" modules/shadow/async_tasks.py`;
     it does today (`:297+`), but verify before relying on it.
   - research pipeline (paths 2,3): **settled — NOT an autonomous vector.**
     `research()`/`run_standing_research()` are NOT router-reachable (recon §2), so
     the deferred graph (which dispatches through the router) reaches `web_fetch`/
     `web_search` (paths 1/7), never `research()`. And the deferred graph's
     "dormancy gate" (`orchestrator.py:1134`) is **module-dormancy** (Morpheus-
     style), NOT the Reaper Tier-2 flag — verified, so do not rely on it to gate
     Reaper. Paths 2,3 still get the M4.2 tag for the `__main__`/internal callers,
     but need no autonomy gate because nothing autonomous reaches them.

**Expected observation:**
- `tests/test_reaper_gate.py::test_async_queue_graph_branch_reaper_result_capped`
  — **the PRODUCTION branch (orchestrator wired, pass-4 B-3):** a completed graph
  task whose `state["tool_results"]` contains a `ToolResult(module="reaper")` is
  persisted with `trust_level <= 0.3` + `safety_class="untrusted_web"` (NOT 0.8).
  The plan's earlier direct-branch-only test would pass vacuously in production —
  this test drives the wired branch. Green (fails today).
- `test_async_queue_reaper_result_not_persisted_when_gate_closed_and_autonomous` —
  graph task, `origin_autonomous=True`, gate False, Reaper in `tool_results` → spy
  `remember` **0 times**. Green.
- `test_async_queue_direct_branch_reaper_tool_capped` — the `else`/no-orchestrator
  branch, `tool_name="web_search"` → capped+tagged (covers both branches).
- `test_async_queue_non_reaper_tool_unchanged` — a non-Reaper backgrounded task
  still stores at its normal trust (the gate must not break other modules'
  results). Green.
- `test_submit_task_propagates_source` — `_step5_execute` with `source="autonomous"`
  backgrounding a tool → the AsyncTask records `source="autonomous"`, not `"user"`.
- `test_unknown_source_reaper_tool_fails_closed` — predicate with `source=None`,
  a Reaper web tool, gate False → returns False (fail-closed).
- **Completeness meta-test** `test_no_reaper_write_bypasses_tag_or_gate` — assert
  the six single-purpose sites (`reaper.py`×5, `standing_tasks.py:236`) go through
  `untrusted_memory_kwargs`; for the **dual-purpose** `async_tasks.py:355` write
  (serves Reaper AND non-Reaper results, so it can't be grep-classified — pass-4
  B-3), assert instead that the `remember(` there is **inside the branch that
  checks the Reaper-content flag + predicate** (i.e. not an unconditional 0.8
  write). If a grep finds a NEW `remember(` reachable from Reaper content outside
  the known set, FAIL with "new Reaper write path — route it through the choke."
  Pass-4 ran the full 41-site enumeration and found no eighth path, so this guard's
  job is to catch a FUTURE one.

**Most likely failure:** gating path 7 breaks OTHER modules' backgrounded results
(Omen self-analysis, security scans also route async). **Cause:** the gate keys on
tool being a Reaper web tool — if it over-matches, non-Reaper results get capped.
**Counter:** the predicate returns True (persist normally) for any tool NOT in
`REAPER_WEB_TOOLS`; `test_async_queue_non_reaper_tool_unchanged` proves it.

**Abort trigger:** if propagating `source` into `submit_task` ripples into other
`submit_task` callers (`async_tasks.py:11` docstring example, any test) → update
call sites; if it forces a signature change to `AsyncTask` that other code
depends on positionally → STOP (Abort A4) and flag.

**Front 5 is not done until ALL of M4.3 (scheduler double-guard), M4.3b (web_fetch
+ async-queue + fail-closed predicate), and the completeness meta-test are green.**
Three passes proved a single door is never the whole gate.

---

## Move 4.4 — the standing gate lines (make the permanent boundaries explicit)

No new capability; these are assertions the plan encodes so the executor and
Master share them:
- **CAPTCHA-solving-service** — last-resort, never default, never autonomous,
  Master per-use approval (Gate G5). Part 1 M2.2 disengages; nothing here solves.
- **Residential proxies / paid infra** — Master-approved (Part 1 Gate G5;
  restated).
- **The permanent line** — Reaper never authenticates as Master into an account,
  never accesses non-public content, never crosses from reading into acting.
  External-facing actions (posting, submitting, purchasing) require explicit
  Master approval (standing policy). Encoded as Abort A1.

---

## Abort conditions

- **A1 — reading→acting / access-control crossing.** Any move where Reaper
  authenticates, reaches non-public content, or takes an external-facing action.
  Mission failure — STOP, flag.
- **A2 — read-side over-claim.** Claiming untrusted content is *demoted at
  recall* — that is the Grimoire mission, not this one. Reaper tags at write; say
  only that.
- **A3 — a write path left untagged.** If `test_no_direct_remember_in_reaper` or
  `test_all_write_paths_tag_untrusted` is red, the seam has a hole — do not ship.
  A single untagged path is a full Front-4 failure.
- **A4 — gate named but not wired.** If the flag exists but
  `test_research_job_absent_when_flag_false` is red, the gate is decorative
  (recon §7's exact failure class). Do not mark Front 5 done.
- **A5 — red baseline / data-loss.** Red baseline (PF-2) → don't build. Never
  delete existing Grimoire rows to "clean up" old high-trust scraped content
  without Master approval + backup (policy: never delete without backup).

---

## Verification runs (built ≠ done; live = done)

- **V1 — unit suite.** `python -m pytest tests/test_reaper_injection.py
  tests/test_standing_tasks_gate.py -q` → all green, AND
  `python -m pytest tests/test_reaper*.py -q` still passes (updated for the
  trust-cap change per the M4.2 fork), AND `tests/test_*standing*` green.

- **V-tag — live untrusted write (Front-4 proof).** Point `fetch_page` at a
  **local fixture** page whose body contains a known injection payload; let it
  store to a scratch Grimoire.
  **PASS:** the stored row has `safety_class="untrusted_web"`, `trust_level <=
  0.3` even though the fixture URL maps to a Tier-1 domain, and
  `metadata["instruction_like"] == True`. Inspect the actual row
  (`grim.recall(...)` / SQLite read), not just the return value.

- **V-gate — dormant-at-boot proof (Front-5).** Start Shadow with default config;
  confirm via `get_schedule_info()` / logs that `standing_research` is NOT
  scheduled and the DORMANT log line printed. Then set the flag True in a scratch
  config, restart, confirm the job appears. **PASS:** absent-by-default,
  present-when-enabled — the gate demonstrably controls the autonomous write.

- **V-seam — read-side is honestly reported (red-team MED).** Run a `recall` of
  the V-tag row with default `min_trust`. **Observation to RECORD (not a
  pass/fail):** the returned dict does **not contain `safety_class` at all**
  (`grimoire.py:1142-1161`) — the marker is not merely unhonored, it is invisible
  on read. So a downstream consumer cannot see it even to act on it. This
  documents that Front-5 earned-by #1 is NOT met and requires the Grimoire mission
  to BOTH surface and demote on the marker. Do not phrase this as
  "retrievable-but-not-yet-acted-on" — it is not retrievable. Reaper's write-half
  is done; Grimoire's read-half is entirely pending (Abort A2). **Make it a
  test, not just prose (pass-2 LOW):**
  `tests/test_reaper_injection.py::test_recall_does_not_surface_safety_class` — a
  characterization test asserting `"safety_class" not in recall(...)[0]` today, so
  the invisibility is checked, and the test's later flip (to `in`) becomes the
  concrete signal that the Grimoire mission has landed earned-by #1.

- **V-reg — dispatch regression.** `python -m pytest tests/test_decision_loop.py
  tests/test_orchestrator.py -q` → no new failures (the scheduler + write paths
  sit on the dispatch/boot path).

---

## Gates & Autonomy Ledger (SUCCESS point 9)

| # | Move | Danger if ungated | Gate (WIRED how) | Earned-by |
|---|---|---|---|---|
| **G1** | M4.3/M4.3b flip `autonomous_research_enabled` → True | Reaper autonomously pulls the web (12h scheduler, manual `/schedule run`, AND orchestrator-chosen `web_fetch` full pages) and writes scraped, possibly-poisoned content into permanent memory with no human in the loop — the project's highest-severity risk | **Dormant-until-condition flag, default False; enforcement spans ALL SEVEN Reaper-content write sites via ONE shared fail-closed predicate `reaper_web_persist_allowed`: (a) `add_job` guard (dormant timer, pass-1); (b) `_run_standing_research` early-return (blocks `run_task`/`/schedule run`, pass-1 CRITICAL); (c) web_fetch persistence gate (pass-2 CRITICAL); (d) async-queue `_store_result_in_grimoire` gate + tag (pass-3 CRITICAL); (e) completeness meta-test so an 8th path fails a test not an attacker.** Tests: `…job_absent_when_flag_false` + `test_run_task_refuses_…` + `test_autonomous_web_fetch_does_not_persist…` + `test_async_queue_reaper_tool_not_persisted_when_gate_closed…` + `test_no_reaper_write_bypasses_tag_or_gate`. | (1) Grimoire read-side surfaces+demotes `safety_class`; (2) Sentinel injection suite green (does not exist yet → gate fail-closed); (3) Reaper source-tagging verified (V-tag) incl. the completeness meta-test green. Only #3 deliverable in this plan; #1 Grimoire-mission, #2 Sentinel-mission. |
| **G2** | M4.2 the on-demand `web_fetch` write | Even supervised, a fetched page can carry a payload into memory | **Untrusted-tagged at write (`safety_class` + trust cap + instruction flag), enforced by the `_untrusted_store` choke + `test_no_direct_remember_in_reaper` guard** — WIRED so no path can write untagged. | M4.2 landed; V1 + V-tag green |
| **G3** | M4.1 detector storing/acting on flagged content | A mis-built detector could silently pass payloads (false negative) or DoS via model calls (false positive storm) | **Deterministic layer always on; phi4 tiebreak bounded to a mid-band; fail-toward-flagging on model outage** — WIRED by the ambiguity-band call condition + the benign/security-article regression tests | M4.1 green incl. the security-article false-positive test |
| **G4** | Config writes (new flag in `reaper_settings.py` + `config.yaml`) | A wrong default (True) would ship the gate open | **Default False in BOTH the schema and `config.yaml`; Master reviews the diff** — WIRED by the schema default + PF-1 confirming `flag_exists False` pre-change and the gate tests post-change | Master has the diff; gate tests green |
| **G5** | CAPTCHA-solve service / residential proxies (restated) | Cost, signaling, edging toward solve-not-avoid / evasion | **Never default, never autonomous, Master per-use approval; not built here** | Separate Master decision (not earned in this plan) |
| **G6** | Existing high-trust scraped rows already in Grimoire (from today's open gate) | Old rows written at 0.7 before the cap remain over-trusted | **No autonomous deletion; Master-approved backfill/retag with backup first** (policy: never delete without backup) — WIRED as an explicit non-autonomous follow-up, not a silent migration | Master approves a backfill; backup verified first |

**Capability planned in full, gated:** the autonomous 12h research capability is
planned completely (the scheduler job, the topic rotation, the write) — it is not
amputated. It simply arrives **dormant behind a real, tested gate** with a
concrete three-part earned-by. Capability and gate both present.

---

## Red-team focus (for the attacker subagent)

Attack hardest at: **(1)** a hostile page scraped through `fetch_page` — trace
whether its content can reach Grimoire tagged as anything other than
`untrusted_web` (any write path bypassing the `untrusted_memory_kwargs` helper;
the scheduler write). **Redirect note (red-team LOW):** `evaluate_source` runs on
the ORIGINAL URL (`reaper.py:930`) BEFORE `allow_redirects` (`:935`), so a
redirect-to-Tier-1 does NOT re-earn 0.7 — the real (minor) case is content from a
redirected-TO page stored under the original URL's reputation; the M4.2 cap makes
both moot (all web = untrusted). Do not chase the "redirect re-earns 0.7"
mechanism — the code doesn't work that way.
**(2)** the gate: find any way `standing_research` still fires with the flag False
(a second scheduler, a direct `run_task("standing_research")` call, the job added
elsewhere). **(3)** the detector: craft a payload that reads benign to the
deterministic layer AND the phi4 tiebreak (obfuscation, encoding, split across
the char cap). **(4)** the read-side over-claim: any verification line that would
report the injection defense "complete" when only Reaper's write-half is done.

---

## Attack log (SUCCESS point 7 — filled after red-team)

Red-team pass 1 — `wargames/red-team/stealth-part2.md`. Write-half held; the gate
had a back door.

- **CRITICAL — attack that LANDED (the gate back door).** M4.3 gated only
  `add_job` (the 12h timer). `run_task("standing_research")`
  (`standing_tasks.py:110-124`) calls `_run_standing_research()` directly and is
  CLI-live at `main.py:577` (`/schedule run standing_research`) — so with the flag
  False, all plan tests went green and V-gate confirmed "dormant at boot," yet the
  autonomous scraped-content write still fired on demand. The plan listed this
  exact attack in its own red-team focus and never patched it — "looks governed
  but isn't," in the plan itself. Verified against code.
  **Patch:** the guard now wraps the FIRING (early-return inside
  `_run_standing_research` + a `run_task` refusal), closing every entry point, with
  a dedicated `test_run_task_refuses_standing_research_when_flag_false` (spy Reaper
  `execute` = 0, spy Grimoire `remember` = 0). G1 enforcement is now DOUBLE.
- **HIGH — LANDED (choke guard scoped to wrong file).** `_untrusted_store` and its
  AST guard lived in `reaper.py`, but the sixth write path is in
  `standing_tasks.py` (no Reaper instance) — the guard couldn't see it.
  **Patch:** tagging extracted to module-level `modules/reaper/tagging.py`
  (`untrusted_memory_kwargs`) imported by BOTH files; guard `test_no_untagged_
  reaper_remember` now spans both `reaper.py` and `standing_tasks.py`.
- **MED — LANDED (read side worse than stated).** `recall()` doesn't just ignore
  `safety_class` — it never returns it (`grimoire.py:1142-1161`); the marker is
  invisible on read. **Patch:** V-seam + earned-by #1 corrected to require the
  Grimoire mission to BOTH surface AND demote on the marker.
- **MED — LANDED (divergent detector).** An existing
  `PromptInjectionDetector.analyze()` at `injection_detector.py:28/94` was never
  grepped; the plan built a second detector. **Patch:** M4.1 now reuses/extends the
  shared Cerberus detector so Cerberus/Reaper/Sentinel key off one pattern set.
- **MED — LANDED (evasion boundary undefined).** Zero-width obfuscation and a
  payload split across the 8000-char truncation had no defined handling.
  **Patch:** normalize (strip zero-width/bidi, NFKC) before matching; inspect the
  FULL pre-truncation text; added `test_zero_width_obfuscation_stripped` +
  `test_split_payload_across_8000_boundary_flagged`.
- **LOW — LANDED (redirect mis-framed).** `evaluate_source` runs pre-redirect
  (`reaper.py:930` before `:935`), so "redirect re-earns 0.7" is not how the code
  works. **Patch:** red-team-focus note corrected; the cap makes it moot anyway.
- **LOW — LANDED (Sentinel suite absent).** Earned-by #2 pointed at a suite not in
  the tree. **Patch:** marked un-runnable-today / fail-closed; Master told only #3
  is deliverable in this plan.
- **HELD.** The attacker could not break the write-side trust cap (0.7 → ≤0.3) or
  the choke-helper convention on `reaper.py` — those are the moves it hit hardest
  and they held. The failure was the autonomy gate, now patched.

Red-team pass 2 — `wargames/red-team/stealth-part2-pass2.md`. Confirmed pass-1
fixes held; found the gate was anchored to the wrong write path.

- **CRITICAL (NEW) — LANDED.** The firing-guard fix genuinely killed the
  `run_task`/`/schedule run` door, but it anchored the whole Tier-2 gate to
  `_run_standing_research` (snippets @0.3) and left the **higher-severity
  `web_fetch` autonomous full-page write** (up to 0.7 pre-cap, dispatched ungated
  at `orchestrator.py:5254`) entirely outside Front 5. "Supervised on-demand" was
  asserted, never wired. Verified against code (`is_autonomous` at `:4982`).
  **Patch:** added **Move 4.3b** — orchestrator injects `_autonomous` into params
  (reusing `:4982`), adapter forces `store_in_grimoire=False` on an autonomous
  fetch while the gate is closed; four tests incl.
  `test_autonomous_web_fetch_does_not_persist_when_gate_closed`. G1 enforcement is
  now TRIPLE.
- **HIGH (NEW) — LANDED.** The shared `untrusted_memory_kwargs` helper's hardcoded
  signature dropped `confidence` (every Reaper write sets it) and didn't pin
  `check_duplicates` — a silent behavior regression. **Patch:** helper now
  preserves `confidence`/`check_duplicates`/passthrough, overriding only
  trust+safety_class+meta; `test_helper_preserves_confidence_and_dedup` added.
- **MED (NEW) — LANDED.** (a) The gate breaks three real `test_standing_tasks.py`
  tests (`:130,:187-205`) with no fork → added the fork to update them to the
  gated contract (grep-all, don't special-case). (b) The detector wrapper assumed
  `analyze()` returns a dict; it returns `InjectionResult(score,flags,action)` and
  needs a required `source` arg → M4.1 now adapts the shape and passes
  `source="reaper_scrape"` (verified `injection_detector.py:94-104`). (c)
  Normalization added to the Cerberus-shared detector → added
  `test_normalization_preserves_existing_verdicts` so the user-input path can't
  regress.
- **LOW (NEW) — LANDED.** Read-side invisibility was prose-only → added
  `test_recall_does_not_surface_safety_class` characterization test.
- **HELD (pass 2).** The write-side trust cap and the (now double-guarded)
  scheduler firing path held under the second, harder attack.

Red-team pass 3 — `wargames/red-team/stealth-part2-pass3.md`. Verdict: HOLE FOUND
(CRITICAL) — a FOURTH autonomous write path, same class one layer out.

- **CRITICAL (NEW) — LANDED (the async task queue).**
  `AsyncTaskQueue._store_result_in_grimoire` (`async_tasks.py:355`) persists EVERY
  backgrounded task result at **trust 0.8**, `source_module="shadow"`, untagged,
  ungated, outside the choke helper. `web_search`/`youtube_transcribe` route async
  by default (`_LONG_RUNNING_TOOLS`, `orchestrator.py:848`) and fire from
  autonomous sources (Proactive Engine; deferred graph `source="autonomous"`).
  Compounded: `submit_task` strips underscore params (`orchestrator.py:5232`) so
  the pass-2 `_autonomous` flag never survives (fail-OPEN), and `source_module=
  "shadow"` hides it from the reaper-scoped guard. Verified against code.
- **This recurring pattern IS the finding.** Three passes, three different write
  paths one layer further out — path-by-path gating was the wrong architecture.
  **Patch (redesign):** M4.3b now (a) enumerates ALL SEVEN Reaper-content write
  sites across three files; (b) funnels them through ONE shared tag+gate; (c) adds
  a `reaper_web_persist_allowed(source, tool_name, gate_open)` predicate that is
  **fail-CLOSED** (unknown source for a Reaper web tool → not persisted); (d)
  threads real `source` into `submit_task` (which hardcoded "user"); (e) routes
  the async-queue Reaper-tool write through `untrusted_memory_kwargs` (≤0.3 +
  `safety_class`), not 0.8; (f) adds a **completeness meta-test**
  `test_no_reaper_write_bypasses_tag_or_gate` so a pass-4 eighth path fails a test
  rather than an attacker. The two-file guard is now three-file.
- **Pass-2 fixes CONFIRMED held** by pass 3: helper-preserves-confidence, detector
  adapts `InjectionResult` (`reaper_scrape` already in the detector's
  `UNTRUSTED_SOURCES`), the 3 standing-tasks test fork, and the scheduler
  double-guard all check out.
- **Honest status:** because the gate took a CRITICAL on all three passes, this
  plan is **PATCHED, converging — NOT DONE.** The redesign closes the class by
  construction (enumerate-all + fail-closed + completeness meta-test). See pass 4.

Red-team pass 4 — `wargames/red-team/stealth-part2-pass4.md`. **Verdict: GATE
CLASS CLOSED on the write-path axis (no 8th path) — but the path-7 FIX had broken
plumbing.**

- **The recurring "one more door" is OVER.** The attacker ran the full
  `grep -rn "\.remember(" modules/` enumeration (41 sites) and traced every one:
  the seven the plan names are the COMPLETE set of Reaper-scraped-content writes;
  all other sites carry telemetry/teaching/code-analysis/static-KB/benchmark/
  user-correction content (the Cerberus `source="research"@0.7` writes come from a
  hardcoded `_CONCEPTS` dict, not the web; the Proactive Engine writes only to
  SQLite, never Grimoire). The enumerate-all redesign achieved its goal.
- **HIGH (B-1) — LANDED (my fix crashed the gate).** Threading `source` into
  `create_task` raises `ValueError` on autonomous sources (`TaskSource` is a
  4-value enum; `create_task` coerces at `task_queue.py:406`), swallowed by the
  async-submit fallback → silent SYNC dispatch where the gate never runs.
  **Patch:** carry `origin_autonomous` in the task PAYLOAD (default True =
  fail-closed), NOT the enum; graph branch is definitionally autonomous.
- **MED (B-2/B-3) — LANDED.** The production worker re-plans through the graph and
  stores `tool_name="graph"`, so a submitted-tool predicate misses it; the plan's
  test was green only on the dead no-orchestrator branch. **Patch:** the graph
  branch inspects `state["tool_results"]` for `.module=="reaper"`
  (`_result_from_graph_state` has it); tests now drive the production graph branch;
  the meta-test asserts the dual-purpose `355` write is inside the gated branch.
- **Pass-1/2/3 CRITICALs confirmed structurally covered** (scheduler double-guard,
  web_fetch sync gate, async-queue enumerated).
