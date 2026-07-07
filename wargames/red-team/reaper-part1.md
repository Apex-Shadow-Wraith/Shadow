# RED-TEAM KILL-ATTEMPT — Reaper Part 1 (gathering)

**Target plan:** `wargames/plans/reaper-part1-gathering.md`
**Recon base:** `wargames/recon/reaper.md`
**Attacker stance:** executor following the plan blind, no other system knowledge.
**Read-only on the system.** Only this file was written. Nothing else changed.

**Verdict up front:** The plan is broken at its own front door. **The very first pre-flight
gate (PF-3) fails against reality and its paired abort (A1) mis-fires, halting the mission
before a single edit.** Separately, the Brave-removal move (M1.0) misses a real cross-module
secret-routing consumer and, worse, its documented failure mode is the *wrong* one — the true
failure is a silent secret leak, not an ImportError. And the M3.1 "expected observation" asserts
a tier value that the live code provably does not produce, so that move's test guards the wrong
URL and the real high-trust attacker vector survives. Multiple HIGH breaks; one CRITICAL. Details
below, each with the exact plan line quoted.

Legend: severity LOW / MED / HIGH / CRITICAL.

---

## 0. Spot-check of recon (recon is a target too)

Recon's `file:line` claims were spot-verified against the live code. Result: **recon is
substantially accurate**, with three drifts worth logging (two are the plan's problem, not
recon's):

- `main.py:673-675` scheduler — recon says `673-675`; actual is **`674-675`** (`StandingTaskScheduler` constructed at 674, `.start()` at 675). Off by one on the lower bound. LOW.
- Recon §8/§140 "**107 collected across the 7 `tests/test_reaper*.py` files**" is **CORRECT** — I verified per-file: brave 23, locale 4, mcp 23, node 8, reformulation 25, searxng 21, searxng_live 3 = 107. Recon counted all seven. The plan then mis-transcribed this (see F1).
- Recon §7.2 / §6.132 says `github.io` pages "inherit **0.7** trust." **This is FALSE.** `github.io` is not in `TIER_1_DOMAINS` (`reaper.py:99-104`) and evaluates to **Tier 4 / 0.1** live. The real over-credit is `gist.github.com` (matches `.github.com` suffix → 0.7). Recon planted a wrong example; the plan inherited it (see F6). **MED recon finding.**

Everything else load-bearing checked out: `_get_stealth_headers` rotation at `reaper.py:826-837`;
`_search_brave` region `717-782`; cascade slots `523-543`; `_stealth_delay` `821-824`;
`fetch_page` store at `988-999` (trust up to 0.7); SearXNG-disabled short-circuit `372-374`;
`reaper.py` uses **zero `logger`, 63 `print()`** (relevant to F5); standing-research writes at
`trust_level=0.3`, 12h interval, `check_duplicates=False` (`standing_tasks.py:236-249`).

---

## 1. THE BREAKS (each: quoted line → one-sentence failure → severity)

### F1 — PF-3 asserts a count the named command cannot produce; abort A1 mis-fires at pre-flight. **HIGH**
> Plan line 34: "`... tests/test_reaper_searxng.py --collect-only -q` → **expect `107 tests collected`, 0 errors.**"
> Plan line 251 (A1): "PF-3 not `107 tests` / any collection error → recon is stale; stop, re-recon before editing."

The PF-3 command lists **six** files (brave, locale, mcp, node, reformulation, searxng) but
omits `test_reaper_searxng_live.py`. Those six collect **104**, not 107 — I ran it: `104 tests
collected`. The "107" was copied from recon's *seven*-file total. So the plan's own first
pre-flight gate reads 104, A1's trigger ("not 107") fires, and the executor **STOPS and
re-recons before any edit** — a false abort on a perfectly healthy baseline. The mission cannot
start. This is a plan self-inflicted halt, and it's the cleanest kill in the deck.

### F2 — V1's post-delete count (84) is inconsistent with PF-3's own scope; a passing baseline reports FAIL. **MED**
> Plan line 264 (V1): "0 brave matches; **84 tests** collected, 0 errors"
> Plan line 56 (M1.0): "Collection drops from 107 to **84** tests (107 − 23)"

`84 = 107 − 23` assumes the **seven**-file total. But PF-3 (the baseline V1 is measured against)
scoped **six** files = 104. After deleting `test_reaper_brave.py` (23), the six-file collection
is **81**, not 84. So whichever collection command the executor reuses, V1's asserted "84" is
wrong for the six-file scope and right only for the seven-file scope the plan never actually
ran. A correct post-delete state gets graded as a regression (or vice-versa). Verification that
reports the wrong pass/fail on a correct result.

### F3 — M1.0 Brave removal breaks a cross-module config-routing contract the Build step never touches. **HIGH**
> Plan line 52 (M1.0 Build): "remove the `brave_search_api_key` field (`reaper_settings.py:30-37`)"
> Plan line 58 (Fork/A2): "if grep in the counter finds a *live consumer* (not just Reaper/tests) → STOP and flag ... Trigger = any match outside `modules/reaper/` and `tests/test_reaper_brave.py`."

The counter grep (`grep -rn "brave_search_api_key" ...`) that the plan mandates **does** hit a
match outside Reaper/tests: **`shadow/config/sources.py:167`**:
`"BRAVE_SEARCH_API_KEY": ("reaper", "brave_search_api_key"),` — the `FLAT_TO_PATH` registry that
routes the legacy flat `.env` name to the typed field. That is a live consumer in a *different*
package (`shadow/config/`), so by the plan's own Trigger, **A2 must abort M1.0.** The Build list
(line 52) enumerates five deletion sites and this one is absent. An executor working the Build
list top-to-bottom deletes the field, then either (a) trips A2 at the counter and stops with the
plan half-applied and no guidance on `sources.py`, or (b) if it reads the field deletion as
"inside Reaper's own settings, not another module," rationalizes past A2 and ships the break in
F4. Either way the plan does not name the file that must change.

### F4 — The M1.0 "most likely failure" is the WRONG failure; the real one is a silent secret leak, not ImportError. **CRITICAL**
> Plan line 57 (M1.0): "**Most likely failure:** another module imports `brave_search_api_key` from settings → `ImportError`/validation error at config load."

No module *imports* the field — `FLAT_TO_PATH` is a **string→tuple mapping**, so deleting the
typed field throws no ImportError and no validation error. The build *looks* clean and green.
But `ReaperSettings` is declared `model_config = ConfigDict(extra="allow", ...)`
(`reaper_settings.py:15`), and the `FlatEnvSource` docstring states the exact consequence
(`sources.py:147-150`):

> "CRITICAL: only list modules that have DECLARED the target field as `SecretStr | None`.
> Listing a flat name whose target module lacks a typed declaration causes the raw secret to
> land as a plain `str` in `extra=allow` storage — and then to leak through `model_dump_json()`."

So if the typed field is deleted but the `FLAT_TO_PATH["BRAVE_SEARCH_API_KEY"]` entry survives
(and the Build step never says to remove it), and a `BRAVE_SEARCH_API_KEY` is ever present in
`.env`/env, the router at `sources.py:203-210` writes `{"reaper": {"brave_search_api_key":
"<rawsecret>"}}`, it lands untyped in `extra=allow`, and `model_dump_json()` **stops redacting
it** — a plaintext secret leak into any config dump/log. The plan steers the executor to watch
for a loud ImportError that will never come while the actual, quiet, security-grade failure
(un-redacted secret) sails through green tests. This is the single worst break — see §2.

### F5 — M3.3 says "route through `logger`" but reaper.py has no logger; the alert it grades as PASS is unbuilt scaffolding. **HIGH**
> Plan line 210 (M3.3 Build): "(a) Route every rung attempt + failure + switch through `logger` (structured ...) — not `print`."
> Plan line 216 (Expected obs): "`grep -n "print(" reaper.py` in the cascade region → replaced by `logger` calls."

`reaper.py` imports no `logging`, defines no `logger`, and uses `print()` **63 times** (verified).
"Replace print with logger in the cascade region" understates a module-wide instrumentation build
(a shared logger, structured fields, and a Master-facing alert channel that **does not exist** —
`grep -rniE "harbinger|alert|notify" modules/reaper/` returns only a briefing-data docstring at
`reaper.py:1751`, no alert emitter). This is the plan's own named target front (the SearXNG
silent-failure class), and it is the "looks governed but isn't" gate: the plan *names* a
`rung-dead: searxng` alert and grades it as a V4 pass, but never wires a check that the alert
reaches Master — there is no reachable alert sink, so a test can assert the alert *object was
constructed* while nothing ever surfaces. Cries-wolf/stays-silent (the whole point of this front)
is untested at the delivery boundary. Directly hits red-team focus (c).

### F6 — M3.1 "expected observation" asserts a tier the live code provably does not produce; the test guards the wrong URL and the real 0.7 vector survives. **HIGH**
> Plan line 185 (M3.1 Expected obs): "a test asserts `evaluate_source("https://evil.github.io/x")["tier"]` is **not** 1 (is 3), and a genuine `arxiv.org` / `*.gov` doc is still Tier 1."

I ran `evaluate_source` live:
- `https://evil.github.io/x` → **tier 4 / 0.1** (github.io is NOT in `TIER_1_DOMAINS`).
- `https://gist.github.com/evil/x` → **tier 1 / 0.7** (matches `.github.com` suffix).
- `https://raw.githubusercontent.com/evil/x` → tier 4 / 0.1.
- `https://medium.com/@evil/post` → **already tier 3 / 0.3**.

So the plan's chosen example is doubly wrong: `evil.github.io` is already Tier 4 (never was 1),
and asserting it becomes **3** would *fail* the test on correct code. Meanwhile the actual
attacker-controlled high-trust path — publish under `gist.github.com`, land at **0.7** — is not
the URL the test guards, so the demotion the move exists to add can ship without ever covering the
real vector. The move's success criterion is fiction; a passing test here proves nothing about the
threat and misses the live 0.7 write. This is a "verification that reports PASS on a broken
result."

### F7 — M1.2 robots fork has no auth/paywall abort; A4 ("reading drifts to acting") is never wired into any fetch path. **HIGH**
> Plan line 254 (A4): "If a page requires auth, a form submit, or any non-GET to read → stop; Reaper reads public content only (Part 2 G4)."
> Plan line 82 (M1.2): "Before any `fetch_page` (`reaper.py:914`) network call, fetch and cache `/robots.txt` ... honor `Disallow` ... and honor `Crawl-delay`"

A4 is declared an abort, but no move installs the check. `fetch_page` (`reaper.py:914-948`) calls
`requests.get(url, ..., allow_redirects=True)` and has **zero** handling for 401/403, login walls,
paywalls, or Set-Cookie session gates (`grep` for `401|403|auth|login|paywall|cookie` in the fetch
path → nothing). `check_download_safety` (`843-908`) is extension/size only and **waves all HTML
through** ("HTML pages are always safe to fetch", `reaper.py:899-901`). With `allow_redirects=True`
a fetch can silently follow a 302 into an auth-gated URL and, on a soft-login page that returns
200 HTML, store the login-wall body at up to 0.7. A4 has no trigger, no detector, no test — it is
a named gate that "looks governed but isn't." Hits red-team focus (d): reading→acting drift is
unclosed.

### F8 — M1.4 Playwright renderer is "buildable" with the browser binary absent; the block is a manual pre-flight, not a code guard. **MED**
> Plan line 117 (M1.4): "**Most likely failure (PF-2):** Playwright package present but **browser binary missing** → launch throws. ... **Counter:** M1.4 is blocked by PF-2; the install is Gate G1.4 ..."
> Plan line 32 (PF-2): "MISSING → M1.4 ... is blocked until `python -m playwright install chromium` is run"

The only thing stopping M1.4 from being written-and-committed against a missing binary is the
executor *remembering* to run PF-2 and honor it. Nothing in the M1.4 build requires a runtime
capability probe (e.g. `chromium_executable_path().exists()`) before the render path is reachable;
the code can be merged green (unit tests can mock Playwright) while every live render throws at
launch. "Blocked by a pre-flight the executor may skip" is not a wired gate. If PF-2 is skipped or
mis-read, M1.4 ships a renderer that fails on first real JS page — the exact PF-2 failure the plan
claims to have countered. Hits red-team focus: Playwright move buildable when binary absent.

### F9 — M1.4 render fork trigger is a vague threshold the executor can't check blind. **MED**
> Plan line 118 (M1.4): "trigger = plain `requests` fetch yields text below a threshold (e.g. < 200 non-boilerplate chars) OR the page's `<body>` is script-dominated → escalate to render. ... No judgment call: the char-threshold decides."

"< 200 **non-boilerplate** chars" is undefined — "non-boilerplate" presupposes the readability
extraction of M3.2, which may not be built yet, and "**script-dominated** `<body>`" has no metric
(ratio? tag count? byte share?). The plan claims "no judgment call," but both halves of the OR are
judgment calls dumped on the executor. An executor blind to intent cannot write a deterministic
test for "script-dominated," so the fork is unverifiable — precisely the "expected observation too
vague to check blind" class the red-team was told to hunt.

### F10 — M2.2 grades a Master-facing CAPTCHA flag as PASS while admitting the alert path may not exist. **MED**
> Plan line 153 (M2.2 Expected obs): "`fetch_page` returns `None` with reason `captcha-wall`, makes **no** further request to that host, and **emits a Master-facing flag**."
> Plan line 155 (M2.2): "**RECON NEEDED:** is the Harbinger alert path reachable from Reaper's context? ... if not reachable, the flag is a structured log line ..."

The expected observation asserts a *Master-facing flag* is emitted as a pass condition, but the
adjacent RECON NEEDED concedes the alert path may be unreachable (I confirmed: no harbinger/alert/
notify emitter in `modules/reaper/`). So V3 can be graded PASS on a `print()`/log line that no
briefing ever consumes — a flag that "surfaces to Master" only in intent. Same failure class as
F5: asserting on a log/intent, not on the behavior (Master actually being alerted).

### F11 — M2.1 soft-block detector fork ("sudden content-length collapse") has no numeric trigger. **LOW/MED**
> Plan line 138 (M2.1): "a detected soft-block (e.g. sudden content-length collapse, a block page)"

"Sudden content-length collapse" names no baseline and no ratio — collapse relative to what prior
sample, by what factor? An executor cannot implement or test this deterministically; it's a
judgment call with no trigger, and a mis-tuned one either disengages live hosts (false positive)
or never fires. Vague-observation class again.

### F12 — M1.5 "304 reuses cache" but no dangerous-content re-validation gate on the cached body. **LOW**
> Plan line 125 (M1.5): "a test re-fetching a URL that returns `304` → no full body transfer, cached content returned"

The stale-invalidation counter (line 126) keys only on age (`WEB_SKIP_OLDER_THAN_DAYS`); nothing
re-checks the cached body against skip patterns or the (Part-2) injection tagging on a 304 replay,
so poisoned-but-fresh cached content is re-served without re-inspection. Minor here because the
trust discipline is explicitly Part 2, but the cache reuse path is a quiet write-back with no
gate, worth flagging.

---

## 2. THE SINGLE WORST BREAK — concrete run-through to the leak (F4 + F3)

**Why this one:** it is CRITICAL, it passes every check the plan defines (green tests, clean grep
after the counter, no ImportError), and it converts a "pure cleanup" move into an un-redacted
secret leak — the opposite of "well-behaved." It also defeats the plan's stated safety net (A2)
because the plan mis-describes the failure, so the executor is watching the wrong exit.

**Setup (real, from the code):**
- `ReaperSettings` is `extra="allow"` (`reaper_settings.py:15`).
- `FLAT_TO_PATH["BRAVE_SEARCH_API_KEY"] = ("reaper", "brave_search_api_key")` (`sources.py:167`).
- `FlatEnvSource._build_nested` reads `.env`+`os.environ` and, for every entry in `FLAT_TO_PATH`
  whose value is non-empty, writes it into the nested dict (`sources.py:202-211`).
- The docstring at `sources.py:147-150` states the exact hazard: an untyped flat name lands as a
  plain `str` under `extra=allow` and **leaks through `model_dump_json()`**.

**The run-through:**
1. Executor reaches M1.0. Follows the Build list (line 52): deletes `_search_brave` et al.,
   deletes the three cascade tuples, deletes the `config.py` constants, deletes the
   `brave_search_api_key` **field** from `reaper_settings.py`, deletes `test_reaper_brave.py`.
   The Build list never mentions `shadow/config/sources.py`.
2. Executor runs the mandated counter grep (line 57). It returns `sources.py:167` among the hits.
3. Two paths, both bad:
   - **Path A (honors A2 literally):** the match is "outside `modules/reaper/`," so A2 fires →
     executor STOPS with the field already deleted but the `FLAT_TO_PATH` entry still live and no
     plan guidance on how to reconcile `sources.py`. Mission stalls mid-edit; the plan gave no
     remediation for the one file that matters.
   - **Path B (rationalizes past A2):** executor reads "it's just Reaper's own env-routing, not
     another module's contract" (a defensible blind read, since the tuple *targets* reaper), and
     the plan's own "most likely failure" (line 57) primes it to expect a loud **ImportError** as
     the only risk. No ImportError occurs — deleting a typed field referenced only by a string
     mapping raises nothing. Tests are green. Grep-for-`brave` in `modules/reaper/` + tests is
     clean. V1 "passes."
4. Later (or in prod), a `BRAVE_SEARCH_API_KEY` is present in `.env` or the environment (it was
   the whole reason the field existed; Master may still have it set). `FlatEnvSource` routes the
   **raw secret** into `{"reaper": {"brave_search_api_key": "<secret>"}}`. With the typed
   `SecretStr` field gone and `extra="allow"` on, it is stored as a plain `str`.
5. Any `config.model_dump_json()` — a debug dump, a Langfuse span, a startup log, a support
   bundle — now emits the Brave key **in clear text**, unredacted, exactly as the `sources.py`
   docstring warns. The "pure cleanup, no paid infra" move has become a credential-disclosure bug
   that no gate in the plan catches, because the plan pointed the executor at an ImportError that
   never happens.

**Kill confirmed:** a move the plan calls "settled cleanup" with a green V1 ships an un-redacted
secret, and the plan's safety net (A2) is either tripped into a dead stall or bypassed by its own
mis-stated failure mode. The correct fix (delete the `FLAT_TO_PATH` entry in the same commit) is
never named. This is the run-through to the worst break.

---

## 3. WHAT I ATTACKED HARDEST THAT HELD (honest accounting)

I could not turn any Part-1 move into a **re-introduction of disguise/evasion** (red-team focus
(a)). I pushed hardest on M1.4 (Playwright) and M1.3 (backoff), looking for a place where
"rendering" or "reliability" smuggles back a fingerprint/proxy/UA-rotation:

- M1.4 explicitly forbids stealth plugins, canvas/WebGL, `add_init_script` fingerprinting, and
  `--disable-blink-features`, and its expected-obs greps for them (line 116). The honest-UA reuse
  (M1.1) is carried into the renderer. I found no seam where the render path *needs* disguise to
  pass — a JS page renders with a real browser and an honest UA, which is genuinely "read a JS
  page," not "look human." **This boundary holds.**
- M1.3's backoff explicitly ends in "a **clean logged skip** (never ... a tactic-switch to route
  around)" and M2.1 forbids UA-switch/proxy on disengage. I could not force a passing test that
  required switching identity. **Holds.**
