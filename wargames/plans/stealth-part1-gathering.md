# BATTLE PLAN — Reaper Part 1: Stealth + Professional Gathering (Fronts 1–3)

**Instance:** "stealth" (isolated run). **Executor:** Opus 4.8, max effort.
**Recon base:** `wargames/recon/stealth.md` (spot-verify its `file:line` before
trusting; treat every `RECON NEEDED` as unsettled until its check runs).
**Scope:** Fronts 1–3 — Reaper-internal capability: read the public web without
a distinguishing fingerprint (Front 1), notice hostility and back off (Front 2,
operational half), and be excellent at the actual research job (Front 3).
**Out of scope → Part 2:** write-time untrusted tagging, the
instruction-like-content DETECTOR, and the Tier-2 autonomy gate. Front 2's
operational responses (backoff / rung-switch / disengage) are here; the
content-inspection step they call is built in Part 2 and stubbed here (M2.4).

**The permanent line (binds every move):** Reaper GATHERS, never ATTACKS.
Stealth = "reads public content without being fingerprinted, throttled, or
served poison." It is NEVER for defeating authentication, evading access
controls, or reaching anything Master isn't entitled to read. Any move that
crosses that line is a mission failure, not a feature — see Abort A1.

---

## Pre-flight (run before Move 1; all read-only)

**PF-1. Confirm host capability matches recon §10.**
Run:
```
source ~/dev/Shadow/shadow_env/bin/activate
python -c "from shadow.config import config as c; print('searxng_enabled',c.reaper.searxng_enabled,'backend',c.reaper.search_backend,'brave',c.reaper.brave_search_api_key is not None)"
ls ~/.cache/ms-playwright
docker ps --filter name=searxng --format '{{.Names}} {{.Status}}'
```
- **Expected observation:** `searxng_enabled True backend ddg brave False`;
  `ls` lists `chromium-1208` (and headless_shell, ffmpeg); docker line reads
  `shadow-searxng Up … (healthy)`.
- **Most likely failure:** `ls ~/.cache/ms-playwright` empty → browser binaries
  gone since recon. **Cause:** cache cleared / different user. **Counter:** run
  `python -m playwright install chromium` (Gate G3 — pinned, into shadow_env
  context) before M1.2; if it fails offline, M1.2 forks to route B (skip
  browser path, mark RECON NEEDED for browser install).
- **Fork trigger (corrected red-team F8):** if `searxng_enabled` reads `False`
  here, the config changed since recon → **STOP and re-read the source of the
  `True`, which is the CHECKED-IN `config/config.yaml:98`** (NOT a local override;
  the schema default in `reaper_settings.py:23` is `False`, but `config.yaml`
  flips it). Also check `config/config.local.yaml` for a machine override. Do not
  assume SearXNG is primary until you see which file sets it.

**PF-2. Baseline the tests green before touching anything.**
Run: `python -m pytest tests/test_reaper*.py -q`
- **Expected observation:** `107 passed` (recon §8). Record the exact number.
- **Most likely failure:** fewer than 107 collected or any failure. **Cause:**
  environment drift. **Counter:** do NOT start the build on a red baseline —
  fix or flag first (Abort A4). A baseline that isn't 107-green means every
  later "tests still pass" observation is meaningless.

**PF-3. Snapshot for rollback (Gate G1 earned-by).**
Run: `git status --short && git rev-parse HEAD`
- **Expected observation:** clean tree (or only the `wargames/` and
  `benchmarks/` untracked files from the session), and a HEAD hash recorded.
- **Counter if dirty:** `git stash` unrelated changes so the Part-1 diff is
  reviewable in isolation. A verified rollback point is the earned-by for every
  code-write gate below.

**PF-4. Verify the dispatch threading model BEFORE writing any `time.sleep` (red-team F1).**
Run: `grep -n "run_in_executor\|to_thread\|def execute" modules/reaper/reaper_module.py`
and `sed -n '5253,5255p' modules/shadow/orchestrator.py`.
- **Expected observation:** `ReaperModule.execute` is `async def`
  (`reaper_module.py:82`) but calls sync `self._reaper.search(...)`/`fetch_page`
  **inline** (`:99, :127`) — **no `to_thread`, no executor** — and dispatch is a
  bare `await module.execute(...)` (`orchestrator.py:5254`). The async-queue
  worker (`async_tasks.py:252`) and the scheduler
  (`standing_tasks.py:160`, `run_coroutine_threadsafe(coro, self._loop)`) also run
  it on the SAME main loop.
- **Load-bearing consequence:** ANY blocking `time.sleep` inside `search`/`fetch`
  — including the EXISTING `_stealth_delay` (`reaper.py:821-824`), Reddit's 2s
  (`:1476`), and Brave's retry (`:748`) — **blocks the whole event loop today.**
  Move 0 fixes this before any new sleep is added. Do NOT write M2.1 backoff
  until Move 0 lands.

---

## MOVE 0 — Foundational: run Reaper's blocking engine off the event loop (fixes F1, enables F3)

**Do:** In `ReaperModule.execute` (`reaper_module.py:82-202`), wrap the sync
engine calls (`self._reaper.search`, `.fetch_page`, `.youtube_transcribe`,
`.search_reddit_json`, `.monitor_subreddit_json`) in `await asyncio.to_thread(...)`.
This moves ALL blocking work (existing stealth delays + Reddit/Brave sleeps + the
new M2.1 backoff + the M1.2 sync-Playwright path) off the main loop in ONE place —
the single dispatch choke point every path (orchestrator, async-queue, marshaled
scheduler) funnels through. The public `search`/`fetch_page` signatures are
UNCHANGED (no cross-module ripple, so Abort A2 does not trigger); only the adapter
changes how it invokes them.
- **Expected observation:**
  `tests/test_reaper_async.py::test_execute_does_not_block_event_loop` — drive
  `await reaper_module.execute("web_search", {...})` with the underlying
  `self._reaper.search` monkeypatched to `time.sleep(0.5)` then return results,
  WHILE a concurrent `asyncio` heartbeat task increments a counter every 10ms;
  assert the heartbeat advanced during the call. **Robust bar (pass-2 P3):** the
  gap between blocked and live is huge (~0-1 ticks vs ~50 over a 0.5s call), so
  assert **≥5 ticks** (not a jitter-fragile ≥30) AND add the control assertion
  that the pre-Move-0 inline path yields **<2 ticks** — the two-sided bar can't be
  loosened to silently re-open F1. Asserts **loop liveness**, not sleep count.
