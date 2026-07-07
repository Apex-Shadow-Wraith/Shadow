# RED-TEAM — Reaper Part 1 (Stealth + Professional Gathering, Fronts 1–3)

**Attacker:** fresh isolated instance ("stealth" red-team). Did not write the plan.
**Target:** `wargames/plans/stealth-part1-gathering.md`.
**Method:** followed the plan BLIND as the executor would, spot-verified every
`file:line` against the real code, and attacked the stealth-vs-access-control
line, the V3 "green test guards a dead path" seam, and the Gates ledger.
**Rules honored:** read-only. No mutation, no test runs, no network, no
`remember()`. I attacked; the author patches.

---

## Findings table

| # | Plan-line quote | How it fails | Severity |
|---|---|---|---|
| F1 | M2.1: *"confirm `search()` is called via `await module.execute` → executor thread (it is; adapter is `async` but calls sync `self._reaper.search` — check `reaper_module.py:99`). If sync-in-thread, `time.sleep` is acceptable"* | **False as fact.** `ReaperModule.execute` is `async def` (`reaper_module.py:82`) and calls sync `self._reaper.search(...)` INLINE (`:99`) — there is no executor. The orchestrator dispatches with a bare `await module.execute(...)` (`orchestrator.py:5254`), the async-queue worker does the same (`async_tasks.py:252`), and the scheduler marshals the coro back onto the SAME main loop via `asyncio.run_coroutine_threadsafe(coro, self._loop)` (`standing_tasks.py:160`). Every path runs sync `search()`/`fetch_page()` ON the event loop. A `time.sleep()` backoff **blocks the whole event loop** — the exact "most likely failure" the move raises, then waves away with a wrong justification. The test the plan writes asserts backoff-sleep COUNT, not that the loop wasn't blocked, so it passes green while the defect ships. | **CRITICAL** |
| F2 | M1.2 fork: *"in `fetch_page`, **if** `requests.get` raises or returns `status_code in {403, 429, 503}` … → route B"* | Unreachable trigger. `fetch_page` calls `response.raise_for_status()` immediately (`reaper.py:939`); a 403/429/503 becomes an `HTTPError` caught at `:946-948` which returns `None`. There is no code path where `fetch_page` "returns `status_code in {403,429,503}`" — the status is consumed and discarded before the fork can read it. The executor wiring the fork as written finds no `status_code` to branch on; the "not a judgment call" trigger is a dead branch. | **HIGH** |
| F3 | M1.2 "most likely failure": *"Playwright sync API raises `Error: … Sync API inside asyncio loop` … Reaper is called from the orchestrator's event loop … **Counter:** run in a worker thread … **if** the call site is `async def` (adapter `execute`) → use `async_api`; **if** sync (scheduler/tests) → `sync_api`"* | The trigger's premise is wrong: the scheduler call site is ALSO async-on-the-main-loop (F1), so "sync (scheduler)" is a case that does not exist — the scheduler's `reaper.execute` runs on `self._loop` via `run_coroutine_threadsafe`. An executor picking `sync_api` "because it's the scheduler" plants the very `Sync API inside asyncio loop` crash into the autonomous 12h path. The branch decides on a false dichotomy. | **HIGH** |
| F4 | M1.2 expected obs: *"`test_browser_fetch_from_async_context` asserting no 'Sync API inside asyncio' error when driven from an `async` caller."* + M1.3 V3 *"a live check (verification V3) shows a non-`requests`/urllib3 JA3 at a JA3 reflector"* | **Green test guards a dead network path (SUCCESS 6).** Both browser and TLS tests run against `127.0.0.1` fixtures / mocked responses. A local `http.server` fixture never exercises a real TLS handshake, so `test_tls_impersonation_selected` (asserts the MAPPING) and the browser test can be fully green while `curl_cffi` is never actually on the wire and the browser never faces a real anti-bot. V3 is the only thing that would catch it — and V3 depends on an UNNAMED reflector (F7), so in practice the suite reports PASS on stealth layers proven by nothing. | **HIGH** |
| F5 | M3.2 expected obs: *"`evaluate_source("https://user.github.io/x")` and a gist URL return a ranking tier ≥ 3 (not 1)"* | Hidden shared-surface coupling, unflagged. `evaluate_source` returns `{domain, tier, trust_score, source_type}` — there is no ranking-tier field (`reaper.py:120-152`). To make the test pass the executor must either (a) add a new key, or (b) change the returned `tier` — and `tier` is load-bearing elsewhere: `check_download_safety` gates Tier-1 auto-allow on `source_eval["tier"] == 1` (`reaper.py:875`) and the Grimoire write stamps `"Tier {source_eval['tier']}"` into stored content (`reaper.py:981`). Demoting `tier` silently changes the download-safety gate and the stored provenance label — a cross-cutting change the plan calls "ranking only." | **MED** |
| F6 | G1 earned-by: *"Master reviews the diff before commit; commit-not-push … WIRED by … the Git-workflow rule (targeted tests green → `git add <files>` → `git commit`, never push)."* | Ledger names a gate the environment does not enforce — the "looks governed but isn't" failure. `CLAUDE.md` Permissions: **"Automatically commit changes without asking … Do not ask for approval before editing files."** The executor auto-commits; "Master reviews the diff before commit" is not wired, it's aspirational. The only real enforcement here is the push deny-list (harness-level), which G1 doesn't cite. G1's stated earned-by ("Master has the diff") is never a precondition to any commit the executor makes. | **MED** |
| F7 | G2 / M1.6 / V3: *"WIRED by the RECON NEEDED in M1.6 blocking V3 until the endpoint is named."* + V3 PASS bar *"JA3 is browser-like … webdriver false … inter-request timing varies"* | The G2 network-touch gate is "wired" only by a RECON-NEEDED note asking Master to name a reflector — a question, not a mechanism. Nothing in code or the runbook prevents the executor from `python scripts/reaper_fingerprint_check.py` against a public reflector before Master answers; the "gate" is a comment. And V3's PASS is unfalsifiable blind: "browser-like JA3," "non-headless," "timing varies" have no threshold, no reference JA3 string, no reflector — an executor cannot mechanically decide PASS/FAIL. It is the vague-observation failure sitting on top of the network gate. | **MED** |
| F8 | PF-1 expected obs: *"`searxng_enabled True backend ddg brave False`; `ls` lists `chromium-1208` …; docker line reads `shadow-searxng Up … (healthy)`."* | Recon fact drift. Recon §10 calls `searxng_enabled=True` a "live override; NOT the schema default False." It is set to `true` in the CHECKED-IN `config/config.yaml:98`, not a local override — the schema default (`reaper_settings.py:23`) is False, but the committed config already flips it. The PF-1 fork ("if `searxng_enabled` reads `False` → re-read `config.local.yaml`") points the executor at the wrong file; the real source of the True is `config.yaml`. Minor, but a wrong file:cause in a fork. | **LOW** |
| F9 | M2.2: *"NEVER call a solving service here (that is Part 2's gated last-resort …)"* + Abort A1 | Not a break — this one HELD. The avoid-never-solve line is explicit, gated (G6 marked EXPLICIT NON-BUILD), and A1 is unambiguous. M2.2's only weakness is the false-positive substring risk, which the move itself counters with a negative test. No stealth→access-control crossing found in M1.2/M1.3/M2.2. Recorded as the move I attacked hardest that survived. | — (held) |

