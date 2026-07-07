# RED-TEAM PASS 3 — Reaper Part 1 (Stealth + Professional Gathering, Fronts 1–3)

**Attacker:** fresh isolated instance, pass 3 (the confirming attack). Did NOT
write the plan or any patch. **Target:** the TWICE-patched
`wargames/plans/stealth-part1-gathering.md`. **Charter:** confirm the pass-1
CRITICAL (event-loop-blocking backoff) and the two pass-2 HIGHs (undecidable
JA3 check; missing ConnectionError/Timeout browser fork) are truly closed, and
that the fixes did not open new seams. Attack hardest at whether the JA3
verification is now decidable BLIND, whether the ConnectionError→browser fork
actually helps, and whether Move 0's double-hop is deadlock-free.
**Method:** followed the patched plan blind, verified every `file:line` against
real code, and — where the prior passes could only reason — ran LIVE read-only
probes (raw-socket capability, userland ClientHello capture, JA3-field
destination-independence, `to_thread` loop-visibility, package presence).
**Rules honored:** read-only. No mutation, no network, no installs, no
`remember()`. I attacked; I did not fix.

---

## What I verified GREEN with live probes (the load-bearing patches hold)

- **Move 0 double-hop is deadlock-free (priority 3).** The scheduler marshals via
  `asyncio.run_coroutine_threadsafe(coro, self._loop)` from an APScheduler thread
  (`standing_tasks.py:160`), blocking on `future.result(timeout=300)`. That thread
  belongs to `BackgroundScheduler(daemon=True)` (`standing_tasks.py:54`) — a
  **separate** pool from asyncio's default executor. So the double-hop
  APScheduler-thread → main-loop → `to_thread` worker does NOT consume a
  `to_thread` slot; the main loop stays free while awaiting the `to_thread`
  future. `grep` confirms NO `set_default_executor` / bounded `ThreadPoolExecutor`
  anywhere in `modules/` or `main.py` — only `run_in_executor(None, input, …)`
  (`main.py:686`) on the default pool. The ~20-worker default pool is intact. **No
  deadlock.**
- **The F3 fix holds under direct test.** Ran `asyncio.to_thread(worker)` and
  called `asyncio.get_running_loop()` inside the worker → `RuntimeError: no running
  event loop`. So `playwright.sync_api` is uniformly safe in the `to_thread`
  worker on every dispatch path. The caller-type branch is correctly gone.
- **The two-sided liveness bar (≥5 live / <2 blocked, lines 97-101) is robust.**
  A 0.5s `time.sleep` on the loop yields <2 ticks; the same via `to_thread` yields
  ~50. Asserting ≥5 with a `<2` control means the bar can't be loosened to reopen
  F1 without failing the control. Sound.
- **F1 stays fixed.** No new inline sync sleep introduced; all blocking work funnels
  through Move 0's `to_thread` choke point (re-confirmed the four dispatch paths).
- **The JA3 "dormant, not claimed" fork IS a real fork, not a judgment call
  (priority 1, the pass-2 P2 fix).** Lines 286-289 make the trigger mechanical:
  *if the RECON-NEEDED question (local capture vs. approved public reflector) is
  unanswered → TLS layer dormant, NOT green.* The executor is never forced to
  decide PASS/FAIL on an unbuildable check; the default state until Master answers
  is dormant. This closes the pass-2 P2 "undecidable falsifiable check" hole.
- **The self-hosted JA3 observer IS buildable blind (priority 1, headline
  option).** I proved a plain **non-root** `socket` listener on `127.0.0.1`
  captures the raw 517-byte ClientHello (record `0x16`, handshake type `0x01`)
  before the handshake completes — stdlib only, no scapy, no tcpdump, no root. And
  I proved **loopback JA3 == internet JA3**: the JA3-relevant fields (cipher list
  + extension-type list) are byte-identical across different SNI/destination
  targets, because JA3 inputs are destination-independent and the SNI *content* is
  not a JA3 input. So the recon-implied worry — "loopback can't represent a real
  internet JA3" — is **false**. The headline mechanism certifies a real JA3 fully
  locally.
- **Baseline is 107 collected** (PF-2 correct); NO stealth code exists yet (this
  is a plan, not a diff). F5/F6/F8 remain cleanly closed (confirmed by re-reading;
  pass-2 already verified them live).
- **F9 (stealth-vs-access-control) holds a THIRD time.** Attacked hardest again
  (below); no move crosses into auth/access-control evasion.

---

## Findings table