- **Most likely failure:** `self._reaper` touches non-thread-safe state (the Brave
  usage-file writer `reaper.py:798-815`) from the worker thread. **Cause:**
  `to_thread` runs on a ThreadPool worker. **Counter:** Grimoire is already
  thread-safe (RLock + `check_same_thread=False`, `standing_tasks.py:11-13`); guard
  the Brave usage read-modify-write with a `threading.Lock` on the Reaper instance
  **UNCONDITIONALLY as part of Move 0 (pass-2 P4)** — `to_thread` means concurrent
  workers regardless of whether a Brave key is set, so the lock is not
  "if M1.3/M2.1 exercise Brave," it is always added. `test_brave_usage_threadsafe`
  is a standing Move-0 test, not conditional.
- **Concurrency invariant (pass-2 P5):** Move 0 runs Reaper on the default
  `asyncio` ThreadPool, which the CLI's parked `input()` (`main.py:686`) also uses.
  Default pool size (min(32, cpu+4)) ≫ the one parked `input()` + concurrent
  Reaper fetches, so this is safe today — but **state the invariant in the Move-0
  commit**: if any future code sets a small `loop.set_default_executor` pool,
  Reaper fetches + the parked `input()` could contend. Not a blocker; a documented
  assumption.
- **Fork with trigger:** **if** any of the 107 `tests/test_reaper*.py` turns red
  after the wrap → a caller depended on `execute` being synchronous in-thread.
  Inspect the failing test; **if** it is a test-harness assumption (patches
  `time.sleep`, asserts call order) → update it to await properly. **If** the red
  test is a *production* call path relying on the sync side effect → STOP (Abort
  A2) and flag; that is real coupling, not a test fix.
- **RECON NEEDED:** confirm `async_tasks.py:252` tolerates `execute` now yielding
  to the loop (it already awaits a coroutine, so it should). **Check:**
  `sed -n '248,256p' modules/shadow/async_tasks.py`.

---

## FRONT 1 — Truly undetectable (stealth as it reads the public web)

### Move 1.1 — Make `stealth_mode` load-bearing (kill the dead flag)
**Do:** `stealth_mode` is read nowhere (recon §4). Wire it as the master
toggle: `_get_stealth_headers()` and `_stealth_delay()` (`reaper.py:821-837`)
already run unconditionally; add the new stealth layers (M1.2–M1.4) behind
`self._settings.stealth_mode`, and add one guard so `stealth_mode=False` yields
a single static honest UA (`config.reaper.reddit_user_agent`) + no delay for
debugging. Keep default `True`.
- **Expected observation:** new test
  `tests/test_reaper_stealth.py::test_stealth_mode_flag_toggles_layer` — with
  `stealth_mode=False` a monkeypatched `requests.get` receives the static UA and
  the timing layer records 0s delay; with `True`, UA ∈ `USER_AGENTS` and delay ∈
  [1.0, 3.0]. Test goes green.
- **Most likely failure:** flipping the flag off breaks a rung that assumed the
  browser-UA headers. **Cause:** hidden coupling. **Counter:** the off-path must
  still send a valid UA (never empty) — assert `headers["User-Agent"]` is
  non-empty in both modes.
- **RECON NEEDED:** none — flag surface fully traced (`reaper_settings.py:22`,
  `config.yaml:98`).

### Move 1.2 — Wire the Playwright full-stealth heavy-page path
**Do:** Add `fetch_page_browser(url, *, store_in_grimoire=...)` on `Reaper` using
`playwright.sync_api` (browsers present, recon §10). Apply stealth patches:
`navigator.webdriver=undefined`, a realistic viewport, `Accept-Language`,
timezone/locale consistency with the chosen UA, and Canvas/WebGL noise via an
init script. Route to the browser path only for pages the `requests` fetch fails
on or that need JS (fork below). Keep `requests` as the default light path.
- **Expected observation:**
  `tests/test_reaper_stealth.py::test_browser_fetch_returns_text_no_webdriver`
  — against a **local** fixture page served from `127.0.0.1` (a temp
  `http.server` the test starts), `fetch_page_browser` returns non-empty text and
  an in-page `navigator.webdriver` probe evaluates to `False`/`undefined`. Green.
- **Fork with trigger (corrected after red-team F2):** the current `fetch_page`
  calls `response.raise_for_status()` (`reaper.py:939`), which turns 403/429/503
  into an exception → the method returns `None` and the status code is discarded,
  so a `status_code in {...}` branch is a DEAD branch. First refactor `fetch_page`
  to capture the status the code actually exposes: in the `except
  requests.HTTPError as e` block (`reaper.py:946-948`), read
  `status = e.response.status_code if e.response is not None else None`. THEN the
  fork is real: **if** that captured `status in {403, 429, 503}` OR `fetch_page`
  returned non-None text < 200 chars → **route B:** retry via
  `fetch_page_browser`. The trigger reads a value the code now surfaces, not one
  it throws away. **Route B on `Timeout` but DISCRIMINATE dead-vs-tarpit
  (pass-2 P1 + pass-3 T1):** `requests.Timeout` and soft-block statuses are the
  tarpit/anti-bot class a browser CAN help — route B. But `requests.ConnectionError`
  (connection refused / DNS failure = genuinely dead host) → a browser retry
  can't help and just **doubles latency** (~30s Playwright default on top of the
  requests timeout); on `ConnectionError` return `None` fast, do NOT route to
  browser. **Cap the browser path:** `fetch_page_browser` sets an explicit
  Playwright navigation timeout (20s) — state it so the executor doesn't inherit
  an unbounded default. Tests: `test_timeout_routes_to_browser`,
  `test_connection_refused_does_not_route_to_browser` (returns None fast, no
  browser call spy), `test_browser_path_has_bounded_timeout`.