---

## Single worst break — F1 (the event-loop-blocking backoff shipped green)

**The concrete blind run-through.** An executor runs the plan in order.

1. **PF-2** passes: `107 passed`. Baseline green, build authorized.
2. **M2.1** ("General rate-limit backoff + rung-switch"). The executor reads the
   move's own "most likely failure": *"the backoff blocks the event loop (sync
   `time.sleep` in an async path)."* Good — the plan raised the real risk. It
   then reads the **counter**, which tells it, as settled fact, to *"confirm
   `search()` is called via `await module.execute` → executor thread (it is …).
   If sync-in-thread, `time.sleep` is acceptable."* The plan asserts the safe
   world exists. The executor, following blind, trusts it and writes
   `_http_get_resilient()` with a plain `time.sleep()` on `429`/`503`.
3. The reality the executor did not independently check: `ReaperModule.execute`
   is `async def` (`reaper_module.py:82`) but calls sync `self._reaper.search`
   INLINE at `:99` — **no `to_thread`, no executor**. Dispatch is a bare `await
   module.execute(...)` at `orchestrator.py:5254`. So `search()` — now containing
   a blocking `time.sleep(4)` retry ladder — runs directly on the main asyncio
   loop.
4. **The test the plan specifies** (`test_429_triggers_backoff_then_rung_switch`)
   monkeypatches `time.sleep` and asserts it was **called twice**. That assertion
   is satisfied by the broken code — the sleeps happen; the test is green. Nothing
   in the test asserts the event loop stayed responsive. **V1 reports PASS.**
