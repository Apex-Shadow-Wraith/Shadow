# RED-TEAM PASS 4 — Reaper Part 2: Injection Discipline + Tier-2 Gate (final confirming attack)

**Attacker:** fresh instance, pass 4, blind executor of the THRICE-patched
`wargames/plans/stealth-part2-injection-gate.md`.
**Mandate:** passes 1, 2, 3 each landed a CRITICAL — a different autonomous
Reaper→Grimoire write path one layer further out (scheduler `run_task` → sync
`web_fetch` persist → async task queue). Move 4.3b was redesigned to close the
whole *class*: enumerate all SEVEN write sites, funnel through one shared tag
helper + one fail-closed `reaper_web_persist_allowed` predicate, thread real
`source` into `submit_task`, gate the async-queue write, add a completeness
meta-test. **My one job: find an EIGHTH path, or prove a claimed guard doesn't
hold.**
**Method:** read-only (grep, Read, `python -c`). The plan is UNAPPLIED (`grep
autonomous_research_enabled modules/ config/` → nothing; `modules/reaper/tagging.py`
absent). I attack the *route*, not applied code. Every claim carries `file:line`,
re-traced this pass.

---

## GATE-CLASS VERDICT: **CLASS CLOSED (no 8th path found), but the path-7 FIX has two BROKEN-GUARD defects — one HIGH.**

I ran the exhaustive enumeration the prompt demanded (`grep -rn "\.remember(" modules/`
→ 41 sites) and traced **every** one for whether Reaper-originated scraped content
can reach it. **No eighth autonomous Reaper-content write path exists.** The seven
the plan enumerates are the complete set. That half of the redesign holds.

But the *mechanism* the plan uses to close path 7 (the async queue) is broken in
two concrete ways the redesign never notices, and the worst one — a `TaskSource`
enum crash — makes the plan's own `submit_task` source-threading fix **throw
`ValueError`, fall back to synchronous dispatch, and route the autonomous Reaper
tool down a path where the path-7 gate never runs.** A gate whose enabling fix
crashes is "looks governed but isn't," one level deeper.

---

## PART A — The exhaustive 8th-path hunt (the decisive enumeration)

41 `.remember(` sites in `modules/`. Every one classified for Reaper-content reach:

| Site | `source_module` | Carries Reaper scraped content? | Why not an 8th path |
|---|---|---|---|
| `reaper.py:988/1192/1217/1377/1625` | reaper | **YES** (paths 1–5) | Enumerated; routed through helper by plan. |
| `standing_tasks.py:236` | reaper | **YES** (path 6) | Enumerated; M4.3 guard + helper. |
| `async_tasks.py:355` | shadow | **YES, generically** (path 7) | Enumerated; M4.3b gate+tag. |
| `standing_tasks.py:185` | omen | No — Omen `code_analyze_self` @0.9 | Non-Reaper; pass-2 confirmed. |
| `standing_tasks.py:291` | grimoire | No — Grimoire health stats | Internal telemetry. |
| `orchestrator.py:5699` | shadow | No — Step-7 op-log: `input=… \| module=… \| tool=…` metadata string, **not** tool result content | trust 1.0 but no scraped body; `user_input[:100]` + counters only. |
| `orchestrator.py:5129` | apex | No — apex_escalation self-teaching text | Apex escalation, not scraped web. |
| `apex.py:868/1072`, `teaching_extractor.py:203` | apex | No — token/cost log + teaching tiers | 200-char prompt/response summary, not scraped content. |
| `omen/code_analyzer.py:400`, `omen.py:2637`, `model_evaluator.py:657`, `problem_fingerprint.py:252` | omen | No — code patterns / self-analysis / benchmarks / code solutions | Omen domain. |
| `cerberus/security/analyzer.py:838`, `threat_intelligence.py:2209` | cerberus.security | No @0.7 `source="research"` — but content is a **hardcoded local `_CONCEPTS` dict** (`analyzer.py:795`), NOT web-scraped | `source="research"` label collides with Reaper's but origin is a static built-in KB. |
| `conversation_ingestor.py:652` | conversation_ingestor | No — Claude-Code transcript files from disk | Filesystem ingest, not web. |
| `staged_retrieval.py:133/146/466` | (inherits) | No — re-summarization layer; **zero live callers** (`store_with_summary`/`backfill_summaries` unreferenced) | Dead paths. |
| `self_teaching.py:249`, `behavioral_benchmark.py:784`, `embedding_evaluator.py:347`, `workflow_store.py:492` | shadow/… | No — teaching tiers / benchmark scores / workflow names | Telemetry & teaching. |
| `grimoire.py:732/1401/1875`, `grimoire_module.py:118/362/371`, `mcp_server.py:116` | grimoire | No — internal `remember`/`correct_memory`/`supersede_memory` + the generic `memory_store` router tool | Read-side/user-driven re-stores; `memory_store` is a router-directed general write through the full decision loop, not a Reaper autonomous write. |