- M2.2's `G-CAPTCHA` (permanent, never-earned-open) plus the V3 grep for solver deps is a real
  guard; I found no move that needs a solver to pass. **Holds.**

So the mission's *spine* — "respect the boundary, never route around it" — is intact at the
capability level. The plan does not smuggle evasion back in. Its failures are elsewhere: a
mis-transcribed pre-flight count, a missed cross-module secret-routing file with a mis-stated
failure mode, an unbuilt logging/alert substrate graded as if wired, a factually-wrong tier
assertion, and an unwired reading→acting abort. The disguise boundary held; the governance and
verification scaffolding did not.

---

## 4. SEVERITY ROLLUP

| ID | Break | Severity |
|----|-------|----------|
| F4 | M1.0 real failure is a silent secret leak, not ImportError (worst) | **CRITICAL** |
| F1 | PF-3 count wrong (104≠107) → A1 false-aborts at pre-flight | HIGH |
| F3 | M1.0 misses `sources.py:167` cross-module consumer; A2 tripped/bypassed | HIGH |
| F5 | M3.3 "route through logger"/rung-dead alert unbuilt; graded on intent | HIGH |
| F6 | M3.1 tier assertion factually wrong; test guards wrong URL, 0.7 vector survives | HIGH |
| F7 | A4 (reading→acting) never wired; fetch has no auth/paywall guard, follows redirects | HIGH |
| F2 | V1 post-delete count (84) inconsistent with PF-3 scope → false regression grade | MED |
| F8 | M1.4 buildable with browser binary absent (block is manual PF-2, not code) | MED |
| F9 | M1.4 render fork trigger vague ("non-boilerplate", "script-dominated") | MED |
| F10 | M2.2 Master-facing CAPTCHA flag graded PASS though alert path may not exist | MED |
| F11 | M2.1 "content-length collapse" soft-block fork has no numeric trigger | LOW/MED |
| F12 | M1.5 304 cache reuse has no content re-validation gate | LOW |

**Bottom line:** the plan's disguise-vs-access-control boundary survives attack, but it cannot be
executed as written — it halts itself at PF-3 (F1), and its flagship "cleanup" move ships a secret
leak (F4/F3) behind a mis-stated failure mode. Author must patch: fix PF-3/V1 counts to the
correct scope, add `shadow/config/sources.py:167` to M1.0's Build and re-word its failure mode to
the redaction leak, wire an actual logger + reachable alert sink before grading F5/F10, correct
the M3.1 example to `gist.github.com` (the real 0.7 vector), and give A4 a real detector in a
fetch-path move.
