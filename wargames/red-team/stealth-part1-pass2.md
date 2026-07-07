# RED-TEAM PASS 2 — Reaper Part 1 (Stealth + Professional Gathering, Fronts 1–3)

**Attacker:** fresh isolated instance, pass 2. Did NOT write the plan or the
patches. **Target:** the PATCHED `wargames/plans/stealth-part1-gathering.md`
(post pass-1). **Special suspicion:** the patches themselves — big patches
(Move 0, the M1.2 status refactor, the V3 falsifiable bar) introduce new seams.
**Method:** followed the patched plan BLIND as the executor would, verified every
`file:line` against real code, ran read-only checks (`pytest --collect-only`,
`python -c`, grep), and hunted for (a) pass-1 fixes that only closed in prose,
(b) NEW breaks the fixes opened.
**Rules honored:** read-only. No mutation, no test runs beyond `--collect-only`,
no network, no `remember()`. I attacked; I did not fix.

**What I verified green (patches that genuinely hold):** Move 0's core
architectural claim — every dispatch path (`orchestrator.py:5254`,
`async_tasks.py:252`, the deferred-graph leg `orchestrator.py:1062` via
`run_deferred_through_graph`, and the scheduler `standing_tasks.py:160`) funnels
through `await module.execute(...)`, so wrapping the engine in `to_thread` INSIDE
`execute` covers all of them (F1 genuinely fixed). No default-executor override
exists anywhere (`grep` clean), so `to_thread` uses the full ~20-worker default
pool — **no hard deadlock**. Grimoire's `remember()` holds an `RLock`
(`grimoire.py:740`) around the entire write incl. the ChromaDB `collection.query`
(`:779-783`), with `check_same_thread=False` (`:214`) — so concurrent
worker-thread + APScheduler-thread writes serialize correctly (F1's thread-safety
counter holds). `raise_for_status()` raises `HTTPError(..., response=self)` (verified
from the installed `requests` source) so `e.response` IS guaranteed non-None for
that call site (M1.2's defensive None-branch is dead but harmless). Baseline is
`107 tests collected` (PF-2 correct). F9's stealth-vs-access-control line still
holds — no move crosses into auth/access-control evasion.

---

## Findings table

| # | Plan-line quote (exact) | How it fails | Severity |
|---|---|---|---|
| **P1** | M1.2, line 158–162: *"in the `except requests.HTTPError as e` block (`reaper.py:946-948`), read `status = e.response.status_code …`. THEN the fork is real: **if** that captured `status in {403, 429, 503}` OR `fetch_page` returned non-None text < 200 chars → **route B:** retry via `fetch_page_browser`."* | **The browser fallback has a hole exactly where anti-bots live.** The refactor only touches the `HTTPError` block. But `fetch_page` catches `requests.ConnectionError` (`:940`) and `requests.Timeout` (`:943`) SEPARATELY, each returning `None` with **no status and no browser fork**. TLS-reset / connection-reset / tarpit are the *most common* anti-bot soft-block signatures — a hostile edge (Cloudflare, Akamai) frequently RSTs or tarpits a bot's `requests`/urllib3 handshake rather than returning a clean 403. So the exact class the browser path exists to defeat (JS/anti-bot pages) bypasses the fork: `ConnectionError`/`Timeout` → `None` → no route B → the page is silently lost, and the plan's own "returned non-None text < 200 chars" trigger never fires because the return is `None`, not a short string. The patch closed the *status-code* half of F2 and left the *connection-error* half open. | **HIGH** |
| **P2** | M1.6 / V3 check 3, line 269–271 + 505–506: *"on the `curl_cffi` path, `JA3_OBSERVED != JA3_BASELINE` AND `JA3_OBSERVED` equals the JA3 the impersonation target is documented to emit"*; reflector spec line 257–260: *"a tiny Flask app on `127.0.0.1:8109` that echoes request headers, and (for JA3) sits behind a local mitmproxy/ja3 capture OR uses `curl_cffi`'s own JA3 self-report."* | **V3 check 3 is unfalsifiable-in-practice — the patch re-opened F7 in a new shape.** A Flask app serving plain HTTP on `127.0.0.1:8109` **never sees a TLS ClientHello**, so it cannot compute *any* JA3 — `JA3_OBSERVED` is undefined from an HTTP reflector. The plan offers three JA3 sources as an OR with **no trigger** (violates SUCCESS 3): (a) `mitmproxy` — **not installed** (verified: `import mitmproxy` fails) so it's an unlisted Gate-G3 install, AND mitmproxy terminates TLS itself, so the JA3 it captures is mitmproxy's re-negotiated upstream handshake unless it's specifically run as a transparent JA3 sniffer — non-trivial, unspecified; (b) `curl_cffi`'s "own JA3 self-report" — **`curl_cffi` exposes no such API**: it *sets* the TLS fingerprint via `impersonate=` but does not compute or return the JA3 string of the handshake it emitted. So there is no named, buildable-blind mechanism that yields a real `JA3_OBSERVED` string on `127.0.0.1`. An executor following blind cannot mechanically decide check 3 → PASS/FAIL is a judgment call → the "five falsifiable checks" collapse to four. The patch named the reflector and added thresholds, but the load-bearing TLS threshold rests on an observer the plan can't build. | **HIGH** |
| **P3** | Move 0 expected obs, line 96–100: *"`test_execute_does_not_block_event_loop` … `self._reaper.search` monkeypatched to `time.sleep(0.5)` then return results, WHILE a concurrent `asyncio` heartbeat task increments a counter every 10ms; assert the heartbeat advanced by ≥30 ticks during the call."* | **The liveness test can pass spuriously if the executor monkeypatches at the wrong layer.** The test's power depends on the patched `time.sleep(0.5)` running INSIDE the `to_thread` worker. But the spec says patch `self._reaper.search` "to `time.sleep(0.5)` then return results" — if the executor instead patches `execute` itself, or patches `to_thread` to run inline (a common test convenience so results are deterministic), the sleep runs on the loop and the test would FAIL loudly (good) — OR, the inverse: if the heartbeat coroutine is created but the test `await`s `execute(...)` *before* yielding control to let the heartbeat task start (no `await asyncio.sleep(0)` to schedule it), the heartbeat may not be running yet, and a `to_thread` that returns fast (0.5s) could still show ≥30 ticks *only because the loop was free* — proving liveness — OR show <30 if the harness's event loop granularity differs. The threshold "≥30 ticks in 0.5s at 10ms" assumes perfect 10ms scheduling with zero jitter; under pytest-asyncio's loop with GC pauses or a slow CI, 0.5s/10ms=50 ideal ticks can dip below 30 from scheduling jitter alone, making the test **flaky-fail** (masking real breaks with noise) OR the executor loosens the threshold to fix flakiness and re-opens the F1 gap. The test is better than pass-1's sleep-count, but its numeric bar (≥30/50) is not robustly specified against loop jitter. | **MED** |
| **P4** | Move 0 counter, line 101–106: *"if `self._reaper` touches non-thread-safe state (the Brave usage-file writer `reaper.py:798-815`) … guard the Brave usage read-modify-write with a `threading.Lock` … Add `test_brave_usage_threadsafe` if M1.3/M2.1 exercise Brave."* | **Conditional guard on a race the patch acknowledges but leaves unbuilt-by-default.** `_brave_increment_usage` (`:798-815`) is an unlocked read-modify-write of a JSON file; `_brave_get_usage` (`:784`) reads it in the cascade availability predicate (`:526`). Under Move 0 two concurrent Reaper calls (on-demand `web_fetch` + the 12h scheduler) run on *different* `to_thread` workers and can interleave the RMW → lost quota increments / corrupted `count`. The plan gates the fix behind *"if M1.3/M2.1 exercise Brave"* — but M2.1's `_http_get_resilient()` is *"used by SearXNG/Bing/`fetch_page`"* (line 284), and Brave already has its own 429 path, so an executor reads "M2.1 doesn't touch Brave" and **skips the lock**. The race then ships latent. It is only *latent* (not live) because `brave_available=False` on Citadel (no API key, recon §10) — but the plan's own PF-1 fork contemplates the config changing, and the moment a Brave key lands the corruption is live with no guard. A conditional gate whose condition an executor can read as "not met" is a half-fix. | **MED** |
| **P5** | Move 0, line 83–91: *"wrap the sync engine calls … in `await asyncio.to_thread(...)` … the single dispatch choke point every path (orchestrator, async-queue, marshaled scheduler) funnels through."* + `main.py:686` | **New interaction the patch didn't trace: the CLI's blocking `input()` permanently parks one default-pool worker, and `to_thread` shares that pool.** `main.py:686` runs `await loop.run_in_executor(None, input, "You > ")` — a blocking `input()` on the DEFAULT executor (`None`), held for the entire time the user sits at the prompt (i.e. ~always, interactively). Move 0's `to_thread` also uses the default pool. On Citadel's 16-core box the default pool is ~20 workers so one parked `input()` doesn't starve `to_thread` — **no deadlock today** — but the plan claims Move 0 is "the single choke point every path funnels through" without noting that the pool is *shared* with the CLI input primitive and with any other `run_in_executor(None, …)`. If a future change (bounded custom executor, or many concurrent scheduled + async-queue + on-demand fetches each 1–3s under `_stealth_delay`) approaches the pool ceiling, the parked `input()` is one permanent slot down. The patch is correct for today's pool size but the plan never states the pool-sharing assumption it now depends on — an unstated invariant is a latent seam (SUCCESS 8: not fully executable-blind because the safety rests on an unnamed pool-size fact). | **LOW** |
| **P6** | PF-1 fork, line 40–45 (F8 patch): *"if `searxng_enabled` reads `False` here … re-read the source of the `True`, which is the CHECKED-IN `config/config.yaml:98` … the schema default in `reaper_settings.py:23` is `False`, but `config.yaml` flips it. Also check `config/config.local.yaml` for a machine override."* | **Pass-1 F8 fixed correctly** — the fork now names `config.yaml:98` as the source of the `True` and treats `config.local.yaml` as a secondary override check, not the primary source. Verified against recon §10 (checked-in override, not local). No break. Recorded as a pass-1 finding **confirmed genuinely closed** (not prose-only). | — (held) |

---

## Single worst break — P2 (V3 check 3 is unfalsifiable; the ONLY certification of Front 1 rests on a JA3 observer the plan can't build blind)

**Why this one and not P1.** P1 (the ConnectionError/Timeout browser-fork hole)
is a real capability gap, but it degrades gracefully — a lost page, not a lie.
P2 is worse because it strikes the plan's own SUCCESS-6 spine: the patched plan
*repeatedly and emphatically* states that **only V3 certifies Front 1** ("A
stealth layer whose only evidence is a local-fixture unit test is NOT done (A3)",
line 256; "V3 — the ONLY certification of Front 1", line 502). The whole
stealth-stack's honesty gate is V3's five falsifiable checks. If check 3 — the
TLS/JA3 check, the entire *point* of Move 1.3 — cannot be mechanically decided,
then the plan's central anti-self-deception mechanism has a hole precisely where
the highest-value, hardest-to-verify layer (TLS fingerprinting) lives.

**The concrete blind run-through.**

1. Executor completes M1.3: installs `curl_cffi` (Gate G3), adds `UA_TO_IMPERSONATE`,
   routes the light path through `curl_cffi.requests(impersonate=...)`. Unit test
   `test_tls_impersonation_selected` goes green — it asserts the UA→target MAPPING
   against `curl_cffi`'s enum. Real, but it proves nothing is on the wire (the plan
   admits this, F4).