**Candidate secondary triggers checked and cleared:**
- **Proactive Initiative Engine** (pass-3 P3-4 MED): `check_triggers()` results are
  written to **`self._task_tracker.create(...)` (SQLite `shadow_tasks`)** at
  `orchestrator.py:1220-1224` — NOT to the async queue and NOT to Grimoire.
  `TaskTracker.create` (`task_tracker.py:76-102`) is a bare INSERT; nothing
  consumes `shadow_tasks` to re-dispatch. `idle_work_cycle()` (`proactive_engine.py:361`)
  has **no caller anywhere** (grep). So the Proactive Engine does **not** currently
  reach an autonomous Grimoire write. P3-4 was over-stated; moot.
- **Harbinger briefing** (`harbinger.py:1553` `_pull_reaper` → `reaper.get_briefing_data()`,
  `reaper.py:1750`): pure **read** (`recall_recent`); Harbinger has zero `remember(`
  calls. Read consumer, not a write path.
- **Daemons** (Void, cerberus_watchdog): zero `remember`/`reaper`/`process_input`
  references (grep `daemons/`). Not a vector.
- **Graph nodes** (`modules/shadow/graph/*`): zero `remember(` calls (only a
  docstring mention). The graph dispatches through `_step5_execute`, so its writes
  are the same 7.

**Conclusion of Part A:** the write-path class is closed by enumeration. There is
no 8th autonomous Reaper-content write. The redesign's "enumerate-all" premise is
correct.

---

## PART B — The path-7 FIX is broken (attack vector 2 landed)

### B-1 — CRITICAL/HIGH: `submit_task`'s threaded `source` crashes on `TaskSource(source)`, forcing a sync fallback that skips the path-7 gate

**Plan line (M4.3b step 2):** *"add `source: str = "user"` to `submit_task` and
thread it to `create_task(source=source, …)`; the orchestrator's call
(`orchestrator.py:5229-5234`) passes the real `source` from `_step5_execute`."*

**Why it fails.** `create_task` coerces the string through a **restricted Enum**:
`source=TaskSource(source)` (`task_queue.py:406`). `TaskSource` accepts only
`{"user","module","scheduled","event"}` (`:35-40`). The autonomous sources the
gate exists to catch are none of these:

```
$ python -c "from modules.shadow.task_queue import TaskSource; TaskSource('autonomous')"
ValueError: 'autonomous' is not a valid TaskSource
```
Verified for `autonomous`, `proactive`, `idle_cycle`, `scheduled_task`,
`module_alert`, `webhook` — **all raise `ValueError`.** And `is_autonomous =
source not in ("user","telegram","discord")` (`orchestrator.py:4982`) means the
real backgrounded-autonomous `source` values are exactly these rejected strings.

