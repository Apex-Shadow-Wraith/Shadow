# Phase B / Track B — LangGraph Cutover Design

**Status:** Design + spike (investigation phase). Cutover lands on a feature branch in a later prompt.
**Authoritative spec:** Shadow_Consolidation_Architecture_v1 §5.3 — full migration, no hybrid.
**Date:** 2026-06-07.

This document is the input to the cutover prompt. It maps what exists today, proposes the graph topology, sequences the migration, lists the behavioral contract the cutover must preserve, and flags the places where the §5.3 spec collides with current reality.

---

## 1. Orchestrator map — what exists today

The decision loop lives in [`modules/shadow/orchestrator.py`](../../../modules/shadow/orchestrator.py) (~3,000 lines). Step 2 (`_step2_classify`, line 1922) is the routing hub.

### 1.1 Routing decision points (tier order)

| # | Decision | File:line | Confidence |
|---|---|---|---|
| 1 | Contextual reference ("do that") via `_last_route` | [orchestrator.py:2173-2189](../../../modules/shadow/orchestrator.py#L2173-L2189) | 0.90 |
| 2 | Command prefixes (`/training`, `/benchmark`, …) | [orchestrator.py:2191-2266](../../../modules/shadow/orchestrator.py#L2191-L2266) | 0.95 |
| 3 | Proactive control commands | [orchestrator.py:2281-2297](../../../modules/shadow/orchestrator.py#L2281-L2297) | 0.95 |
| 4 | Greetings / introspection prefixes | [orchestrator.py:2299-2402](../../../modules/shadow/orchestrator.py#L2299-L2402) | 0.95 |
| 5 | Explicit module mention ("ask apex") | [orchestrator.py:2595](../../../modules/shadow/orchestrator.py#L2595) | 0.90 |
| 6 | Math regex (`\d+[+\-*/×÷^%]\d+`), Bible-verse guard | [orchestrator.py:2668-2696](../../../modules/shadow/orchestrator.py#L2668-L2696) | 0.85 |
| 7 | Code-context detection + **Session 47 informational-guard override** | [orchestrator.py:2698-2789](../../../modules/shadow/orchestrator.py#L2698-L2789) | 0.85 |
| 8 | Wraith/Cerberus/Morpheus stem matching (Morpheus gated by `registry.is_routable()`) | [orchestrator.py:2790-2892](../../../modules/shadow/orchestrator.py#L2790-L2892) | 0.85 |
| 9 | LLM router (Ollama JSON, low temperature) | [orchestrator.py:1975-2003](../../../modules/shadow/orchestrator.py#L1975-L2003) | 0.70 |
| 10 | Fallback keyword classifier | [orchestrator.py:2009-2041](../../../modules/shadow/orchestrator.py#L2009-L2041) | 0.50 |

**Session 47 override** (item 7): keyword-based code-context matching defers to the informational-guard predicate so that questions *about* code don't get routed to Omen for execution. The override semantics are mechanical — the graph translation must preserve them as a single predicate, not break them across edge conditions.

### 1.2 State carried across the 7 steps

- **`TaskClassification`** ([orchestrator.py:312-320](../../../modules/shadow/orchestrator.py#L312-L320)): `task_type`, `complexity`, `target_module`, `brain`, `safety_flag`, `priority`, `confidence`.
- **`ExecutionPlan`** ([orchestrator.py:324-328](../../../modules/shadow/orchestrator.py#L324-L328)): `steps`, `cerberus_approved`, `raw_plan`.
- **`self._last_route`** ([orchestrator.py:1201](../../../modules/shadow/orchestrator.py#L1201)) — cross-invocation routing memory (powers item 1 above).
- **`self._last_tool_results`** ([orchestrator.py:1409-1419](../../../modules/shadow/orchestrator.py#L1409-L1419)) — Apex escalation context.
- **`ToolResult`** ([modules/base.py:37-59](../../../modules/base.py#L37-L59)) — dataclass that flows Step 5 → Step 6.

### 1.3 Async, retry, queue

- **`RetryEngine`** ([modules/shadow/retry_engine.py](../../../modules/shadow/retry_engine.py)) — 12-attempt strategy rotation, fatigue tracking, Apex escalation. Wraps Step 5 at [orchestrator.py:1374](../../../modules/shadow/orchestrator.py#L1374).
- **`AsyncTaskQueue`** ([orchestrator.py:438-652](../../../modules/shadow/orchestrator.py#L438-L652)) — background worker loop, started at L648, stopped at L746. Runs **outside** the decision loop.
- **`PriorityTaskQueue`** ([orchestrator.py:433](../../../modules/shadow/orchestrator.py#L433)) — JSON-persisted task list.
- **`_should_run_in_background()`** ([orchestrator.py:821-842](../../../modules/shadow/orchestrator.py#L821-L842)) — priority ≥ 4 OR `_background=true` param, never Cerberus safety tasks.

### 1.4 Observability (Track C)

`observed_span` from [modules/shadow/observability.py:143-193](../../../modules/shadow/observability.py#L143-L193) uses `start_as_current_observation`, so child spans nest automatically via OTel context propagation.

| Span | File:line | Scope |
|---|---|---|
| `shadow.router_decision` | [orchestrator.py:1193](../../../modules/shadow/orchestrator.py#L1193) | Step 2 classification |
| `shadow.module_dispatch` | [orchestrator.py:1369-1372](../../../modules/shadow/orchestrator.py#L1369-L1372) | Step 5 + retry |
| `shadow.response_assembly` | [orchestrator.py:1428-1430](../../../modules/shadow/orchestrator.py#L1428-L1430) | Step 6 confidence + self-review |

Degrades gracefully if Langfuse is unreachable (yields `None`).

### 1.5 Behavioral contract — the regression gate

| Test file | Tests |
|---|---|
| `tests/test_orchestrator.py` | 192 |
| `tests/test_context_orchestrator.py` | 41 |
| `tests/test_retry_engine.py` | 40 |
| `tests/test_code_analyze_routing.py` | 39 |
| `tests/test_informational_guard.py` | 23 |
| `tests/test_contextual_routing.py` | 19 |
| `tests/test_false_positive.py` | 16 |
| `tests/test_decision_loop.py` | 9 |
| `tests/test_orchestrator_child_spans.py` | 9 |
| `tests/test_router_opt_out.py` | 5 |
| `tests/test_fallback_transparency.py` | 4 |
| **Total core gate** | **~397 tests** |

The cutover must keep these passing. Plus Phase 0 baseline at ≥78.18%.

---

## 2. LangGraph readiness

| Dependency | Installed | Pinned |
|---|---|---|
| `langgraph` | 1.2.4 | `==1.2.4` |
| `langgraph-checkpoint` | 4.1.1 | `==4.1.1` |
| `langgraph-checkpoint-sqlite` | 3.1.0 | `==3.1.0` (Phase B target) |
| `langgraph-checkpoint-postgres` | 3.1.0 | `==3.1.0` (staged for Track A) |

**Verified API symmetry:** `SqliteSaver` and `PostgresSaver` both expose `BaseCheckpointSaver` (`get`, `get_tuple`, `list`, `put`, `put_writes`, `aget`, `aput`, …). The Track A swap will be a constructor change, not a graph rewrite.

**Verified interrupt/resume semantics** (sanity-check script run during spike prep):
- `from_conn_string(path)` returns a context manager → `with SqliteSaver.from_conn_string(db) as saver:`.
- `compile(checkpointer=saver, interrupt_after=["node"])` halts after the named node; state persists to disk.
- A fresh process (new saver, same path, same `thread_id`) calls `graph.invoke(None, config=cfg)` to resume.
- `graph.get_state(config)` reads the checkpoint without resuming — useful for tests.

**No conflicts:** pydantic 2.13.2, OTel 1.41.1 (pinned), Langfuse 4.5.1, ChromaDB 1.5.8, FastAPI 0.136.0 all compatible.

**Side-effect:** `websockets` downgraded 16.0 → 15.0.1 to satisfy `langgraph-sdk<16`. Shadow does not import `websockets` directly.

---

## 3. Graph topology

### 3.1 Sub-graphs vs. nodes — per-module recommendation

| Module | Shape | Why |
|---|---|---|
| Shadow (orchestrator) | **Top-level graph** | The graph IS the orchestrator post-cutover. |
| ShadowModule (peer) | Single node | 4 tools, no internal branching. |
| Cerberus | **Sub-graph** | Ethics + injection-detect + reversibility + watchdog + snapshot — distinct phases. |
| Omen | **Sub-graph** | Lint / git / exec / scaffolding / scoring — distinct phases. |
| Grimoire | **Sub-graph** | 9 tools spanning store / recall / blocks / graph layer. Already the spike target. |
| Harbinger | **Sub-graph** | Briefings → alerts → personalization. |
| Reaper | **Sub-graph** | Search cascade (DDG → Bing → Reddit; SearXNG staged) has internal branching. |
| Apex | Single node | One external call path; retry/escalation lives in the wrapping retry sub-graph. |
| Wraith | Single node | Fast brain, single dispatch. |
| Nova | Single node | Content generation, single dispatch. |
| Morpheus | Sub-graph (gated) | Creative pipeline; dormant by default. |

### 3.2 Fast-path classifier — pre-graph short-circuit

Treat the 10-tier classifier as a **plain Python function** that runs before the graph and either returns a direct route (with `classify_path`, `confidence`, metadata) or hands off to graph entry. Reasoning:

- Pushing 10 tiers into conditional entry edges scatters the ordering across edge predicates and obscures the Session 47 override.
- The classifier is pure (modulo `_last_route` lookup) — making it a graph node would buy nothing and cost legibility.
- The pre-graph function still emits `observed_span("shadow.router_decision")` so Track C instrumentation survives unchanged.

The graph proper handles **module dispatch + retry + Cerberus safety check + response assembly + checkpoint persistence**.

### 3.3 Morpheus dormancy + daemon exclusion

- Morpheus sub-graph entry is guarded by a conditional edge predicate calling `registry.is_routable("morpheus")`. When dormant, the predicate routes to a no-op node that returns a `ToolResult(success=False, error="dormant")`.
- **Daemons (`daemons/void/`, `daemons/cerberus_watchdog/`) stay outside the graph entirely.** They are systemd-managed processes that observe system state, not request-path participants. The graph does not call them and does not wait for them.

### 3.4 ToolResult through graph state — no schema change

```python
class ShadowState(TypedDict):
    user_input: str
    classification: TaskClassification
    plan: ExecutionPlan | None
    tool_results: Annotated[list[ToolResult], add]   # reducer: append
    response: str | None
    last_route: TaskClassification | None             # checkpointed
```

The `Annotated[..., add]` reducer keeps `tool_results` as an append-only list so retry attempts and multi-tool plans accumulate naturally. **`ToolResult` itself is not modified** — Phase D owns the typed-subclass refactor.

### 3.5 Retry engine — wrapped sub-graph

`RetryEngine` stays a class. The graph wraps it in a sub-graph:

```
   ┌───────────────┐
   │ module_dispatch ├──success──► response_assembly
   └───────┬─────────┘
           │ failure
           ▼
   ┌───────────────┐
   │ retry_strategy │ ──(strategy rotation, fatigue, max 12)
   └───────┬─────────┘
           │ exhausted
           ▼
   ┌───────────────┐
   │  apex_escalate │
   └────────────────┘
```

The 12-strategy rotation table is *data*; the conditional edges are: succeed / retry-with-next-strategy / escalate. Keeping rotation logic inside `RetryEngine.run()` preserves the existing test surface (40 tests) without re-implementing rotation in graph topology.

### 3.6 `_last_route` lives in checkpointed state

`self._last_route` becomes a graph-state field keyed by `thread_id` (conversation ID). The checkpointer persists it across invocations automatically. The orchestrator instance no longer carries cross-invocation memory.

---

## 4. Migration sequencing (feature branch)

Each step is independently testable. Each step keeps the live orchestrator path operational behind a feature flag until the final cutover.

1. **Grimoire sub-graph** (spike — lowest risk, no consolidation pending).
2. **Cerberus sub-graph** (safety gate must work before anything dispatches through the graph).
3. **Apex sub-graph** (single fallback path, easy to validate independently).
4. **Wraith, Reaper, Harbinger, Nova, Omen, ShadowModule** sub-graphs — any order, behind feature flag.
5. **Router replacement** (fast-path classifier → pre-graph function; LLM router → graph node; fallback classifier → terminal edge).
6. **Retry engine sub-graph** wraps module dispatch.
7. **`AsyncTaskQueue` + `PriorityTaskQueue` stay external** — they invoke the compiled graph per deferred task. See challenge #1 below.
8. **Morpheus last** — still dormant; only the gate predicate needs wiring.
9. **Cutover**: flip the feature flag, archive `orchestrator.py`'s decision loop, leave the file as a thin shim that constructs the graph.

---

## 5. Behavioral contract — what the graph must preserve

The ~397 tests above are the gate. The cutover must preserve at minimum:

1. All 10 routing decision points in their current tier order.
2. Confidence bands per tier (0.95 / 0.90 / 0.85 / 0.70 / 0.50).
3. **Session 47** informational-guard / code-context override semantics, as a single predicate.
4. `_last_route` cross-invocation memory keyed by conversation (now via checkpointer).
5. Morpheus dormancy gate via `registry.is_routable()`.
6. 12-attempt retry rotation, fatigue logic, Apex escalation thresholds.
7. `observed_span` parent → child nesting (`router_decision`, `module_dispatch`, `response_assembly`) — plus Track D's search cascade spans inside Reaper.
8. `ToolResult` shape — no schema change in Phase B.
9. `AsyncTaskQueue` background worker semantics (priority ≥ 4 or explicit `_background=true`).
10. Cerberus safety-flag short-circuit before any module dispatch.

---

## 6. Challenges to the full-cutover / no-hybrid decision — flagged loudly

The §5.3 spec says "no hand-written decision loop remains." Five places where current reality complicates that:

### 6.1 `AsyncTaskQueue` is orthogonal to the decision loop

The background worker processes deferred priority-≥4 tasks **outside the request path**. LangGraph is a request-execution framework; long-lived background workers are not graph nodes. The honest framing: post-cutover the **decision loop** is pure LangGraph, but at the **process level** the orchestrator process still has a background worker that wraps graph invocations. This is not a decision-loop hybrid — but the spec language should be sharpened in the cutover prompt to acknowledge it.

### 6.2 Behavioral-contract scale (~397 tests)

The first pass through the codebase undercounted the test surface by ~20×. Cutover effort scales with test maintenance, not with module count. Plan for it.

### 6.3 Sync Grimoire methods in an async graph

`Grimoire.remember()` / `recall()` / `_get_embedding()` are synchronous and block on `requests.post()`. The cutover pattern must wrap these in `asyncio.to_thread()` inside graph nodes. The spike establishes the pattern for one module so the rest don't have to re-litigate it.

### 6.4 Retry engine strategy rotation is non-trivial business logic

12 strategies × fatigue tracking × Apex escalation thresholds. Encoding this purely as conditional edges + state would hurt readability and break the 40 existing retry tests. Recommendation: keep `RetryEngine` as a class invoked from a single graph node that loops via a conditional self-edge. Not a hybrid; just pragmatic node design.

### 6.5 Checkpointer sync/async split — and `ToolResult` msgpack registration

Two LangGraph-internal findings surfaced during the spike:

- **Sync graphs need `SqliteSaver`; async graphs need `AsyncSqliteSaver`.** They are not interchangeable — calling `graph.ainvoke()` against a `SqliteSaver` raises `NotImplementedError` on `aget_tuple`. Same split exists on the Postgres side (`PostgresSaver` vs. `AsyncPostgresSaver`). The orchestrator is fully async today, so the cutover lands on `AsyncSqliteSaver` (and later `AsyncPostgresSaver` for Track A). Worth pinning the contract early so module sub-graphs don't drift.
- **`ToolResult` triggers a forward-compat warning** during checkpoint serialization: `Deserializing unregistered type modules.base.ToolResult from checkpoint. This will be blocked in a future version.` LangGraph's msgpack serde doesn't know about Shadow dataclasses and falls back to pickle. The cutover needs to either register `ToolResult` via `allowed_msgpack_modules` (config-level) or provide a custom serde. Cheap to fix; expensive to discover mid-migration if not flagged now.

### 6.6 Spec predates Track C / Track D instrumentation

§5.3 does not mention `observed_span`, the orchestrator's three child spans, or Reaper's search-cascade spans (Track D). The cutover prompt should treat the **current observability surface** as authoritative, not the spec. The graph topology in §3 reflects current reality.

**None of these are deal-breakers for full cutover.** All are surfaced so the cutover prompt can spec around them rather than discover them mid-migration.

---

## 7. Spike — see `spikes/langgraph_grimoire/`

The spike proves six properties on the Grimoire sub-graph:

| Proof | Verdict file |
|---|---|
| a. store/query round-trip through compiled graph | `tests/test_langgraph_spike.py::test_proof_a_round_trip` |
| b. pydantic config singleton inside graph nodes | `tests/test_langgraph_spike.py::test_proof_b_config_singleton` |
| c. SQLite checkpoint persists across process restarts | `tests/test_langgraph_spike.py::test_proof_c_process_restart` |
| d. `observed_span` parent/child nesting inside nodes | `tests/test_langgraph_spike.py::test_proof_d_observed_span_nesting` |
| e. `ToolResult` passes through graph state unmodified | `tests/test_langgraph_spike.py::test_proof_e_toolresult_passthrough` |
| f. Async execution compatible with Grimoire's surface | `tests/test_langgraph_spike.py::test_proof_f_async_compat` |

The spike is **not wired into the live orchestrator**. It lives at `spikes/langgraph_grimoire/` (new top-level dir, additive) and writes only to test temp dirs.