2. Executor builds `scripts/fingerprint_reflector.py` per line 258: "a tiny Flask
   app on `127.0.0.1:8109` that echoes request headers." It serves plain HTTP —
   `flask` was not installed, so this is itself an unlisted install. The reflector
   dutifully echoes UA, headers, and can report `navigator.webdriver` (browser
   path) and timing. Checks 2, 4, 5 are decidable.
3. Executor reaches check 3: `JA3_OBSERVED != JA3_BASELINE` AND `JA3_OBSERVED ==
   the impersonation target's documented JA3`. It asks: *what produces
   `JA3_OBSERVED`?* The Flask HTTP reflector saw no TLS handshake — there is no
   ClientHello to hash. It reads the plan's OR: (a) mitmproxy — not installed,
   and even installed it would need transparent-TLS-sniff config the plan doesn't
   give; (b) "`curl_cffi`'s own JA3 self-report" — the executor greps `curl_cffi`
   and finds **no self-report API** (curl_cffi sets the fingerprint; it does not
   emit the JA3 it produced).
4. The executor now faces a judgment call the plan swore it eliminated (SUCCESS 3,
   8): either (i) skip check 3 and declare V3 PASS on 4/5 — **silently dropping the
   one check that proves TLS randomization actually happened**, exactly the F4/F7
   "green over a dead path" failure the patch claimed to close; or (ii) invent a
   JA3 capture mechanism blind (stand up mitmproxy as a transparent proxy, or
   point at an external JA3 reflector like `tls.browserleaks.com` — which trips
   Gate G2's allowlist AND the A1/A3 supervised-network line); or (iii) stop and
   flag (correct, but the plan gave it no trigger to know it must).
5. Whichever branch: the plan certified that V3 is falsifiable and mechanical, and
   it is not. The most likely real-world outcome is (i) — an executor under
   "make V3 green" pressure drops the un-runnable check and reports **Front 1 TLS
   layer certified** on a reflector that never observed a single JA3. That is the
   precise self-deception the entire V3/A3 apparatus exists to prevent, re-entered
   through the patch that was supposed to close it.

**The one-line fix (not my job, but to show it's real):** the plan must name a
concrete JA3-observing mechanism that runs on `127.0.0.1` and is buildable blind —
e.g. a small TLS-terminating socket server that captures the ClientHello bytes and
computes the JA3 itself (a ~40-line `ssl`/raw-socket capture), with the reference
JA3 pinned as a literal from `curl_cffi`'s documented target — OR downgrade check 3
to "the light path imports and dispatches through `curl_cffi` (asserted by a
`sys.modules` / call-spy), TLS-fingerprint claimed DORMANT-until-external-reflector"
and stop pretending the local reflector certifies JA3. Either makes check 3
mechanical; as written it is a judgment call wearing a threshold's clothes.

---

## Pass-1 findings re-checked (did the fix hold, or move the break?)

- **F1 (was CRITICAL) — fix HOLDS in architecture, new seams P3/P4/P5.** Move 0's
  `to_thread` correctly covers all four dispatch paths; the RLock serializes
  Grimoire writes. But the *test* (P3) has a jitter-fragile numeric bar, the Brave
  race guard (P4) is conditional on a condition an executor can read as unmet, and
  the shared default-pool assumption (P5) is unstated. The core fix is sound; the
  patch spawned three lower-severity seams.
- **F2 (was HIGH) — fix PARTIAL (P1).** Status capture from `HTTPError` works and
  `e.response` is provably non-None. But the refactor left `ConnectionError`/`Timeout`
  (the connection-reset anti-bot class) with no status and no browser fork — the
  half of the fetch-failure space where anti-bots most often live.
- **F3 (was HIGH) — fix HOLDS.** Move 0's worker thread has no running loop, so
  `playwright.sync_api` is uniformly safe; the caller-type branch is gone. Verified
  all paths reach the `to_thread` worker. Clean.
- **F4 (was HIGH) — fix PROSE-ONLY where it matters most (folds into P2).** The
  plan now *says* unit tests don't certify Front 1 and only V3 does — correct
  prose — but the V3 mechanism it points to (P2) can't decide its central check,
  so "only V3 certifies" plus "V3 check 3 is undecidable" = TLS layer certified by
  nothing, the exact F4 failure with an extra layer of indirection.
- **F5 (was MED) — fix HOLDS.** `ranking_tier` is a NEW field; `tier`/`trust_score`
  untouched; `test_download_safety_gate_unaffected` guards the gate at
  `reaper.py:875` and the provenance stamp at `:981`. Verified the gate reads
  `source_eval["tier"]` and the write stamps `Tier {source_eval['tier']}` — both
  left alone by a `ranking_tier` addition. Clean.
- **F6 (was MED) — fix HOLDS.** G1 reframed around the real controls (push
  deny-list, PF-3 rollback, tests-green). Matches CLAUDE.md auto-commit reality.
- **F7 (was MED) — fix PARTIAL (folds into P2).** The G2 allowlist mechanism
  (`sys.exit` off-list) genuinely closes the "network gate is a comment" half. But
  the "V3 PASS is falsifiable" half re-opens: check 3's threshold is unbuildable
  blind (P2). Half the F7 patch holds; half moved the break.
- **F8 (was LOW) — fix HOLDS (P6).** Correct file:cause now.
- **F9 (held) — still holds.** No stealth→access-control crossing in any move,
  including the new Move 0 and the M1.2 browser path. Attacked hardest again
  (below); survived again.

---

## What I attacked hardest and could NOT break

**The stealth-vs-access-control line (F9), re-attacked through the NEW surfaces.**
I specifically probed whether Move 0's `to_thread` off-loading, the M1.2 browser
path (`fetch_page_browser` with `navigator.webdriver=undefined`, Canvas/WebGL
noise), or the M1.5 proxy plumbing could be the seam where "stealth" becomes
"evasion of an access control." They cannot: the browser stealth patches defeat
*fingerprinting*, not *authentication*; M1.5 proxy stays `proxy_url=None` dormant
behind Gate G5 with A1 re-affirmed; M2.2 disengages-never-solves with G6 as an
explicit NON-BUILD; and the download-safety gate (`reaper.py:843-908`) and A1 line
are untouched. No move reads non-public content, authenticates as Master, or
defeats an access control. The permanent line holds under pass 2 exactly as it
held under pass 1.

---

## Verdict

The patches did their core job: **F1's load-bearing architectural error is
genuinely fixed** — Move 0's `to_thread` wrap sits at the one choke point all four
dispatch paths funnel through, Grimoire's RLock makes concurrent worker+scheduler
writes safe, and F3/F5/F6/F8 are cleanly closed with the tests to prove F5. The
stealth-vs-access-control line (F9) survived a second, harder attack. This is a
markedly stronger plan than pass-1's target.

**But two big patches introduced or left two HIGH seams, and both sit on Front 1's
honesty spine.** P2 (worst): the V3 "falsifiable bar" — the patch's headline fix
for F7 — cannot mechanically decide its central TLS/JA3 check, because a local
HTTP Flask reflector observes no TLS handshake and neither of the plan's named
JA3 sources (uninstalled mitmproxy; a `curl_cffi` self-report API that doesn't
exist) yields a `JA3_OBSERVED` string blind. So "only V3 certifies Front 1" +
"V3's TLS check is undecidable" reproduces the exact F4/F7 "green over a dead path"
failure the patch was written to kill. P1: the M1.2 status refactor closed the
HTTP-status half of the browser fork but left `ConnectionError`/`Timeout` — the
connection-reset/tarpit anti-bot class — with no status and no browser fallback,
so the browser path has a hole precisely where anti-bots live. P3/P4/P5 are the
lower-severity new seams Move 0 spawned (jitter-fragile liveness threshold,
conditional Brave-race guard an executor can skip, unstated shared-default-pool
assumption).

**Fails SUCCESS points 3, 6, and 8 as written** (an undecidable "falsifiable"
check = a judgment call the trigger was supposed to remove; a certification that
can report PASS on an unexercised TLS layer; a plan not fully executable-blind at
check 3 and at the Brave-guard condition). Not far from passable: name a
buildable-blind local JA3 observer (or downgrade check 3 to a dispatch-spy +
mark TLS dormant-until-external-reflector), extend the M1.2 fork to route
`ConnectionError`/`Timeout` to the browser path, make the Brave lock
unconditional (it's cheap and the config can change), and specify the liveness
threshold against loop jitter.