| # | Plan-line quote (exact) | How it fails | Severity |
|---|---|---|---|
| **T1** | M1.2, line 173-177: *"**Also route B on `requests.ConnectionError`/`Timeout` (pass-2 P1):** … the browser fork must trigger on them too … Add `test_connection_error_routes_to_browser`."* | **The ConnectionError→browser fork has no cap and doubles latency on the class where the browser can't help.** `requests.get(timeout=15)` fails fast on a genuinely dead host (connection refused / NXDOMAIN); the plan then routes to `fetch_page_browser`, whose Playwright `page.goto` default navigation timeout is **30s** — and the plan specifies **no** `set_default_navigation_timeout`, no single-retry cap (verified: `grep` for any browser timeout in the plan = 0). So a dead-host fetch costs 15s (requests) + up to 30s (Playwright) ≈ **45s**, on hosts where a browser genuinely cannot help (a refused/NXDOMAIN connection is dead for both stacks). The plan conflates two ConnectionError sub-classes — anti-bot RST/tarpit (browser CAN help, different TLS stack) vs. dead host (browser CANNOT) — and routes both identically with no discriminator and no browser cap. On the 12h scheduler path an unattended run against a dead/tarpitting host burns ~45s/URL for no benefit (still under the `_marshal` 300s ceiling, so no timeout crash — just wasted latency). Move 0 keeps this OFF the event loop (no loop-block, no lie), so it degrades gracefully; but it's a real resource-waste seam the fork opened. | **MED** |
| **T2** | M1.6, line 280-281: *"(e.g. `scapy` sniffing loopback, or the `ja3` PyPI lib fed a `tcpdump`/`pyshark` capture). Add whatever it needs to G3's pinned install list."* | **The parenthetical "buildable-blind" examples are NOT buildable blind on Citadel as a non-root user — a misleading example that can send the executor down a dead path.** Live-verified: `scapy` sniffing needs `CAP_NET_RAW` → opening an `AF_PACKET` raw socket as user `patrick` returns `PermissionError [Errno 1] Operation not permitted`; `tcpdump` is `-rwxr-xr-x root root` (NOT setuid) so it fails without root; `dumpcap`/`tshark` (pyshark's backend) are **absent**; and `scapy`/`ja3`/`pyshark`/`dpkt` are all **MISSING** and unlisted in `requirements.txt`. Granting `CAP_NET_RAW` needs `sudo`/`setcap`, both on CLAUDE.md's hard-deny list. So an executor that reaches for the named "e.g." tools hits a permission wall. **Why this is only LOW, not a break:** the bullet's HEADLINE mechanism — "a small TLS-terminating listener that records the raw ClientHello and computes JA3" — I proved is buildable blind with stdlib sockets, no root, no missing package; and the "dormant, not claimed" fork saves the executor if it can't stand any of it up. The examples are a wrong-turn signpost, not a broken fork. | **LOW** |
| **T3** | Line 281: *"Add whatever it needs to G3's pinned install list."* | **G3's install list is left un-populated for the JA3 stack — a deferred pin, not an executable one.** Unlike `curl_cffi`/`playwright` (named + gated), the JA3-observer dependency is "whatever it needs," with no package or version named in G3 or `requirements.txt`. For the stdlib-socket headline mechanism this is fine (nothing to pin). But it means the plan never asserts G3-for-JA3 is satisfiable, so if the executor picks the scapy/pyshark path (T2) the pin is both unnamed AND unbuildable. Folds into T2; noted separately because it is the *reason* T2 is a signpost the executor might follow (the plan implies "just add it to G3" as if that resolves it). | **LOW** |

---

## Priority-by-priority verdict (the charter questions, answered)

**1. The JA3 observer fix — DECIDABLE BLIND. Confirmed closed (with a LOW residual).**
- *Is the self-hosted option actually buildable blind on Citadel?* **YES for the
  headline mechanism** (stdlib `socket` TLS-terminating listener captures the
  ClientHello without root — live-proven, 517-byte ClientHello captured). **NO for
  the parenthetical scapy/tcpdump/pyshark examples** (need CAP_NET_RAW / setuid /
  absent binaries — live-proven PermissionError; blocked by the sudo deny-list).
  → **T2/T3 (LOW):** the examples mislead but the headline saves it.
- *Does loopback carry a real internet JA3?* **YES.** JA3 fields (ciphers +
  extension-types) are destination-independent — live-proven byte-identical across
  different SNI targets; SNI content is not a JA3 input. Loopback is fully
  representative. The recon-implied worry is false.
- *Is "dormant not claimed" a real fork the executor can act on?* **YES — it is a
  mechanical trigger** (RECON-NEEDED unanswered → dormant), not a judgment call.
  The pass-2 P2 hole ("undecidable check the executor is forced to grade") is
  genuinely closed: the executor's default until Master answers is *dormant, not
  green*.

**2. The ConnectionError/Timeout browser fork — REAL but with a latency/cap gap.**
Routing ConnectionError→browser helps ONLY for the anti-bot RST/tarpit sub-class
(different TLS stack); on a genuinely dead host the browser ALSO fails, and with
Playwright's unstated 30s default it ~doubles latency (T1, MED). No infinite loop
(Playwright's 30s IS a cap, just generous and unstated), no loop-block (Move 0),
no double-*retry* beyond the single browser attempt — so it's a resource-waste
seam, not a hang. The pass-2 P1 fix closed the *coverage* hole (ConnectionError
now forks) but introduced an *efficiency* hole (no browser cap, no dead-vs-tarpit
discriminator).

**3. Move 0 held — no deadlock, robust bar.** The `run_coroutine_threadsafe`
double-hop uses a separate APScheduler pool, so it never consumes a `to_thread`
slot; the main loop stays live. The two-sided liveness bar (≥5/<2) can't be
loosened to reopen F1. **Confirmed sound (live-proven).**

**4. Prose-only / judgment-call check.** The two pass-2 HIGH fixes each ship WITH
a test (`test_connection_error_routes_to_browser` for P1; the V3 dormant fork for
P2 is a mechanical state, not a test-gated claim). No pass-1/pass-2 fix is
prose-only where it matters. The one residual judgment-risk — "which JA3 observer"
— is correctly converted to a RECON-NEEDED with a mechanical default (dormant).

---

## What I attacked hardest and could NOT break

**The JA3-decidable-blind spine (pass-2 P2's fix) AND the stealth-vs-access-control
line (F9).** I went at P2 with live probes rather than reasoning: I tried to prove
the "self-hosted, buildable-blind" JA3 observer was a paper claim (as pass 2
proved of the Flask reflector). It is not — a non-root stdlib socket listener
captures the raw ClientHello, and loopback JA3 equals internet JA3, so the check
is genuinely decidable fully locally. The only crack (T2) is that the plan's
*example* tools (scapy/tcpdump/pyshark) are the unbuildable ones while its
*headline* mechanism is the buildable one — a signpost error, not a broken gate,
because the dormant fork is the mechanical backstop. F9 survived a third pass: the
browser stealth patches defeat fingerprinting not authentication; M1.5 proxy stays
dormant behind G5; M2.2 disengages-never-solves behind G6; A1 is untouched. No
move reads non-public content or defeats an access control.

---

## Verdict: SOUND (no BREAKS REMAIN)

The pass-1 CRITICAL and both pass-2 HIGHs are **truly closed**, and I confirmed it
with live probes, not prose:

- **F1 (CRITICAL) — closed.** Move 0's `to_thread` covers all four dispatch paths;
  the double-hop is deadlock-free (separate APScheduler pool); the two-sided
  liveness bar is robust; no new inline sleep.
- **pass-2 P2 (HIGH, undecidable JA3) — closed.** The self-hosted JA3 observer is
  buildable blind with a stdlib socket (live-proven), loopback JA3 is
  representative of internet JA3 (live-proven), and the "dormant, not claimed"
  fork is a mechanical trigger, not a judgment call. The check is decidable blind.
- **pass-2 P1 (HIGH, missing ConnectionError browser fork) — closed for coverage.**
  ConnectionError/Timeout now forks to the browser and has a test.

The fixes did **not** open a new HIGH or CRITICAL seam. They left three lower
seams: **T1 (MED)** — the ConnectionError→browser fork has no browser cap and
doubles latency (~45s) on genuinely dead hosts where the browser can't help;
**T2 (LOW)** — the JA3 bullet's *example* tools (scapy/tcpdump/pyshark) are
unbuildable blind on Citadel as a non-root user, a misleading signpost the
buildable headline mechanism and the dormant fork both rescue; **T3 (LOW)** — G3's
JA3 install pin is deferred ("whatever it needs"), fine for the stdlib mechanism.

None of the three block execution: the verification is now decidable blind, the
autonomous path degrades gracefully (Move 0 + graceful-empty + dormant fork), and
the permanent line holds. The plan passes SUCCESS 1, 2, 3, 6, 8, and 9 as written.
**Recommend: sharpen the ConnectionError fork (add a browser navigation timeout
and a dead-vs-tarpit discriminator, or a single-attempt browser cap) and replace
the scapy/tcpdump/pyshark example with the stdlib-socket ClientHello capture as
the named mechanism — both quality polish, neither a gate on shipping.**