- **Most likely failure:** Playwright sync API raises
  `Error: It looks like you are using Playwright Sync API inside asyncio loop`.
  **Cause:** `fetch_page_browser` sync Playwright inside a running loop is
  forbidden. **Counter (corrected after red-team F3):** there is NO "sync
  scheduler" case — EVERY dispatch path runs the engine on the main loop
  (orchestrator, async-queue, and the scheduler which marshals via
  `run_coroutine_threadsafe`, `standing_tasks.py:160`). The previous "if scheduler
  → sync_api" branch was a false dichotomy that would plant the crash on the
  autonomous path. **Correct rule:** because Move 0 wraps the whole engine in
  `asyncio.to_thread`, `fetch_page`/`fetch_page_browser` run INSIDE a worker
  thread that has **no running event loop** — so `playwright.sync_api` is safe
  there, uniformly, on every path. Do NOT branch on caller type. Test:
  `tests/test_reaper_stealth.py::test_browser_fetch_from_async_context` drives
  `await reaper_module.execute("web_fetch", {...})` (which routes through Move 0's
  `to_thread`) against a local page and asserts NO "Sync API inside asyncio"
  error — this exercises the real async→to_thread→sync_playwright path, not a bare
  sync call.
- **Abort trigger:** if wiring the browser path requires making the public
  `fetch_page` itself `async` (signature change rippling into
  `reaper_module.py:127`, `standing_tasks.py`, `mcp_server.py`) — STOP, flag
  (Abort A2). Move 0 makes this UNNECESSARY: `fetch_page` stays sync; only the
  adapter's invocation is off-loaded.

### Move 1.3 — TLS-fingerprint randomization (JA3)
**Do:** `curl_cffi` / `tls-client` are NOT installed (recon §10). Install
`curl_cffi` (Gate G3) and route the light `requests` fetch through
`curl_cffi.requests` with `impersonate=` set to a browser matching the rotated
UA family (e.g. UA=Chrome/124 → `impersonate="chrome124"`). Map the 8 UA
signatures (`config.py:132-146`) to the nearest `curl_cffi` impersonation
target; add a `UA_TO_IMPERSONATE` dict in `config.py`.
- **Expected observation:**
  `tests/test_reaper_stealth.py::test_tls_impersonation_selected` — for each UA
  in `USER_AGENTS`, `_impersonation_for(ua)` returns a non-None target in
  `curl_cffi`'s supported set. Green. AND a live check (verification V3) shows a
  non-`requests`/urllib3 JA3 at a JA3 reflector.
- **Most likely failure:** the installed `curl_cffi` version doesn't support a
  named target (e.g. `chrome124`). **Cause:** version skew. **Counter:** pin to
  a `curl_cffi` version whose `curl_cffi.requests.BrowserType` enumerates the
  targets you map; assert the mapping against `curl_cffi`'s actual enum in the
  test (not a hardcoded string), so an unsupported target fails at test time, not
  in prod.
- **Fork with trigger:** **if** `curl_cffi` import fails after install (native
  build issue on the host) → **route B:** keep `requests`, mark
  `RECON NEEDED: curl_cffi native build on Citadel`, and do NOT claim TLS
  randomization in verification. The plan does not pretend a failed layer works.

### Move 1.4 — DNS-over-HTTPS for Reaper's own lookups
**Do:** DoH is absent host-wide (recon §10). Do NOT change the system resolver
(host-OS change, Gate G4). Instead give Reaper an in-process DoH resolver: a
small resolver that queries `https://1.1.1.1/dns-query` (or a Master-chosen
provider) and feeds the resolved IP to the fetch layer, behind
`config.reaper.doh_enabled` (default False until Master approves the provider).
- **Expected observation:**
  `tests/test_reaper_stealth.py::test_doh_resolver_returns_ip` — with a
  monkeypatched DoH HTTP response, `_resolve_doh("example.com")` returns a
  dotted-quad string; with `doh_enabled=False` the resolver is bypassed and
  system resolution is used. Green.
- **Most likely failure:** SNI still leaks the hostname even with DoH (DoH hides
  the DNS query, not the TLS SNI). **Cause:** DoH ≠ full hostname privacy.
  **Counter:** state this honestly in the plan output — DoH closes the DNS-leak
  vector only; ECH/encrypted-SNI is a separate, out-of-scope layer. Do NOT
  verification-claim "hostname hidden."
- **RECON NEEDED:** the DoH provider is Master's choice (privacy/trust
  tradeoff). **Check:** ask Master which resolver (`1.1.1.1`, `9.9.9.9`,
  self-hosted). Until answered, `doh_enabled=False` and the layer is dormant.