**The consequence is worse than a crash.** `submit_task` is called inside a
`try/except` at `orchestrator.py:5227-5247`:
```python
except Exception as e:
    logger.warning("Async submit failed, falling back to sync: %s", e)
# falls through to line 5249: module.execute(tool_name, params)  ← SYNC
```
So the plan's own source-threading fix, on the autonomous path, throws → the
orchestrator **silently falls back to synchronous dispatch**. The task never
enters the async queue, so `_store_result_in_grimoire` and its path-7 gate
**never run**. Enforcement point (d) of G1 — "async-queue gate + tag" — is
bypassed by the very fix meant to feed it. The autonomous Reaper tool now runs
sync, and whether its content is gated falls entirely to path-1's sync gate,
whose `source`-plumbing the plan leaves under-specified (see B-2). **Severity:
HIGH** (the fix is non-functional for exactly the autonomous sources it targets,
and fails toward *executing* the tool, not blocking it).

**What the plan needed:** either map arbitrary source strings to a stored raw
field (not the `TaskSource` enum — e.g. a new `origin: str` on the payload/task),
or widen `TaskSource`. Threading a free-form `source` into a 4-value enum is an
Abort-A4 ripple the plan explicitly worried about ("if it forces a signature
change to `AsyncTask` that other code depends on") but mis-scoped to *positional*
callers (which are safe — all use `(module, tool, params)` positionally) while
missing the *enum-domain* break.

### B-2 — MED: the async worker RE-PLANS through the graph, so path-7's tool discriminator can be wrong both ways

**Plan line (M4.3b step 3, path 7):** *"`_store_result_in_grimoire` calls the
predicate with `task.source, task.tool_name`; … routes the Reaper-tool result
through `untrusted_memory_kwargs`."*

**Fact 1 — `task.tool_name` does not exist.** `QueuedTask` (`task_queue.py:62-80`)
has no `tool_name` attribute; the tool is `task.payload["tool_name"]`. Minor, but
the plan's literal accessor `AttributeError`s; the executor must read
`task.payload.get("tool_name")`.

**Fact 2 — the LIVE worker never executes the submitted tool directly.** In
production the queue is built with `orchestrator=self` (`main.py:287-291`,
`orchestrator.py:672-676`), so `self._orchestrator is not None` and the worker
takes `run_deferred_through_graph(task.description, source="autonomous")`
(`async_tasks.py:245`) — it **re-plans `task.description` from scratch** and
**ignores `task.payload` (tool_name/params) entirely**. The result_dict it then
persists has `tool_name="graph"`, `module="orchestrator"` (`async_tasks.py:329-330`),
and `content` = the synthesized final `response`, **not** the raw scraped page.

The plan's discriminator trusts the *submitted* `task.payload["tool_name"]`
(`web_search`), but the *executed* tool is whatever the router picks when it
re-plans `task.description`. This breaks both directions:
- A task submitted as `web_search` whose description re-routes to a non-Reaper
  tool → gated/capped as Reaper for content that isn't scraped (false cap; benign).
- **A task submitted as a non-Reaper tool whose description re-routes to a Reaper
  `web_search`/`web_fetch` → predicate sees the non-Reaper submitted tool →
  `reaper_web_persist_allowed` returns True → the scraped-content-derived response
  persists at 0.8, untagged (false MISS).**

The existing test `test_async_tasks.py:504-526` only passes its
`parsed["tool_name"]=="web_search"` assertion because it constructs the queue
**without** an orchestrator (`AsyncTaskQueue(task_queue, task_tracker, registry)`,
`:500`), taking the dead `else` branch. In production that branch never runs. So
the plan's path-7 test would be green against a code path that does not exist at
runtime — the pass-3 "mock past it" failure, re-instantiated. **Severity: MED**
(the gate keys on the wrong tool identity in the only branch that runs live).

### B-3 — MED: the completeness meta-test cannot mechanically discriminate the one Reaper write in `async_tasks.py`

**Plan line (M4.3b):** *"Completeness meta-test `test_no_reaper_write_bypasses_tag_or_gate`
— grep the three files for `remember(` with Reaper-reachable content … if a grep
finds a `remember(` outside the known set, FAIL."*

Grep sees text, not runtime provenance. In `standing_tasks.py` there are **three**
`remember(` calls with `source_module` = `omen` (:188), `reaper` (:239), `grimoire`
(:294) — the meta-test must accept two and flag none, discriminating by the
`source_module="reaper"` literal. Fine there. But `async_tasks.py:355` is the
**single** write site that serves **both** Reaper (`web_search`) and non-Reaper
(`code_analyze_self`, security scans) results, and it is hardcoded
`source_module="shadow"` (`:358`) — **not** `"reaper"`. So a grep keyed on
`source_module="reaper"` will **not recognize `async_tasks.py:355` as a Reaper
write at all**, and a grep that flags every `remember(` in the three files will
false-positive on `standing_tasks.py:185/291`. The Reaper-vs-non-Reaper split at
`:355` is a **runtime** decision (`task.payload["tool_name"]`), invisible to grep.
The meta-test therefore either passes **vacuously** (treats `:355` as "the known
site," always OK, never checking the runtime gate fires) or cannot express the
predicate at all. It cannot, as specified, prove a Reaper-tool result at `:355`
is capped while a non-Reaper one isn't. **Severity: MED** — the guard-against-a-
pass-5 is itself unable to see the very site pass-3 found.

---

## PART C — Are the pass-1/2/3 CRITICALs each truly covered? (yes, structurally)

- **Pass-1 (scheduler `run_task` / `/schedule run standing_research`):** COVERED.
  `_run_standing_research` (`standing_tasks.py:209`) and `run_task` (`:110-124`,
  CLI-live at `main.py:577`) are the only two callers of the firing function
  (`add_job` `:78`, `run_task` dict `:114`). M4.3's early-return inside
  `_run_standing_research` + a `run_task` refusal closes both. No second scheduler
  (one `StandingTaskScheduler` construction, `main.py:674`). Structurally sound.
- **Pass-2 (sync `web_fetch` full-page write @≤0.7):** COVERED IN INTENT, fragile
  in mechanism. `fetch_page` (`reaper.py:988`) writes inside the adapter
  (`reaper_module.py:127`, default `store_in_grimoire=True`). M4.3b path-1 gates it
  via `store_in_grimoire=reaper_web_persist_allowed(source, "web_fetch", gate_open)`.
  The hole: `source` must reach `ReaperModule.execute("web_fetch", params)`, but
  `_step5_execute` passes only `params` (`:5254`) — the plan says "use a stable key
  the async path also sets," yet B-1 shows the async path is bypassed on crash, so
  path-1 becomes the *sole* line of defense while its `source`-in-`params`
  plumbing is the least-specified part of the plan. Note also `web_fetch` is NOT
  in `_LONG_RUNNING_TOOLS` (`orchestrator.py:848-851` has `web_scrape`, not
  `web_fetch`), so `web_fetch` only ever runs sync by default — path-1 is the
  right place, but its wiring is hand-waved.
- **Pass-3 (async queue write @0.8):** ENUMERATED and gated in design, but the
  gate's runtime discriminator (B-2) and its enabling `source` thread (B-1) are
  both broken, and its completeness test (B-3) can't see it. The *class* is named;
  the *fix* doesn't hold as written.

## Detector / helper sanity (pass-2/3 holds re-confirmed)

- `PromptInjectionDetector.analyze(input_text, source, request_history) ->
  InjectionResult(score, flags, action)` (`injection_detector.py:94-159`);
  `UNTRUSTED_SOURCES` contains `"reaper_scrape"` (`:74`); thresholds `>0.7`/`>0.4`
  (`:146-149`). Plan wrapper maps correctly. **No normalization today** (`:116`
  `.lower()` only) — plan owns adding NFKC/zero-width + the regression test. HOLDS.
- Helper preserves `confidence`/`check_duplicates` (plan `:170-171`); five call
  sites set confidence (`reaper.py:991,1196,1221,1381,1628`). HOLDS.
- `submit_task` positional callers all use `(module, tool, params)` (grep) → the
  keyword-default `source` add is positionally safe (Abort A4 satisfied for
  signature). But the *enum-domain* break (B-1) is the real A4 ripple, unmarked.

---

## What I attacked hardest and could NOT break

- **The 8th write path.** 41 `.remember(` sites, all traced. Every non-enumerated
  one carries telemetry, teaching, code-analysis, static security KB, benchmark,
  transcript, or user-correction content — never Reaper-scraped web content. The
  Cerberus `source="research"` writes @0.7 (`analyzer.py:838`,
  `threat_intelligence.py:2209`) looked like a candidate but their `knowledge`
  comes from a hardcoded `_CONCEPTS` dict (`:795`), not the web. The
  Step-7 op-log @1.0 (`orchestrator.py:5699`) writes a metadata string, not tool
  content. **No 8th path.** The class is closed by enumeration.
- **The scheduler double-guard and research-pipeline containment.**
  `research()`/`run_standing_research()` reachable only via the guarded scheduler
  or `__main__` (grep). Reddit write (`:1377`) only via the router-unexposed
  `_reddit_search` pipeline. Contained, as the plan claims.
- **The write-side trust cap** `min(reputation, UNTRUSTED_WEB_TRUST)`. Sound on
  every path that goes through the helper.

---

## Verdict

**GATE CLASS CLOSED on the WRITE-PATH axis — no 8th path found.** The redesign's
core premise (enumerate-all + fail-closed) is correct: the seven sites are the
complete set of Reaper-content writes, verified against all 41 `.remember(` sites.
Three passes of "one more door" is over — there is no eighth door.

**BUT the path-7 fix does not hold as written**, and the failure is the same
"looks governed but isn't" class, now inside the *fix* rather than a missing path:

1. **HIGH (B-1):** the plan's `submit_task(source=…)` → `create_task(source=…)`
   threading throws `ValueError` for every autonomous source string
   (`TaskSource` is a 4-value enum; `autonomous`/`proactive`/`idle_cycle` are not
   members — verified by `python -c`). The exception is swallowed by the
   async-submit `try/except` (`orchestrator.py:5246`), **falling the autonomous
   Reaper tool back to synchronous dispatch** where the path-7 gate never runs.
   The gate's own enabling fix disables the gate.
2. **MED (B-2):** the LIVE worker re-plans `task.description` through the graph
   (`async_tasks.py:245`, orchestrator always wired) and stores a `tool_name="graph"`
   result — so a predicate keyed on the *submitted* tool can miss (or wrongly cap)
   the *executed* tool. The plan's path-7 test is green only in the no-orchestrator
   branch, which never runs in production.
3. **MED (B-3):** the completeness meta-test cannot grep-distinguish the single
   dual-purpose `remember(` at `async_tasks.py:355` (`source_module="shadow"`,
   serves Reaper and non-Reaper alike) — it passes vacuously and cannot prove the
   runtime cap fires.

**Front 5 is closed on enumeration but NOT on enforcement.** Before Master flips
`autonomous_research_enabled`, the path-7 fix must: (a) carry the autonomous
origin as a free-form field, not `TaskSource`, so `submit_task` doesn't crash and
fall back to sync; (b) key the async gate on the *submitted* `task.payload["tool_name"]`
AND account for the graph re-plan actually executing a possibly-different tool
(gate on what the re-plan dispatches, e.g. inside `_step5_execute` for both sync
and the recursive async submit, not on the outer task's declared tool); (c) make
the meta-test assert the runtime cap by spying `remember`, not by grepping
`source_module`. The hardest path I attacked — and the one that broke — is **the
plan's own `submit_task` source-threading fix crashing on the `TaskSource` enum
and silently falling back to synchronous, un-path-7-gated dispatch for the exact
autonomous sources the gate targets.**