5. **V4** ("threat-response live-ish") points `fetch_page` at a local fixture
   returning 429. It observes "429 → backoff+rung-switch logged." Also PASS —
   a single sequential fixture fetch never reveals loop starvation, because
   nothing else is contending for the loop during the test.
6. **Ships.** In production, the first rate-limited SearXNG/Bing rung makes
   Reaper's backoff `time.sleep` freeze the orchestrator's entire event loop for
   up to 1+2+4s per fetch — every concurrent request, every Langfuse span flush,
   every other module `await` stalls behind Reaper's nap. Worse, the same
   `time.sleep` sits on the **autonomous 12h scheduler path** (`standing_tasks.py`
   marshals `reaper.execute` onto `self._loop` at `:160`), so an unattended
   standing-research run against a throttling host silently hangs the loop with
   no human watching. The plan certified a green suite over a defect it named and
   then mis-cleared with a wrong architectural claim.

**Why it's the worst:** it is simultaneously (a) an assumption stated as fact
that the code contradicts, (b) a verification that PASSes on a broken result,
and (c) a latent hang on the autonomous path — three of the nine SUCCESS
failures in one move. F2 and F3 compound it: F3 puts the *same* class of
sync-in-asyncio crash into the Playwright path via an equally false "the
scheduler is sync" premise, and F2's dead `status_code` fork means the browser
fallback the plan leans on may never even trigger.

---

## Verdict

The plan is strong on the mission line I was told to attack hardest — the
stealth-vs-access-control boundary holds (F9): M2.2 disengages and never solves,
A1 is explicit, G6 is a clean non-build, and no move smuggles authentication or
access-control evasion in under "stealth." But the plan is built on a **single
false architectural fact — that Reaper's sync work runs in an executor thread —
and that error is load-bearing for three moves** (M2.1 backoff, M1.2 browser,
M1.3's async/sync fork), because every real dispatch path (`orchestrator.py:5254`,
`async_tasks.py:252`, `standing_tasks.py:160`) runs the sync engine on the main
event loop. The verifications don't catch it: the backoff test asserts sleep
count, not loop liveness, and the stealth tests (F4) prove their layers against
`127.0.0.1` fixtures while V3's live check hangs on an unnamed reflector (F7) —
so the whole Front-1 stealth stack can go green without a single real TLS or
anti-bot exchange. Add F6 (a governance gate the auto-commit environment never
enforces) and F5 (a "ranking only" change that silently mutates the
download-safety gate and stored provenance), and the plan **fails SUCCESS points
1, 2, 6, and 9** as written. It is not far from passable: fix the threading fact
(wrap the sync engine in `asyncio.to_thread` or make the backoff loop-aware, and
assert loop-liveness in the test), make F2's fork read a status the code actually
exposes, name the V3 reflector so the network gate is a mechanism not a comment,
and re-scope M3.2 off the shared `tier` field.
