# Cerberus Safety-Gate Surface Map

**Source:** promoted from Session 50, Step 3a — "Cerberus Safety-Gate
Investigation." This is the canonical reference the dispatcher-migration step
reaches for. Findings + proposed short-circuit topology; the Cerberus sub-graph
(Step 3b) has since landed at
[modules/shadow/graph/cerberus_subgraph.py](../../../modules/shadow/graph/cerberus_subgraph.py).

All counts and interfaces here were verified by `grep` / `grep -c` / direct
source reads — no estimates.

---

## Context

Cerberus is the safety gate. The 10-item behavioral contract (design doc §5
item 10) names it explicitly: *"Cerberus safety-flag short-circuit before any
module dispatch."* A wrong ToolResult from Grimoire is a bad answer; a missed
short-circuit means an unsafe request reaches a module that executes it. This
map captures the live surface so the short-circuit mechanism can be preserved
through the cutover.

---

## 1. Where Cerberus fires in the live decision loop (the five guards)

The live loop runs **five distinct Cerberus-related guards**, not one. The
design doc's "before any module dispatch" framing is *operationally* true but
obscures the actual ordering. Mapped against
[orchestrator.py](../../../modules/shadow/orchestrator.py):

| # | What | File:line | Run order |
|---|---|---|---|
| 1 | `CerberusWatchdog.is_locked()` lockfile check | [orchestrator.py:1075](../../../modules/shadow/orchestrator.py#L1075) | Step 1.0 — first thing after Step 1 input log |
| 2 | `_step1_5_injection_screen(...)` injection screen | [orchestrator.py:1084](../../../modules/shadow/orchestrator.py#L1084) | Step 1.5 — before classification |
| 3 | Per-step `cerberus.execute("safety_check", ...)` over each plan step | [orchestrator.py:4445-4464](../../../modules/shadow/orchestrator.py#L4445-L4464) | Step 4 — plan generation, before Step 5 |
| 4 | Plan-level guard `if not plan.cerberus_approved` | [orchestrator.py:4923-4931](../../../modules/shadow/orchestrator.py#L4923-L4931) | Step 5 — entry; refuses entire plan |
| 5 | Per-tool `cerberus.execute("hook_pre_tool", ...)` | [orchestrator.py:4962-4979](../../../modules/shadow/orchestrator.py#L4962-L4979) | Step 5 — immediately before each tool dispatch |

Guards 1 and 2 are **pre-graph** (they run before anything LangGraph would
see). Guards 3, 4, 5 are **in-loop** and translate to graph nodes/edges.

Design doc divergence: §5 item 10 implies a single guard. Reality is two layers
(plan-level at 3+4, per-tool at 5), plus two pre-graph defenses (1, 2). Both
layers must survive the cutover.

---

## 2. The short-circuit mechanism — quoted from source

### Layer A — plan-level (the main gate)

**Write site** at [orchestrator.py:4453-4464](../../../modules/shadow/orchestrator.py#L4453-L4464):
```python
if check_result.success:
    verdict = check_result.content
    if hasattr(verdict, "verdict"):
        from modules.cerberus.cerberus import SafetyVerdict
        if verdict.verdict == SafetyVerdict.DENY:
            logger.warning("Cerberus DENIED step %d: %s", step["step"], verdict.reason)
            plan.cerberus_approved = False
            return plan
```

DENY on any single step short-circuits the whole loop over steps and returns
the plan with `cerberus_approved=False`. `safety_check` returns a
`ToolResult(success=True, content=SafetyVerdict(...))` — the boolean lives
inside `.content.verdict`, not on the ToolResult envelope.

**Read site** at [orchestrator.py:4923-4931](../../../modules/shadow/orchestrator.py#L4923-L4931):
```python
if not plan.cerberus_approved:
    results.append(ToolResult(
        success=False, content=None, tool_name="plan",
        module="orchestrator", error="Plan was denied by Cerberus",
    ))
    return results
```

This is the **single guard that prevents module dispatch**. It is at the top of
`_step5_execute`, before the per-step dispatch loop starts. If the loop reaches
the dispatch line ([orchestrator.py:5010](../../../modules/shadow/orchestrator.py#L5010)
`result = await module.execute(tool_name, params)`), `plan.cerberus_approved`
is necessarily True. The property the sub-graph must preserve: **when
`plan.cerberus_approved=False`, the dispatch line is unreachable.**

### Layer B — per-tool hook (defense in depth)

**At [orchestrator.py:4962-4979](../../../modules/shadow/orchestrator.py#L4962-L4979)**,
before each tool dispatch:
```python
if cerberus:
    pre_hook = await cerberus.execute("hook_pre_tool", {"tool_name": ..., "tool_params": params})
    if pre_hook.success and hasattr(pre_hook.content, "verdict"):
        if pre_hook.content.verdict == SafetyVerdict.DENY:
            results.append(ToolResult(success=False, ..., error=f"Pre-hook denied: ..."))
            continue                   # <-- skips THIS tool, not the whole plan
        elif pre_hook.content.verdict == SafetyVerdict.MODIFY:
            params = pre_hook.content.modified_params or params
```

DENY here uses `continue` — skips just this tool, lets the plan keep running on
the remaining steps. MODIFY mutates `params` in place for the upcoming
dispatch. There is no plan-level state write; the effect is local to one
iteration of the dispatch loop.

### Escape hatches — the "looks-governed-but-isn't" check

**Eight command-prefix routes** ([orchestrator.py:1234-1315](../../../modules/shadow/orchestrator.py#L1234-L1315))
take a direct handler path that **completely bypasses Steps 3-6**, including
Cerberus:

| target_module | File:line | Handler |
|---|---|---|
| `proactive_control` | 1235-1244 | `_handle_proactive_control` |
| `training_pipeline` | 1247-1251 | `_handle_training_command` |
| `synthetic_generator` | 1254-1258 | `_handle_synthetic_command` |
| `benchmark` | 1271-1287 | `_handle_benchmark_command` |
| `embedding_eval` | 1290-1294 | `_handle_eval_command` |
| `transcript_ingestor` | 1297-1301 | `_handle_ingest_command` |
| `snapshot_exporter` | 1304-1308 | `_handle_export_command` |
| `generate` | 1311-1315 | `_handle_generate_command` |

Plus `_fast_response` at [orchestrator.py:1318-1353](../../../modules/shadow/orchestrator.py#L1318-L1353)
— text-only, no module dispatch, no Cerberus.

These are not new gaps; they are intentional creator-command routes. They route
off the fast-path classifier (design doc §3.2), which sits **before** the graph
entry. The LangGraph cutover does not introduce or close these — same coverage
as live.

**No other escape hatch found.** Retry paths re-enter `_step5_execute` through
`_step5_with_retry` ([orchestrator.py:4487](../../../modules/shadow/orchestrator.py#L4487))
and inherit the same `plan.cerberus_approved` guard. Background async-queue
submissions inside `_step5_execute` (the `_should_run_async` branch at
[orchestrator.py:4982](../../../modules/shadow/orchestrator.py#L4982)) run only
after the plan guard has already passed, and inject a Cerberus pre-hook just
like sync dispatch. Exception handlers around the dispatch line
([orchestrator.py:5025](../../../modules/shadow/orchestrator.py#L5025)) build
failure ToolResults, never reach a second dispatch.

---

## 3. State touched by the short-circuit

### `ExecutionPlan.cerberus_approved` — the only carried verdict

`bool`, default `False`, on [orchestrator.py:323-328](../../../modules/shadow/orchestrator.py#L323-L328).
Three write sites:
- [orchestrator.py:3870](../../../modules/shadow/orchestrator.py#L3870) — set `True` for `target_module="direct"` (no tools, no safety needed)
- [orchestrator.py:4463](../../../modules/shadow/orchestrator.py#L4463) — set `False` on first DENY (short-circuit)
- [orchestrator.py:4474](../../../modules/shadow/orchestrator.py#L4474) — set `True` after the for-loop completes with no DENY

Two read sites:
- [orchestrator.py:1364](../../../modules/shadow/orchestrator.py#L1364) — logged as decision-loop metadata (diagnostic)
- [orchestrator.py:4923](../../../modules/shadow/orchestrator.py#L4923) — the dispatch guard

**Already present in `ShadowState` (Step 1):** `plan: ExecutionPlan | None`
([skeleton.py:47](../../../modules/shadow/graph/skeleton.py#L47)). The
`cerberus_approved` field rides on the `ExecutionPlan` dataclass already in
state — no new top-level field needed.

### `TaskClassification.safety_flag` — **NOT a gate, despite the name**

The field at [orchestrator.py:318](../../../modules/shadow/orchestrator.py#L318)
(`safety_flag: bool  # does Cerberus need to pre-screen?`) is **set** by
upstream injection-detection / watchdog paths but **never read** as a
conditional to gate whether `cerberus.execute("safety_check", ...)` runs. The
gate at [orchestrator.py:4432-4434](../../../modules/shadow/orchestrator.py#L4432-L4434)
is `if "cerberus" in self.registry and cerberus.status == ModuleStatus.ONLINE`
— module presence, not the flag. Cerberus runs unconditionally on every plan
step that has a tool, regardless of `safety_flag`. The sub-graph plan must not
infer behavior from it.

### Per-tool MODIFY mutation

`params` is rebound at [orchestrator.py:4979](../../../modules/shadow/orchestrator.py#L4979)
(`params = pre_hook.content.modified_params or params`) — local to the for-loop
iteration, never written back to `plan.steps`. In a graph translation this
stays node-local; doesn't need to live in `ShadowState`.

---

## 4. Cerberus's dispatch surface

| Field | Value | Citation |
|---|---|---|
| Adapter class | `class Cerberus(BaseModule)` | [cerberus.py:66](../../../modules/cerberus/cerberus.py#L66) |
| Dispatch method | `async def execute(tool_name, params) -> ToolResult` + if/elif table | [cerberus.py:227-501](../../../modules/cerberus/cerberus.py#L227-L501) |
| Tool count | **39** (15 native + 24 absorbed from Sentinel) | `grep -c '"name":' modules/cerberus/cerberus.py` = 39; cross-checked at [docs/phase-a/sentinel-cerberus/tool_diff.md](../../phase-a/sentinel-cerberus/tool_diff.md) |
| Special path? | **No.** Orchestrator calls `await cerberus.execute("safety_check", ...)` like any other module tool. | [orchestrator.py:4445](../../../modules/shadow/orchestrator.py#L4445), [orchestrator.py:4963](../../../modules/shadow/orchestrator.py#L4963) |
| Heartbeat side effect | `self.send_heartbeat()` fires inside the `safety_check` branch | [cerberus.py:238](../../../modules/cerberus/cerberus.py#L238) |
| `_record_call` parity | Every branch increments via `self._record_call(...)` — same surface to preserve as Grimoire | (multiple sites in cerberus.py:227-501) |

The two safety-critical tools (`safety_check`, `hook_pre_tool`) are the only
ones the in-loop guards use. The other 37 are post-incident audit / security
analyzer / threat intel / rollback tools dispatched normally through `execute`.

---

## 5. observed_span surface for Cerberus

`grep -rn 'observed_span(' modules/cerberus/` → **zero matches**.
`grep -rn 'langfuse\|opentelemetry' modules/cerberus/` → no direct usage in the
dispatch path.

Identical to Grimoire's observability posture: Cerberus is span-silent; the
only span over a Cerberus call in the live path is the parent
`shadow.module_dispatch` (when called from Step 5) or the parent
`shadow.router_decision`/Step-4 region (when called from Step 4). The sub-graph
stays silent — adding new spans would create instrumentation that doesn't exist
in the live path, violating "live stays authoritative."

---

## 6. Cerberus regression test set — exact counts

`grep -c '^\s*def test_\|^\s*async def test_'` per file:

| File | Count |
|---|---|
| `tests/test_cerberus.py` | 42 |
| `tests/test_cerberus_auto_registration.py` | 30 |
| `tests/test_cerberus_ethics.py` | 28 |
| `tests/test_cerberus_security_analyzer.py` | 37 |
| `tests/test_cerberus_security.py` | 30 |
| `tests/test_cerberus_security_threat_intelligence.py` | 22 |
| `tests/test_cerberus_security_tool_selection.py` | 12 |
| `tests/test_injection_detector.py` | 23 |
| `tests/test_cerberus_watchdog.py` | 9 |
| `tests/test_safety_report.py` | 9 |
| **Total** | **262** |

**Contract-critical short-circuit subset** (these specifically assert DENY →
halt behavior):
- `tests/test_cerberus.py::test_protected_path_write_denied` (lines 165-173)
- `tests/test_cerberus.py::test_shell_metacharacter_denied` (lines 176-184)
- `tests/test_cerberus.py::test_approval_required_tool` (lines 145-152)
- `tests/test_cerberus.py::test_denies_protected_path` pre-hook (lines 209-215)
- `tests/test_cerberus.py::test_denies_unapproved_external` pre-hook (lines 218-224)

These five are the load-bearing tests for the short-circuit contract. They must
stay green under the cutover.

---

## 7. Watchdog / daemon boundary

Two distinct watchdogs — different code, different purpose, different lifecycle.

### In-process: `modules/cerberus/watchdog.py:128-256`

`CerberusWatchdog.is_locked()` — static method, checks file existence at
`data/cerberus_lock`. Imported at [orchestrator.py:96](../../../modules/shadow/orchestrator.py#L96),
called at [orchestrator.py:1075](../../../modules/shadow/orchestrator.py#L1075)
(Step 1.0). Pure file-existence test, no I/O dependency beyond the filesystem.

**Topology:** lives in the **pre-graph** layer of the cutover (before any graph
node would run). Stays orthogonal to the Cerberus sub-graph.

### External: `daemons/cerberus_watchdog/watchdog.py:71-138`

Systemd-managed process. Polls `data/cerberus_heartbeat.json` on
`check_interval_seconds`; calls `emergency_response()` (`pkill -f shadow_core` +
Telegram alert) on `consecutive_failures >= threshold`. **Zero imports from
`modules/cerberus/`** — fully orthogonal process, exactly per design doc §3.3
("Daemons stay outside the graph entirely").

**Coupling, tight but clean:** Cerberus writes `data/cerberus_heartbeat.json`
via `send_heartbeat()` ([cerberus.py:1070-1096](../../../modules/cerberus/cerberus.py#L1070-L1096))
as a side-effect of every `safety_check` execution. The daemon reads the file;
if stale, the daemon creates `data/cerberus_lock`; the in-process watchdog sees
that lock at Step 1.0 and halts the next request. **No load-bearing graph
dispatch depends on the daemon directly.**

Preservation note: the heartbeat write happens *inside* `safety_check`
([cerberus.py:238](../../../modules/cerberus/cerberus.py#L238)). If the
sub-graph delegates dispatch to `cerberus.execute(...)` (Option A), the
heartbeat fires automatically. A duplicating sub-graph that bypasses `execute()`
would silently kill the heartbeat → the external daemon would think Cerberus is
dead → emergency_response would kill Shadow. **This is the single biggest reason
to delegate, not duplicate.**

---

## Proposed short-circuit topology

### Pre-graph (untouched by the sub-graph step)

These guards run before any LangGraph node and stay where they are:
- Step 1.0 watchdog lockfile check.
- Step 1.5 injection screen.
- Fast-path classifier — including the eight command-prefix escape hatches and `_fast_response`.

These mirror the design doc §3.2 fast-path classifier. No graph involvement.

### In-graph

**Cerberus sub-graph** — same Grimoire-pattern delegator:

```
CerberusCallState(TypedDict, total=False):
    tool_name: str
    params: dict
    tool_results: Annotated[list[ToolResult], add]   # shared reducer with ShadowState

build_cerberus_subgraph(cerberus_module) -> StateGraph:
    async def cerberus_dispatch(state):
        result = await cerberus_module.execute(state["tool_name"], state.get("params", {}) or {})
        return {"tool_results": [result]}
    builder.add_node("cerberus_dispatch", cerberus_dispatch)
    builder.add_edge(START, "cerberus_dispatch")
    builder.add_edge("cerberus_dispatch", END)
```

Same delegating posture, same physical-separation feature flag, same
span-silent observability. Symmetric with
[grimoire_subgraph.py](../../../modules/shadow/graph/grimoire_subgraph.py).

**Why this is the sub-graph (and not the safety orchestration):** Cerberus's 39
tools are a dispatch surface — the sub-graph wraps the dispatch, like Grimoire's.
The plan-level and per-tool *gating logic* is **orchestration**, not module
dispatch, and it lives in the parent graph's plan + dispatch nodes (which land
in later cutover steps when the planner and dispatcher migrate).

### The short-circuit, when the parent graph wires the orchestration (later step)

```
                ┌───────────────┐
classified ──►  │  plan_node    │  (Step 4 equivalent — calls cerberus subgraph
                │               │   N times with safety_check, aggregates into
                │               │   state["plan"].cerberus_approved)
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────────────┐
                │ approved? (conditional│  ──► False ──► END(blocked)
                │   edge predicate)     │
                └───────┬───────────────┘
                        │ True
                        ▼
                ┌───────────────┐
                │ dispatch_node │  (Step 5 equivalent — per step:
                │               │   1. invoke cerberus subgraph with hook_pre_tool
                │               │   2. on DENY: skip this tool, continue
                │               │   3. on MODIFY: update params
                │               │   4. on ALLOW: invoke the module sub-graph
                │               │      e.g. grimoire_subgraph)
                └───────────────┘
```

**The "no module reachable when flagged" property is encoded in the conditional
edge after `plan_node`.** Because that edge inspects
`state["plan"].cerberus_approved` and routes to `END(blocked)` on `False`, every
module sub-graph node (`grimoire_subgraph`, future `omen_subgraph`, etc.) is
downstream of the True branch only.

---

## Divergences from the design doc

1. **Design doc §5 item 10 says "Cerberus safety-flag short-circuit before any
   module dispatch."** Reality is two layers (plan-level + per-tool), plus two
   pre-graph defenses (watchdog + injection). The cutover preserves all four;
   the spec language is incomplete.
2. **Design doc §3.1 frames Cerberus sub-graph internals as "Ethics +
   injection-detect + reversibility + watchdog + snapshot — distinct phases."**
   Reality: those are post-incident tools (39 total), plus an injection screen
   that runs PRE-graph at Step 1.5 (not via Cerberus.execute), plus a watchdog
   lockfile check that also runs PRE-graph at Step 1.0. The sub-graph itself is
   a thin Grimoire-pattern delegator over the 39-tool surface.
3. **Design doc implicitly treats Cerberus as a single per-request gate.**
   Reality: it's invoked N+M times per request (N = plan steps for
   `safety_check`, M = tool steps for `hook_pre_tool`). The graph translation
   must respect that interleaving.
4. **The sub-graph inherits the Option-A dispatch posture** (delegate to
   `cerberus.execute` rather than duplicate the if/elif table). The heartbeat
   side effect (§7) makes this even more load-bearing for Cerberus than it was
   for Grimoire — a duplicating sub-graph would silently kill the daemon link
   and trigger emergency_response.

---

## Surprises (the things that bit twice in earlier phases)

1. **`TaskClassification.safety_flag` looks like a Cerberus gate. It isn't.**
   Set in multiple places ([orchestrator.py:1097](../../../modules/shadow/orchestrator.py#L1097),
   [orchestrator.py:1198](../../../modules/shadow/orchestrator.py#L1198)) as an
   informational marker; never read as a guard. Cerberus runs unconditionally
   per plan step. Don't infer behavior from this field in the sub-graph plan.
2. **Eight escape hatches bypass Cerberus entirely**
   ([orchestrator.py:1234-1315](../../../modules/shadow/orchestrator.py#L1234-L1315)).
   Not a new gap, but worth understanding: the LangGraph cutover does not
   introduce or close these. They route off the fast-path classifier in the
   pre-graph layer.
3. **The heartbeat side effect inside `safety_check` is load-bearing for the
   daemon.** A duplicating Cerberus sub-graph that bypasses `cerberus.execute`
   would silently kill `data/cerberus_heartbeat.json` writes → external daemon
   would think Cerberus is dead → `pkill -f shadow_core`. Option-A delegation is
   non-negotiable; the heartbeat canary test is mandatory.
4. **Two watchdogs share a name, do different things.** In-process
   `CerberusWatchdog.is_locked()` runs pre-graph at Step 1.0; external
   `daemons/cerberus_watchdog/` is a separate process. The "daemons stay out"
   rule applies to the external one. The in-process one is part of the pre-graph
   guard layer.
5. **Layer B's pre-hook can MODIFY params, not just DENY.** Easy to overlook
   when planning a graph node — the MODIFY case mutates the dispatch payload in
   flight. The orchestration node that wraps per-tool dispatch must handle three
   verdicts (ALLOW, DENY, MODIFY), not two.

---

## Verification gates for the dispatcher migration

The build that wires the safety orchestration into the parent graph validates
**262/262 Cerberus regression green** and the **orchestrator-untouched gate**
(`test_orchestrator.py` + `test_decision_loop.py` green, currently 201, AND the
import-isolation grep empty). The "63/63 orchestrator sanity" figure that
appeared in the Step 3a working notes was phantom — there is no 63-test
orchestrator gate; the real invariant is the 201 green-tests-plus-isolation rule
above. See [cutover-backlog.md](cutover-backlog.md) item 8.