### Move 1.5 — Residential proxy plumbing (dormant)
**Do:** No proxy infra or account on host (recon §10). Build the plumbing only:
`config.reaper.proxy_url` (default None) threaded into both fetch paths; when
None, direct connection (today's behavior). Do NOT hardcode any provider.
- **Expected observation:**
  `tests/test_reaper_stealth.py::test_proxy_threaded_when_set` — with
  `proxy_url="http://127.0.0.1:9999"` set, the monkeypatched fetch receives
  `proxies={"http":..., "https":...}`; with None, no `proxies` kwarg. Green.
- **RECON NEEDED / BLOCKED-adjacent:** whether Master has a residential-proxy
  account is unknown (recon §9.2). **Check:** ask Master. The layer stays dormant
  (proxy_url=None) and is gated (G5) until Master provides a provider +
  credentials. Building the plumbing is safe; *enabling* it is paid-infra-gated.

### Move 1.6 — Fingerprint self-check harness (the ONLY thing that certifies Front 1)
**Do:** Add `scripts/reaper_fingerprint_check.py` with a **hardcoded host
allowlist** (default: the local reflector only). It fetches the reflector via
each fetch path and prints observed UA, JA3 hash, `navigator.webdriver`, headless
detection, and inter-request timings. **This script IS the network gate G2** — it
refuses to run against any host not in the allowlist, so "don't hit an
unapproved endpoint" is a mechanism (an `if host not in ALLOWLIST: sys.exit`),
not a comment (fixes red-team F7).
- **Red-team F4 — unit tests do NOT certify Front 1.** M1.2/M1.3's unit tests run
  against `127.0.0.1` fixtures and mocks; a green
  `test_tls_impersonation_selected` proves the UA→impersonation MAPPING, NOT that
  `curl_cffi` is on the wire, and a local `http.server` never does a real TLS
  handshake or faces an anti-bot. **Only V3 (live) certifies the stealth layer.**
  A stealth layer whose only evidence is a local-fixture unit test is NOT done
  (A3) — it is dormant.
- **The reflector — the JA3 half needs a REAL TLS observer (pass-2 P2).** A plain
  Flask app on `127.0.0.1` terminates HTTP after the handshake and **cannot see
  the client JA3**; `mitmproxy` is NOT installed on Citadel (verified) and
  `curl_cffi` has **no JA3 self-report API**. So the header/UA/webdriver/timing
  checks use the local Flask reflector (`scripts/fingerprint_reflector.py`,
  `127.0.0.1:8109`), but the **JA3 check needs one of these explicitly**:
  - **(preferred, buildable-blind — pass-3 proven) a stdlib `socket` listener** on
    `127.0.0.1` that `recv`s the raw TLS ClientHello (~517 bytes) and computes JA3
    from it (JA3 = TLS version + cipher list + extension types + curves — all
    destination-independent, so loopback JA3 == internet JA3; SNI is NOT a JA3
    input). This needs **no root, no `scapy`/`tcpdump`/`pyshark`** (all of which are
    unbuildable blind on Citadel: `CAP_NET_RAW` denied, `tcpdump` not setuid,
    `tshark` absent, `sudo` deny-listed). A ~40-line pure-stdlib parser is the
    mechanism; it keeps V3 fully local with zero new deps.
  - **(fallback) a Master-approved PUBLIC JA3 reflector** (e.g. a known JA3 echo
    JSON endpoint) added to the script's allowlist. Never a paid/anti-bot vendor
    (A1).
  - **RECON NEEDED:** which of the two Master wants (local capture stack vs. an
    approved public endpoint). Until answered, the JA3 sub-check is **un-runnable**
    → per A3 the TLS-randomization layer is marked **dormant, NOT claimed green**.
    The UA/webdriver/timing sub-checks still run locally and certify their layers.
- **Falsifiable PASS bar for V3 (fixes F7 "unfalsifiable"):**
  1. **Baseline capture first:** run the reflector once with the plain `requests`
     path, record `JA3_BASELINE` (the urllib3 hash).
  2. **UA rotation:** across 8 runs the observed UA set has size ≥3 AND every UA ∈
     `USER_AGENTS`.
  3. **TLS (requires the JA3 observer above; pass-2 P2):** on the `curl_cffi`
     path, the observer reports `JA3_OBSERVED != JA3_BASELINE` (the urllib3 hash
     captured in step 1). If no JA3 observer is stood up (RECON NEEDED unanswered),
     this sub-check is **un-runnable → TLS layer dormant, not claimed** (A3) — do
     NOT report TLS randomization green off a check that couldn't observe a
     handshake (the exact pass-2 P2 failure).
  4. **Browser path:** `navigator.webdriver === false` and the reflector's
     headless heuristic returns false.
  5. **Timing:** stdev of the 8 inter-request gaps > 0.3s (not a fixed cadence).
  Each is a mechanical PASS/FAIL an executor decides blind — no judgment call.

---

## FRONT 2 — Threat-aware (recognize hostility, back off) — operational half

### Move 2.1 — General rate-limit backoff + rung-switch
**Do:** Today only Brave handles 429 (recon §5). Add a shared
`_http_get_resilient()` used by SearXNG/Bing/`fetch_page`: on `429`/`503` honor
`Retry-After`, else exponential backoff (e.g. 1s, 2s, 4s, cap 3 tries), then
**switch rung** (search) or **give up cleanly** (fetch). Every backoff and
rung-switch emits a `logger.warning` (not `print`).
- **Expected observation:**
  `tests/test_reaper_threat.py::test_429_triggers_backoff_then_rung_switch` —
  a stub backend returning 429 twice then 200 causes exactly 2 backoff sleeps
  (monkeypatched `time.sleep` records calls) and a `logger.warning` containing
  `"rate-limited"` and the backend name. Green.
- **Most likely failure:** the backoff blocks the event loop. **Cause (corrected
  after red-team F1):** the adapter runs the sync engine INLINE on the main loop
  (`reaper_module.py:99`, no executor), so a bare `time.sleep` freezes the whole
  loop — the previous version of this move wrongly claimed "runs in an executor
  thread." **Counter:** this is exactly what **Move 0** fixes — with the engine
  wrapped in `asyncio.to_thread`, the `time.sleep` backoff runs on a worker thread
  and does NOT block the loop. **Move 0 is a hard prerequisite for M2.1** (see the
  DAG note in PF-4). The test must assert **loop liveness**, not sleep count:
  `tests/test_reaper_threat.py::test_backoff_does_not_starve_loop` reuses Move 0's
  heartbeat harness — drive `await execute(...)` against a stub backend that 429s
  twice, assert both (a) exactly 2 backoff sleeps recorded AND (b) the concurrent
  heartbeat kept ticking. A green sleep-count alone certifies nothing (the F1
  failure class).
- **Fork with trigger:** **if** all rungs exhaust with 429/blocks → return `[]`
  with a `logger.error("all search rungs rate-limited")` and metadata
  `{"exhausted": true}`. Executor/orchestrator sees empty+flag, not a hang.

### Move 2.2 — CAPTCHA-wall detection → avoid, never solve
**Do:** Add `_looks_like_captcha(html, url, status)` — detect interstitials
(`cf-challenge`, `recaptcha`, `hcaptcha`, `"unusual traffic"`, `"verify you are
human"`, known challenge paths). On hit: **disengage** this rung/URL, log, switch
rung (search) or abort the fetch (do NOT store). NEVER call a solving service
here (that is Part 2's gated last-resort, not a Part-1 default).
- **Expected observation:**
  `tests/test_reaper_threat.py::test_captcha_page_disengages_no_store` — feeding
  a known-captcha HTML fixture to `fetch_page` returns `None`, writes **nothing**
  to a spy Grimoire (`remember` call count 0), and logs `"captcha detected"`.
  Green.
- **Most likely failure:** false positive on a page that merely *mentions*
  "recaptcha" in body text. **Cause:** naive substring match. **Counter:** gate
  the check on structural signals (challenge script src, response status,
  known challenge hostnames) not raw body mentions; add a negative test
  `test_article_mentioning_captcha_not_flagged`.
- **The line (Abort A1):** "avoid, never solve" is permanent. Any move that adds
  automated solving without Gate G6 is a mission failure.

### Move 2.3 — Honeypot / bot-trap recognition → disengage
**Do:** Add `_looks_like_honeypot(soup, url)` — detect hidden links
(`display:none`/`visibility:hidden`/zero-size anchors funneling crawlers),
trap forms, and bot-only content markers. On hit: do not follow such links, do
not store, log.
- **Expected observation:**
  `tests/test_reaper_threat.py::test_hidden_link_trap_not_followed` — a fixture
  with a `display:none` honeypot link plus a real link yields extraction that
  excludes the trap and logs `"honeypot"`. Green.
- **Most likely failure:** over-eager filtering strips legitimately-hidden
  accessibility content (e.g. `sr-only`). **Cause:** CSS heuristics are blunt.
  **Counter:** only *avoid following* hidden anchors; never *drop visible body
  text* on a hidden-element signal. Assert body text is preserved in the test.

### Move 2.4 — Threat-flag STUB seam to Part 2
**Do:** In the fetch path, after extraction and before store, call
`self._inspect_content(text, url)` returning
`{"instruction_like": bool, "injection_score": float}`. **In Part 1 this returns
`{"instruction_like": False, "injection_score": 0.0}` (inert stub)** and is not
wired to storage tagging. Part 2 replaces the stub with the real detector AND
wires the flag into the write. Placing the seam now keeps Part 1 and Part 2 from
editing the same lines twice.
- **Expected observation:**
  `tests/test_reaper_threat.py::test_inspect_content_stub_present` — the method
  exists, returns the inert dict, and `fetch_page` calls it exactly once per
  fetch (spy). Green.
- **Abort trigger:** Part 1 must NOT change any `trust_level` or add
  `safety_class` at a write (that is Part 2, and doing it here without the
  read-side demotion would be a half-seam). If a Part-1 move tempts a write-tag
  change → STOP, it belongs to Part 2.

---

## FRONT 3 — Professional information gathering

### Move 3.1 — Close the cascade silent-fallback class (observability → alerting)
**Do:** Replace every rung-failure `print()` (`reaper.py:571, 620, 652, 714,
781`) with `logger.warning`. Add a per-rung failure counter; when an **enabled**
rung fails to serve N consecutive times (config, default 5), emit
`logger.error("rung <name> down: N consecutive non-serves")` once (edge-trigger,
not every call). This fully closes the SearXNG-class failure (recon §3a): a dead
enabled rung becomes loud, not silent.
- **Expected observation:**
  `tests/test_reaper_cascade.py::test_enabled_rung_down_alerts_once` — a stubbed
  SearXNG returning `[]` 5× with `searxng_enabled=True` emits exactly one
  `logger.error` containing `"searxng"` and `"down"`, and the cascade still
  serves via DDG. Green.
- **Most likely failure:** the alert fires for a rung that is *disabled by
  config* (SearXNG when `searxng_enabled=False`), which is not a fault.
  **Cause:** conflating disabled with failed. **Counter:** only count non-serves
  for rungs whose `available` predicate is True; add
  `test_disabled_rung_never_alerts`.
- **Fork with trigger:** **if** on this host `searxng_enabled=True` and SearXNG
  is healthy (PF-1), a live run must show SearXNG serving as primary; **if** it
  is `False` → the primary is DDG and the SearXNG alert path must stay silent.

### Move 3.2 — Source-eval hardening (user-content under Tier-1 suffixes)
**Do:** `evaluate_source` treats any `*.github.com`, `github.io`, `*.edu`
user-dir, `raw.githubusercontent.com`, gists as Tier-1 → 0.7 (recon §7.2). For
**source-quality ranking**, demote known user-content hosts/paths so
aggregator/user-content doesn't outrank primary docs. **Add a NEW field
`ranking_tier` to `evaluate_source`'s return dict — do NOT touch the existing
`tier`/`trust_score`/`source_type`** (fixes red-team F5). `tier` is load-bearing:
`check_download_safety` gates Tier-1 auto-allow on `source_eval["tier"] == 1`
(`reaper.py:875`) and the write stamps `"Tier {tier}"` into stored provenance
(`reaper.py:981`) — mutating it silently changes the safety gate and every stored
label. Add `USER_CONTENT_PATTERNS`; on match set `ranking_tier = 3` while `tier`
stays as-is; the research-pipeline sort (`reaper.py:1158`) switches to
`ranking_tier`.
- **Expected observation:**
  `tests/test_reaper_source.py::test_user_content_ranking_tier_3_but_tier_unchanged`
  — `evaluate_source("https://user.github.io/x")` returns `ranking_tier == 3` AND
  `tier == 1` AND `trust_score == 0.7` (unchanged); a `github.com/<org>/<repo>`
  docs URL returns `ranking_tier == 1`. Plus
  `test_download_safety_gate_unaffected` — `check_download_safety` for a Tier-1
  URL is byte-identical before/after M3.2. Green.
- **Critical scope fork:** this move changes **ranking only**. It must NOT be
  relied on as the *trust* fix — the trust cap that stops a payload landing at
  0.7 is **Part 2 / Front 4** (untrusted tagging). **If** the executor is tempted
  to also lower `trust_score` here → STOP: that is Part 2's write-side change and
  doing it in isolation creates a partial seam. Note the coupling in the commit
  message; leave the trust cap to Part 2.
- **Most likely failure:** demoting `github.com` blanket-breaks legit repo-doc
  trust. **Cause:** too-broad pattern. **Counter:** match user-content *paths*
  (`/gist/`, `raw.`, `*.github.io`, `~user`) not the whole `github.com` apex;
  keep `github.com/<org>/<repo>` docs at Tier 1 for ranking.

### Move 3.3 — Extraction quality (main-content isolation)
**Do:** Current extraction strips script/style/nav/etc. (`reaper.py:954-956`)
then dumps all text. Add readability-style main-content selection (largest
text-density block / `<article>`/`<main>` preference) before the char cap, so
stored content is the article, not chrome+comments.
- **Expected observation:**
  `tests/test_reaper_extract.py::test_main_content_beats_boilerplate` — a fixture
  page with a nav sidebar + article returns extracted text containing the article
  sentence and excluding the nav link text. Green.
- **Most likely failure:** heuristic drops the article on pages that don't use
  `<article>`/`<main>`. **Cause:** structure varies. **Counter:** fall back to
  the current full-strip extraction when the main-content block is < 200 chars;
  assert the fallback in a second fixture.

### Move 3.4 — Dedup + conflict flagging
**Do:** The research pipeline dedups by URL (`reaper.py:1142-1149`). Add
content-hash dedup (near-identical bodies across different URLs) and, when two
kept sources state conflicting facts on the query, attach a
`metadata["conflict_with"]` marker rather than averaging. Surface conflicts in
the returned result list.
- **Expected observation:**
  `tests/test_reaper_gather.py::test_conflicting_sources_flagged_not_merged` —
  two fixture sources with opposing claims produce two retained results each
  carrying a `conflict_with` reference; neither is dropped, nothing is averaged.
  Green.
- **RECON NEEDED:** conflict *detection* quality (semantic) may need phi4-mini.
  **Check:** decide deterministic (contradiction keywords / numeric mismatch)
  vs. phi4 classification; if phi4, confirm it's the scoring model already used
  (`config.py:273`) — no new model dependency.

### Move 3.5 — Specialized paths audit (Reddit primary, YouTube, finance)
**Do:** Confirm Reddit `.json` stays permanent primary for Reddit queries
(`reaper.py:500-519`, unchanged). YouTube is subtitles-only; Whisper is unbuilt
(`reaper.py:1597`). Investment-research free-API path is not built.
- **Expected observation:** no code change needed to confirm Reddit primary —
  `tests/test_reaper_gather.py::test_reddit_query_uses_json_first` asserts a
  Reddit-shaped query hits `search_reddit_json` before any general rung (spy on
  call order). Green.
- **RECON NEEDED (both out-of-scope for Part 1 unless Master expands):**
  (a) Whisper transcription — needs a Whisper model + GPU pipeline; **check**
  with Master whether Phase-5 Whisper is in scope now. (b) Financial free-API
  research — **check** which APIs/keys (recon found none). Until answered, these
  are BLOCKED, not guessed. Do not invent an API.

---

## Abort conditions (stop and flag; do not improvise)

- **A1 — the line is crossed.** Any move where "stealth" becomes defeating an
  access control, evading authentication, solving a CAPTCHA automatically
  (without Gate G6), or reaching non-public content. This is a mission failure.
  STOP, revert the move, flag to Master.
- **A2 — cross-module signature ripple.** If a stealth move forces the public
  `fetch_page`/`search` signature to change in a way that ripples into
  `reaper_module.py`, `standing_tasks.py`, or `mcp_server.py`. STOP — that is a
  shared-surface change beyond Part 1's scope; flag.
- **A3 — a stealth layer can't be verified honestly.** If TLS/DoH/browser can't
  be shown working at V3, do NOT claim it. Mark the layer `RECON NEEDED`/dormant
  and continue; a green unit test guarding an unexercised network path certifies
  nothing (SUCCESS 6).
- **A4 — red baseline.** If PF-2 isn't 107-green, do not build on it.
- **A5 — data-loss / write risk.** Part 1 should write **nothing** to Grimoire
  that isn't already written today. If a move adds or changes a Grimoire write,
  STOP — that is Part 2.

---

## Verification runs (built ≠ done; live-verified = done)

Run in this order; each states when and what PASS is.

- **V1 — unit suite (after each move, and all at end).**
  `python -m pytest tests/test_reaper_stealth.py tests/test_reaper_threat.py
  tests/test_reaper_cascade.py tests/test_reaper_source.py
  tests/test_reaper_extract.py tests/test_reaper_gather.py -q`
  **PASS:** all new tests green AND the original `tests/test_reaper*.py` still
  reports **107 passed** (no regression). Run the original suite too:
  `python -m pytest tests/test_reaper*.py -q` → `107 passed`.

- **V2 — cascade live, on this host.**
  With `searxng_enabled=True` (PF-1), run a real
  `reaper.search("ollama updates", 5)` and inspect ToolResult metadata.
  **PASS:** `backend == "searxng"` (primary served), ≥1 result, and the
  Langfuse/`logger` record shows the rung. **Fork:** if SearXNG is down at run
  time, `backend` reads `ddg` AND a `logger.warning` for the SearXNG non-serve
  is present — that is also PASS (graceful, observable), NOT a silent skip.

- **V3 — fingerprint live (the ONLY certification of Front 1; red-team F4/F7).**
  Run `scripts/reaper_fingerprint_check.py` ≥8× across both fetch paths against
  the allowlisted reflector (Gate G2). **PASS = all five falsifiable checks in
  M1.6 pass** (UA set size ≥3 & ∈ USER_AGENTS; `JA3_OBSERVED != JA3_BASELINE` and
  == the impersonation target's documented JA3; `navigator.webdriver === false`;
  headless heuristic false; inter-gap stdev > 0.3s). Green unit tests do NOT
  substitute for V3 — they test mappings/logic against local fixtures and certify
  no real TLS/anti-bot exchange. **FAIL→A3:** any layer that can't pass its V3
  check is marked dormant and NOT claimed; do not report Front 1 done on unit
  tests alone.

- **V4 — threat-response live-ish.**
  Point `fetch_page` at a local fixture server (PF/tests) that returns 429 then
  a captcha page then a honeypot page.
  **PASS:** 429 → backoff+rung-switch logged; captcha → `None`, zero Grimoire
  writes; honeypot link not followed, body preserved. No automated solve
  attempted (A1).

- **V5 — regression gate (before any commit series ends).**
  `python -m pytest tests/test_decision_loop.py tests/test_orchestrator.py -q`
  (Part 1 touches Reaper only, but `_inspect_content` seam + cascade logging sit
  on the dispatch path). **PASS:** no new failures vs. the pre-change baseline
  for those two files. (Full benchmark is Master's phase-gate call, not this
  plan's.)

---

## Gates & Autonomy Ledger (SUCCESS point 9)

Every Part-1 move that writes Shadow's code/config, touches the network, the
host OS, or paid infra — with what breaks ungated, the gate, and the earned-by.

| # | Move(s) | Danger if ungated | Gate (WIRED how) | Earned-by |
|---|---|---|---|---|
| **G1** | All code edits (M0–M3.5) | Self-modification of Shadow's own module code; a bad edit degrades research or breaks dispatch | **Corrected (red-team F6): the environment auto-commits (CLAUDE.md), so "Master reviews before commit" is NOT enforceable and is dropped.** The REAL enforced controls are: (a) `git push` is harness-deny-listed — nothing leaves Citadel without Master, so **Master's review checkpoint is at push time**, not commit; (b) verified rollback point (PF-3 `git rev-parse HEAD` + clean tree) so any bad commit is revertible; (c) targeted tests green gate the commit (Git-workflow rule). WIRED by the push deny-list + PF-3 + V1/V5. | PF-2 107-green + PF-3 snapshot recorded; V1/V5 green; commit is local-only (push blocked at harness) |
| **G2** | M1.6 / V3 network touch to a fingerprint reflector | Hitting a third-party (or anti-bot vendor) endpoint signals Reaper's traffic / may be disallowed | **Corrected (red-team F7): the gate is a MECHANISM, not a comment — `scripts/reaper_fingerprint_check.py` has a hardcoded host ALLOWLIST (default = the local `127.0.0.1:8109` reflector) and `sys.exit`s on any host not in it.** An external reflector enters the allowlist only after Master names one. WIRED by the allowlist check in the script itself. | Default self-hosted reflector needs no approval; any external host requires Master to add it to the allowlist (read-only public, no auth) |
| **G3** | M1.2/M1.3 package installs (`curl_cffi`, any `playwright-stealth`) | Adding deps to the env; supply-chain + version-skew risk | **Install into `shadow_env` only, pinned versions, Master-approved package list** — WIRED by pinning in `requirements.txt` and the test asserting the version's capability (M1.3) so an unexpected version fails at test time. | Master approves the package + pin; V1 green with the pin |
| **G4** | M1.4 DoH | Changing DNS resolution path; a bad resolver breaks all lookups or leaks to an untrusted provider | **In-process resolver behind `doh_enabled=False` default; NEVER edit `/etc/systemd/resolved.conf` (host-OS change)** — WIRED by the default-False flag + the RECON-NEEDED provider question blocking enablement. | Master picks the resolver; `doh_enabled` stays False until then |
| **G5** | M1.5 residential proxy | Routing Reaper's traffic through paid third-party infra; cost + trust + could be misused to evade blocks (A1 boundary) | **`proxy_url=None` default (dormant plumbing only); enabling requires Master-provided provider + credentials; must stay read-public-content-only** — WIRED by the None-default threading (test M1.5) and the A1 line. | Master provides account + explicitly approves; A1 re-affirmed (reading only, never evading access controls) |
| **G6** | Any future CAPTCHA-solving-service | Costs money, signals automation, edges toward "solve not avoid" | **Last-resort, never default, never autonomous, Master per-use approval** — WIRED here as an EXPLICIT NON-BUILD: M2.2 disengages and never solves; solving is out of Part 1 scope entirely. | Not earned in Part 1; a separate Master-approved decision |
| **G7** | Live web reads during V2/V3/V4 (real fetches) | Reaper reads the public web; must never cross into auth/access-control evasion | **Reads public content only, supervised (Master runs verification), stealth is for not-being-throttled — A1 is the hard line** — WIRED by A1 + verification being Master-run, not scheduled/autonomous. | Supervised run; targets are public, no auth |

**Autonomy note:** Part 1 changes **no** autonomy posture. It does not enable the
scheduler, does not add a Grimoire write, does not grant any new autonomous
action. The Tier-2 gate is Part 2's deliverable. Part 1's stealth capability is
built **fully** (browser path, TLS, DoH plumbing, proxy plumbing) but every
network-affecting layer arrives dormant-or-supervised behind the gates above —
capability and gate both present, neither amputated.

---

## Red-team focus (for the attacker subagent)

Attack hardest at: **(1)** any move where "stealth" quietly becomes "defeating an
access control" (A1) — especially M1.2 browser path and M2.2 CAPTCHA handling;
**(2)** any verification (V3 especially) that would report PASS on a layer that
isn't actually exercised against the network (the "green test guards a dead
path" failure); **(3)** the M2.4/M3.2 seam to Part 2 — find where a Part-1 move
smuggles in a trust/write change that belongs to Part 2 and creates a half-seam.

---

## Attack log (SUCCESS point 7 — filled after red-team)

Red-team pass 1 — `wargames/red-team/stealth-part1.md`. 9 findings (1 held).

- **F1 (CRITICAL) — attack that LANDED.** M2.1's counter claimed Reaper's sync
  `search()` "runs in an executor thread," so `time.sleep` backoff is safe. FALSE
  and verified against code: `ReaperModule.execute` is `async` but calls the sync
  engine INLINE (`reaper_module.py:99`), awaited on the main loop
  (`orchestrator.py:5254`) — a `time.sleep` freezes the whole loop, and the same
  defect sits on the autonomous scheduler path. The test asserted sleep COUNT, so
  it shipped green over a broken result (SUCCESS 1,2,6,9 failure).
  **Patch:** added foundational **Move 0** (wrap the engine in `asyncio.to_thread`
  at the single adapter choke point — fixes the existing `_stealth_delay`/Reddit/
  Brave sleeps too), added **PF-4** to verify the threading model first, corrected
  M2.1's counter, and replaced the sleep-count test with a **loop-liveness**
  heartbeat test (`test_execute_does_not_block_event_loop`,
  `test_backoff_does_not_starve_loop`).
- **F2 (HIGH) — LANDED.** M1.2's fork branched on `status_code in {403,429,503}`,
  but `fetch_page` calls `raise_for_status()` (`reaper.py:939`) and discards the
  status → dead branch. **Patch:** refactor `fetch_page` to capture the status in
  the `except HTTPError` block; the fork now reads a value the code exposes.
- **F3 (HIGH) — LANDED.** M1.2's async/sync Playwright fork ("sync_api for the
  scheduler") rested on a non-existent "sync scheduler" case and would plant the
  `Sync API inside asyncio loop` crash on the autonomous path. **Patch:** Move 0's
  `to_thread` worker has no running loop, so `sync_api` is uniformly safe there;
  removed the caller-type branch.
- **F4 (HIGH) — LANDED.** Stealth unit tests run against `127.0.0.1` fixtures, so
  green certifies no real TLS/anti-bot exchange. **Patch:** M1.6 + V3 now state
  unit tests do NOT certify Front 1; **only live V3** does, and a layer without a
  passing V3 is dormant (A3).
- **F5 (MED) — LANDED.** M3.2 mutated the shared `tier` field (breaks
  `check_download_safety` + stored provenance) while claiming "ranking only."
  **Patch:** demotion moved to a NEW `ranking_tier` field; `tier`/`trust_score`
  untouched; added `test_download_safety_gate_unaffected`.
- **F6 (MED) — LANDED.** G1's "Master reviews diff before commit" is
  unenforceable — the environment auto-commits. **Patch:** G1 reframed around the
  REAL controls (push is harness-deny-listed → Master's checkpoint is at push;
  verified rollback; tests-green gate).
- **F7 (MED) — LANDED.** G2 network gate was a comment; V3 PASS was unfalsifiable.
  **Patch:** the fingerprint script carries a hardcoded host allowlist (`sys.exit`
  off-list) = the mechanism; V3 gets five mechanical thresholds.
- **F8 (LOW) — LANDED.** PF-1 fork named `config.local.yaml` as the source of
  `searxng_enabled=True`; it is checked-in `config.yaml:98`. **Patch:** corrected.
- **F9 (HELD).** The stealth-vs-access-control line held — M2.2 avoid-never-solve,
  A1, and G6 are clean; no move crosses into auth/access-control evasion. Recorded
  as the move the attacker hit hardest and could not break.

Red-team pass 2 — `wargames/red-team/stealth-part1-pass2.md`. Move 0 held; two
HIGHs in the verification spine.

- **P2 (HIGH) — LANDED.** The F7 fix (V3 as the only Front-1 certification) has a
  hole exactly at TLS: a local Flask reflector observes no TLS handshake,
  `mitmproxy` isn't installed, and `curl_cffi` has no JA3 self-report — so the
  central JA3 check couldn't be decided blind, reproducing the "green over a dead
  path" failure the patch was meant to kill. **Patch:** M1.6 now names a real JA3
  observer (self-hosted ClientHello capture via scapy/`ja3`, or a Master-approved
  public reflector); if neither is stood up, the TLS layer is **dormant, not
  claimed** (A3). UA/webdriver/timing still certify locally.
- **P1 (HIGH) — LANDED.** The M1.2 status refactor covered HTTP status but left
  `requests.ConnectionError`/`Timeout` (`reaper.py:940-945`, return None, no
  status) with no browser fork — the tarpit class. **Patch:** route B now triggers
  on ConnectionError/Timeout too; `test_connection_error_routes_to_browser` added.
- **P3 (MED) — LANDED.** Move 0's liveness bar (≥30/50 ticks) was jitter-fragile.
  **Patch:** two-sided robust bar (≥5 live / <2 blocked) that can't be loosened to
  re-open F1.
- **P4 (MED) — LANDED.** The Brave-usage lock was conditional ("if Brave
  exercised"). **Patch:** unconditional Move-0 lock (to_thread → concurrent
  workers regardless of a Brave key).
- **P5 (LOW) — LANDED.** Move 0 shares the default ThreadPool with the CLI's
  parked `input()`. **Patch:** invariant documented (default pool ≫ contention;
  flag if a small executor is ever set).
- **HELD (pass 2):** Move 0's core `to_thread`-at-the-choke-point fix and the
  stealth-vs-access-control line (F9) survived a second, harder attack.

Red-team pass 3 — `wargames/red-team/stealth-part1-pass3.md`. **Verdict: SOUND —
no BREAKS REMAIN.** The pass-1 CRITICAL and both pass-2 HIGHs are truly closed,
confirmed with LIVE socket/JA3 probes (not prose): the attacker proved a non-root
stdlib socket captures the ClientHello on loopback and that loopback JA3 == internet
JA3, so the V3 TLS check is decidable fully locally. No deadlock in Move 0's
to_thread × the scheduler's `run_coroutine_threadsafe` double-hop (separate
APScheduler pool). F9 (stealth-vs-access-control) held a THIRD time — the move the
attacker hit hardest across all three passes and never broke. Residual, patched:
- **T1 (MED):** ConnectionError→browser fork doubled latency on genuinely dead
  hosts. **Patch:** discriminate dead (`ConnectionError` → return None fast, no
  browser) vs tarpit (`Timeout`/soft-block → browser); explicit 20s browser cap.
- **T2/T3 (LOW):** the JA3 bullet's `scapy`/`tcpdump`/`pyshark` examples are
  unbuildable blind (non-root, `sudo` deny-listed). **Patch:** M1.6 now names the
  stdlib-socket ClientHello capture (pass-3-proven, zero deps) as the mechanism.

Part 1 has now survived a clean pass (pass 3 landed no CRITICAL/HIGH; the
kill-attempt on the load-bearing spine FAILED). Post-pass-3 patches were MED/LOW
polish only. → **DONE** (see LEDGER).
