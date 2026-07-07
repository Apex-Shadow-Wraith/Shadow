# Phase B / Track B — Cutover Forward-Obligations

Carried-forward items that the per-module sub-graph migrations defer to later
cutover steps. Each entry names what was deferred, why, and where it must
land. Read this before starting the dispatcher-migration step — the items
under "Dispatcher migration (hard gate)" are non-negotiable safety
contracts.

---

## Dispatcher migration (hard gate)

The dispatcher migration is the step where the orchestrator's
`_step5_execute` loop becomes a LangGraph dispatch node, the planner becomes
a plan node, and the conditional edges between them encode the Cerberus
short-circuit. These items MUST be satisfied before that step can land:

1. **Structural reachability test — "no module sub-graph reachable when
   `cerberus_approved=False`."** The parent graph's plan_node sets
   `state["plan"].cerberus_approved`. The conditional edge after plan_node
   must route to a terminal `END(blocked)` node on `False` and to
   dispatch_node on `True`. A unit test must compile the parent graph,
   instrument each module sub-graph (Grimoire, Cerberus, future modules)
   with a "did I run" canary, set `cerberus_approved=False`, ainvoke, and
   assert that NO module sub-graph canary fired. Repeat with `True` and
   assert the target module DID run. This is the structural proof that the
   dispatch line is unreachable past a denial.

2. **Five contract-critical short-circuit tests must stay green.** Already
   in the regression set, they encode the safety contract:
   - `tests/test_cerberus.py::test_protected_path_write_denied`
   - `tests/test_cerberus.py::test_shell_metacharacter_denied`
   - `tests/test_cerberus.py::test_approval_required_tool`
   - `tests/test_cerberus.py::test_denies_protected_path` (pre-hook)
   - `tests/test_cerberus.py::test_denies_unapproved_external` (pre-hook)
   These exist today and must not drift through the dispatcher migration.

3. **Three-verdict handling in the per-tool hook node.** The dispatcher
   migration's per-tool hook handler must understand ALLOW / DENY / MODIFY,
   not just ALLOW / DENY. DENY uses `continue` semantics — skip just this
   tool, the plan keeps running on remaining steps. MODIFY mutates
   `params` in flight via `verdict.modified_params`. A two-verdict node
   silently drops MODIFY and the PII-stripping rule (and any future MODIFY
   rules) becomes a no-op. The MODIFY test in
   `tests/test_cerberus_subgraph.py::test_cerberus_subgraph_hook_pre_tool_modify_verdict_round_trip`
   pins the field reachability; the orchestration node must consume it.

4. **Heartbeat link preservation under all dispatch paths.** Step 3b's
   `test_cerberus_subgraph_safety_check_writes_real_heartbeat_file` proves
   the heartbeat write survives the sub-graph delegation. Any future
   refactor — including the dispatcher migration — that reaches into
   `Cerberus` internals instead of going through `cerberus.execute` will
   silently break the external `daemons/cerberus_watchdog/` link and
   trigger `pkill -f shadow_core`. The canary must keep running and must
   keep passing on every Cerberus-touching change.

---

## Closure backlog (intentional, not gaps)

Items that are documented behavior in the live system, not regressions
introduced by the cutover. Recorded so future redesigns know they exist by
choice.

5. **Eight creator-command escape hatches bypass Cerberus.** Routes at
   [orchestrator.py:1234-1315](../../../modules/shadow/orchestrator.py#L1234-L1315)
   for `proactive_control`, `training_pipeline`, `synthetic_generator`,
   `benchmark`, `embedding_eval`, `transcript_ingestor`, `snapshot_exporter`,
   and `generate` take a direct handler path that skips Steps 3-6 entirely
   — no plan, no Cerberus, no module dispatch. Plus `_fast_response`
   (text-only, no tool dispatch). These are intentional creator-command
   routes living in the fast-path classifier (design doc §3.2) which sits
   before the graph. The LangGraph cutover does not introduce or close
   these. A future fast-path re-design should know they're choice, not
   oversight.

6. **`TaskClassification.safety_flag` is informational, not a gate.** The
   field at [orchestrator.py:318](../../../modules/shadow/orchestrator.py#L318)
   carries the misleading comment "does Cerberus need to pre-screen?" but is
   never read as a guard. Cerberus runs on module presence
   (`"cerberus" in registry and status == ONLINE`), not on the flag. Do not
   introduce conditionals keyed on `safety_flag` in graph code. Renaming the
   field would clarify intent but touches enough sites to be its own
   cleanup.

---

## Carried from Step 2 (Grimoire)

7. **Async embeddings inside Grimoire — pre-existing live blocking.**
   `Grimoire._get_embedding` at
   [grimoire.py:626](../../../modules/grimoire/grimoire.py#L626) blocks on
   `requests.post` to Ollama. Six of Grimoire's nine tools call sync
   methods that hit this path; `GrimoireModule.execute` is `async def` but
   does not wrap them in `asyncio.to_thread`. The event loop blocks for the
   duration of each embedding call. The Grimoire sub-graph delegates to
   `execute` and therefore inherits the blocking — the spike's
   `asyncio.to_thread` wrap cannot be retrofitted at the sub-graph layer
   without either modifying `GrimoireModule` (violates the additive
   constraint) or duplicating dispatch (violates Option-A delegation, and
   does not actually unblock the loop — the `requests.post` still blocks,
   just on a worker thread). Real fix is making `_get_embedding` async
   (and the downstream `remember`/`recall` chain that calls it). Out of
   scope for the sub-graph migration steps; lands as its own Grimoire
   refactor.
   - The test
     `tests/test_grimoire_subgraph.py::test_grimoire_subgraph_inherits_live_blocking_for_sync_tools`
     pins the inherited behavior so the refactor knows what tightens.

---

## Carried from Step 1 (Router)

8. **Phantom "63/63 orchestrator sanity" gate — corrected.** The Session 50
   Step 3a working notes asserted the router/dispatcher build "validates
   262/262 Cerberus regression green and 63/63 orchestrator sanity green."
   There is **no 63-test orchestrator gate**. Verified counts (`grep -c` for
   `def test_` / `async def test_`): `tests/test_orchestrator.py` = 192,
   `tests/test_decision_loop.py` = 9 → **201** total. The orchestrator-untouched
   gate is the *green-tests-AND-import-isolation* rule, **not a fixed count**:
   `test_orchestrator.py` + `test_decision_loop.py` green (currently 201) AND
   `grep -rn 'modules.shadow.graph' modules/ main.py | grep -v 'modules/shadow/graph/'`
   → empty. The phantom figure was struck at source (the Step 3a notes) and in
   the promoted [cerberus-safety-gate.md](cerberus-safety-gate.md); recorded
   here so no future step re-imports "63/63."

9. **Concurrent-mutation hazard on `orchestrator._last_route`.** The router
   delegating node ([modules/shadow/graph/router_node.py](../../../modules/shadow/graph/router_node.py))
   bridges cross-invocation route memory by hydrating
   `orchestrator._last_route` from the checkpointed `state["last_route"]`
   before delegating to `_step2_classify`, then mirroring the live write back
   onto `orchestrator._last_route` (parity with
   [orchestrator.py:1201](../../../modules/shadow/orchestrator.py#L1201)).
   `_last_route` is a **shared instance attribute**. This is correct under
   sequential invocation, but under **concurrent node execution across distinct
   `thread_id`s** it becomes a cross-`thread_id` route-memory leak — invocation
   A hydrates the attr from thread A's checkpoint, invocation B overwrites it
   from thread B's, then A reads B's route. The per-thread `state["last_route"]`
   checkpoint is correct; the shared live attribute is the leak. The real fix —
   route `last_route` purely through graph state, i.e. make the contextual-
   reference read at [orchestrator.py:2173](../../../modules/shadow/orchestrator.py#L2173)
   consume `state["last_route"]` instead of `self._last_route` — requires
   touching `_fast_path_classify` and is therefore **blocked by the
   orchestrator-untouched constraint** of the additive router step. **Deferred
   to the parent-graph integration step**, which must close it deliberately
   (the additive node keeps the instance-attribute mutation in the meantime).
   - **Parent-graph step update (carried, not yet closed).** The parent graph
     ([modules/shadow/graph/parent.py](../../../modules/shadow/graph/parent.py))
     runs nodes **sequentially within a single `ainvoke`** — `dispatch` has
     in-degree 1, `plan` has in-degree 1, and the only branch points are the two
     *mutually exclusive* conditional gates, so one invocation walks one linear
     path with no intra-invocation race (asserted by
     `tests/test_parent_graph.py::test_item9_single_linear_path_per_invocation`).
     The residual hazard is **concurrent invocations across distinct `thread_id`s
     against one shared orchestrator instance**, which cannot bite pre-flip: no
     live caller invokes the graph yet, let alone concurrently. The real fix
     (route `last_route` purely through `state`, i.e.
     [orchestrator.py:2173](../../../modules/shadow/orchestrator.py#L2173) reads
     `state["last_route"]`) still requires touching `_fast_path_classify` and so
     **carries to the flip dispatch**, where `orchestrator.py` is intentionally
     edited. Confirmed-sequential-and-deferred, not band-aided.

10. **Retry self-edge node superseded by whole-loop delegation (S51b).** The
    first retry-graph commit drove its own attempt loop from `attempt_task`'s
    primitives (`get_strategy_for_attempt` / `_build_strategy_context` /
    `classify_failure` / `should_escalate`) across a conditional self-edge,
    bypassing [retry_engine.py:352](../../../modules/shadow/retry_engine.py#L352)
    entirely, and silently dropped 5 behaviors that live *inside* `attempt_task`:
    deterministic-failure early-exit
    ([retry_engine.py:476-489](../../../modules/shadow/retry_engine.py#L476-L489)),
    the fatigue counter
    ([:404-405](../../../modules/shadow/retry_engine.py#L404-L405) /
    [:413-414](../../../modules/shadow/retry_engine.py#L413-L414)), the Grimoire
    preflight ([:329-350](../../../modules/shadow/retry_engine.py#L329-L350)),
    progress notifications ([:502-503](../../../modules/shadow/retry_engine.py#L502-L503)),
    and `_record_session`
    ([:444](../../../modules/shadow/retry_engine.py#L444) /
    [:465](../../../modules/shadow/retry_engine.py#L465) /
    [:521](../../../modules/shadow/retry_engine.py#L521)). The 40
    `tests/test_retry_engine.py` tests call `attempt_task` directly, so they
    guarded the live loop, **not** the node's reimplemented driver — green
    tests over an untouched path. The pre-decision "retry = self-edge, rotation
    as data" assumed a per-attempt public primitive that does not exist;
    `attempt_task` owns the whole 12-attempt loop. **Superseded:** retry is now a
    single node delegating the whole `attempt_task` call to live code, forwarding
    the same `execute_fn` / `evaluate_fn` / `grimoire_search_fn` / `notify_fn`
    closures the live path builds at
    [orchestrator.py:4698-4709](../../../modules/shadow/orchestrator.py#L4698-L4709)
    — same posture as `dispatch_node` → `_step5_execute`. Rotation stays entirely
    inside the engine as data; the graph models no per-attempt topology.
    Delegation seam chosen at `attempt_task` (not the higher `_step5_with_retry`)
    because `_step5_with_retry` re-wraps `_step5_execute` (already
    `dispatch_node`'s) plus Apex escalation / decomposition concerns beyond the
    retry loop. 6th "looks governed but isn't" of the phase; **first caught
    pre-ship.**

---

## Parent-graph wiring (assembled; FLIP LANDED — merged to main @ e44f16e)

*(Header corrected S54, 2026-07-07: this section was written at wiring time,
pre-flip. The flip has since landed and merged to main @ `e44f16e` — see the
"FLIP LANDED" section below. Historical text preserved in past tense.)*

The parent graph is assembled and asserted at
[modules/shadow/graph/parent.py](../../../modules/shadow/graph/parent.py)
(`build_parent_graph` / `compile_parent_graph`): `START → router → routable_gate
→ plan → plan_gate → dispatch`, with `dormant` / `blocked` terminals. The two
load-bearing safety properties (Cerberus denial unreachable; dormant target
unreachable) are re-asserted **structurally** across the full graph in
[tests/test_parent_graph.py](../../../tests/test_parent_graph.py). At wiring
time the build did **not** flip the live path: `process_input` stayed
authoritative and nothing live imported the graph (the item-8 grep still ran
empty). The items below were the deliberate obligations the wiring left to the
flip dispatch — all since closed at the flip (items 9/11/12/13).

11. **New import-isolation invariant (supersedes item-8's grep AT FLIP, not
    now).** The pre-flip invariant — `grep -rn 'modules.shadow.graph' modules/
    main.py | grep -v 'modules/shadow/graph/'` → empty — still holds after the
    wiring dispatch (the assembler lives *inside* `graph/`). At flip it is
    intentionally broken; the invariant that replaces it is:
    > The live path imports the compiled parent graph from **exactly one entry
    > point** (`modules.shadow.graph.parent`); **no node imports a sibling node's
    > internals** (a node module imports only its delegation target +
    > `ShadowState` / `ToolResult`); and the orchestrator's `_step*` methods
    > remain the **delegated-to source of truth** (nodes reimplement none).

    The two mechanically-checkable clauses (single assembler entry point; no
    sibling-internal imports, parent.py the sole composition seam) are asserted
    now by [tests/test_graph_import_isolation.py](../../../tests/test_graph_import_isolation.py).
    The "live path imports from one entry point" clause activates at flip; its
    precondition (a single public assembler exists) is asserted now. The flip
    dispatch must wire the live caller through `parent` only — not scatter graph
    imports across the orchestrator.

12. **Retry + response (Step 6) legs carry to the flip.** The parent graph's
    approved branch wires the bare `dispatch` node (delegates `_step5_execute`).
    The **retry** wrap and the **response/Step-6** leg are NOT wired this
    dispatch: both need per-request closures / Step-3 context the orchestrator
    builds *inside* `_step5_with_retry`
    ([orchestrator.py:4515-4709](../../../modules/shadow/orchestrator.py#L4515-L4709))
    — `execute_fn` / `evaluate_fn` / `grimoire_search_fn` / `notify_fn` and the
    loaded context — which are not exposed without touching `orchestrator.py`.
    `make_retry_node` deliberately takes those closures as arguments
    ([retry_graph.py:54](../../../modules/shadow/graph/retry_graph.py#L54): "the
    orchestrator at cutover builds them"). Wiring them now would force either a
    **reimplemented driver** (the item-10 trap) or an orchestrator edit (a
    partial flip) — both out of scope. The flip dispatch exposes the closures
    (and Step-3 context) from live code and inserts `retry` between `plan_gate`'s
    approved branch and `response`. **Confirmed-deferred, not band-aided.**

13. **AsyncTaskQueue worker still dispatches outside the graph.** The background
    worker at
    [async_tasks.py:234-235](../../../modules/shadow/async_tasks.py#L234-L235)
    calls `module.execute(...)` directly (bypassing the graph, and therefore the
    Cerberus plan-gate). The design says the queue should **invoke the compiled
    graph per deferred task** (design §4 item 7), but rerouting it now would
    live-import `modules.shadow.graph` from a non-graph file — breaking the
    item-8 grep before the flip and changing live behavior (a partial flip). The
    parent graph is documented as the worker's future entry point; the reroute
    **carries to the flip dispatch**. **Confirmed-deferred, not band-aided.**

14. **Spec-wording divergence: `_step4_plan` is not "a single `cerberus_approved`
    write."** Recon for the new `plan_node` enumerated the full side-effect
    surface of `_step4_plan`
    ([orchestrator.py:3850-4483](../../../modules/shadow/orchestrator.py#L3850-L4483)):
    a per-step Cerberus `safety_check` loop (whose transitive `send_heartbeat()`
    at [cerberus.py:238](../../../modules/cerberus/cerberus.py#L238) writes the
    daemon heartbeat), the `cerberus_approved` verdict, and `_background` param
    injection ([:4477-4481](../../../modules/shadow/orchestrator.py#L4477-L4481)).
    `plan_node` therefore delegates the **whole** method (same posture as
    `dispatch_node` / `retry`); a thinner "set the gate flag" reconstruction
    would have silently dropped the heartbeat and the `_background` flag. Pinned
    by the side-effect tests in
    [tests/test_parent_graph.py](../../../tests/test_parent_graph.py). Recorded
    so no future step re-imports the "single write site" framing.

---

## FLIP LANDED — import-isolation transition (item 11 closed)

The flip is wired (`process_input` drives the compiled parent graph via segmented
invoke; retry + response legs in; items 9/11/12/13 closed). The pre-flip
import-isolation grep
(`grep -rn 'modules.shadow.graph' modules/ main.py | grep -v 'modules/shadow/graph/'`
→ empty) is now **intentionally non-empty and superseded** by the item-11
invariant:

> The live path imports the compiled parent graph from **exactly one entry
> point** — `modules.shadow.graph.parent` (`orchestrator._ensure_graph` /
> `run_deferred_through_graph` import `build_parent_graph` from there, and
> nowhere else). **No node imports a sibling node's internals** (a node module
> imports only its delegation target + `ShadowState` / `ToolResult`;
> `parent.py` is the sole composition seam). The orchestrator's `_step*` methods
> remain the **delegated-to source of truth** — nodes reimplement none.

Mechanically: `async_tasks.py` (a non-graph file) does **not** import
`graph.parent`; it delegates to `Orchestrator.run_deferred_through_graph`, so the
single-entry-point clause holds. `tests/test_graph_import_isolation.py` continues
to assert the two mechanical clauses (single assembler entry point; no
sibling-internal imports). The grep-empty rule is retired; cite this entry, not
the grep, going forward.

---

## Reconstructed appends (S51e / S52) — landed S54

> **Items 16–23 reconstructed 2026-07-07 (S54)** — drafted in Sessions 51e
> (16–19) and 52 (20–23), never committed; they existed only in session reports
> and Master Plan v9 §18, from which they are reconstructed here. **No item 15
> was ever drafted** (S51e's append began at 16); the number is retired unused
> to preserve append-only numbering. Rule going forward: **an append is not
> done until `git log` shows it.**

15. **Retired unused** — see reconstruction note above. Never assigned.

16. **memtest86+ overnight — unrun.** Required before trusting Citadel with
    long unattended autonomous GPU runs; does not block supervised work.
    (Hardware, S51e)

17. **Freeze root cause not isolated.** The S51e recovery changed the NVIDIA
    driver (580→595) AND EXPO (on→off) together; the validated-stable config
    (EXPO-off / 3600 MT/s / driver 595) is proven by the 40-min soak but the
    single root cause is not isolated. Relevant only if EXPO-5600 bandwidth is
    wanted back. (Hardware, S51e)

18. **8TB SATA drive offline.** All SATA ports link-down; physical cable
    reseat needed. Blocks automated nightly backups (memory DB, training
    data, LoRA adapters → HDD + encrypted offsite). (Hardware, S51e)

19. **Flip re-dispatch scope — RESOLVED S52** via enumerated-set ruling D1.
    Recorded for numbering continuity; listed among v9 §18's resolved
    landmarks. (S51e)

20. **Brittle scorer `required_keywords`** (`benchmark_suite.py:336-341`):
    single-keyword exact-substring rubrics under-credit correct answers and
    manufacture phantom regressions — the 0.8424 baseline's landscaping 1.00
    was lucky-phrasing on exactly this mechanism. Fix before future benchmark
    comparisons. Low-risk early task. (Benchmark, S52)

21. **Populated-store live median-of-N floor.** The current honest floor is
    empty-store median-of-N; a populated-store distribution is a precision
    refinement, not a blocker. (Benchmark, S52)

22. **Annotate `benchmark_2026-06-18.json` as a high single sample** so it is
    never silently reused as a floor. — **CLOSED S54** (F-8: annotation
    embedded in the JSON itself; the six 06-28 clean-arm files and two
    populated-store files committed with arm/store/basis labels). (Benchmark,
    S52)

23. **Reconcile Claude Code's self-initiated memory writes**
    (`track-b-flip-wired.md`, `MEMORY.md`) against the S52 report wording. —
    **CLOSED S54** (memory rewritten to merged state; the S52 floor figures
    were independently verified by recomputation as the excl-memory basis).
    (Hygiene, S52)

## S54 appends (post-merge audit, 2026-07-07)

*Ledger tail verified at 23 before this append.*

24. **v9 ERRATA (S54 post-merge audit).** Corrections to Master Plan v9,
    measured against the repo at `e44f16e`:
    - Apex cumulative cost **$1.35** across 84 escalations
      (`data/apex_escalation.db`, SUM(cost_usd)), not ~$0.03.
    - PostgreSQL **16.14**, not 16.13.
    - Benchmark suite has **13 categories**, not 10 (75 tasks confirmed).
    - **"511 targeted tests" STRUCK** per phantom-count doctrine (v9 §22.5):
      no source file list exists and the figure is not reconstructable (flip
      gate = 402 exact; track-b test files collect 131; 402+131 = 533).
    - "16 misc training examples": no matching artifact found (in-repo
      `training_data/` holds only `apex_sessions/`, 217 JSONL lines; curated
      sets live in `~/dev/shadow-training-data`).
    - Line-cite drift: the `state["last_route"]` read is
      `router_node.py:123` (not orchestrator.py:2196); `_build_retry_closures`
      def at :4720 (not :4716); `_resolve_retry_outcome` def at :4927 (not
      :4923).
    - §15's flip/live floor figures (0.8360 / 0.8340, SDs 0.0074 / 0.0157)
      are the **excl-memory_retrieval basis**; on the full basis the sign
      inverts (flip 0.8327 vs live 0.8361, −0.0034) — still within 1 SD,
      EQUIVALENT verdict unchanged. The basis label was omitted in v9's table.
    - §14/§7 "ESV 100% ingested (18,610 entries)" was false at compile time:
      no ESV tables or collections exist on Citadel (`memories` = 309 rows;
      Chroma has only `shadow_memories`); `esv_ingestion.py` carried Windows
      `C:\Shadow` paths and can never have run here (see items 36 and F-5).

25. **`safety_flag` checkpoint divergence** (orchestrator.py, injection-warn
    application after graph segment 1): the caller mutates the deserialized
    `classification` copy; the checkpointed graph state keeps `False`.
    Annotated as a trap in-code this session (F-6); harmless today — item 6
    pins the flag as informational, nothing in graph code reads it. Real fix
    (write the flag back via `aupdate_state`) deferred. (S54)

26. **Graph-segment exceptions bypass `_step7_log`.** A mid-segment graph
    failure exits through the generic outer handler with no interaction log.
    Confirm pre-flip parity first (the old loop may have had the same gap);
    then fix deliberately. (S54)

27. **Worker fallback silently bypasses Cerberus** (`async_tasks.py`,
    `orchestrator is None` branch → direct `module.execute`). Correct today
    because the worker is always wired with an orchestrator, but a wiring
    mistake would silently reopen the pre-item-13 bypass. Make it fail loud.
    (S54)

28. **Pre-flip remnant branches in `process_input`** (engine-None confab
    metadata + engine-None confidence-retry): reachable only when the
    RetryEngine import fails. Review for removal or explicit degraded-mode
    support. (S54)

29. **`context` channel is replace-not-reducer** (`skeleton.py`): safe under
    the current 3-segment protocol; fragile to future segment insertions
    between `aupdate_state` and the plan segment. Document or convert
    deliberately. (S54)

30. **`config.yaml` lists morpheus in `load_on_startup`** while `main.py`
    gates instantiation on `config.morpheus.enabled` — contradictory-reading
    config. Drop the list entry or comment the gate. (S54)

31. **README badge/count fixes**: 13-modules badge, "tools-138",
    "Python 3.14+", "1,422 tests" — all stale. (S54)

32. **`parent.py` + `retry_graph.py` docstring drift**: pre-flip "no caller
    enters this graph yet" / "imported by exactly one caller (tests)" claims,
    plus stale orchestrator line cites. (S54)

33. **`graphify-out/GRAPH_REPORT.md` regeneration** — dated 2026-04-28,
    predates `modules/shadow/graph/` entirely; CLAUDE.md marks it
    load-bearing for multi-file changes. (S54)

34. **`langgraph-cutover-design.md` status line** still reads "Design +
    spike"; the cutover is merged. (S54)

35. **Graph scaffolding prune — KEEP for now.** Nine production-orphaned
    leaf/subgraph node files, the dispatch/retry standalone builders, and the
    `_step5_with_retry` reference are retained deliberately. Trigger:
    revisit after dogfooding validates the flip under real load; any prune
    must retire the ~45 pinning tests together with the files. (S54)

36. **ESV full ingestion run** (target 18,610 entries: 2,392 pericopes +
    16,218 study notes → SQLite + Chroma). Start-and-walk-away item, after
    the F-5 path port. Note: `config/ethical_topics.yaml` is **gitignored by
    design** (Scripture-derived content stays out of the public repo) — it
    must be deployed per-machine from
    `~/dev/shadow-training-data/ethics/ethical_topics.yaml` (see F-1 for the
    schema transform). (S54)

37. **On-disk AsyncSqliteSaver decision** — follow-on to the F-2 per-request
    checkpoint cleanup: decide `:memory:` vs file-backed checkpoint DB
    (crash-resume semantics vs zero-persistence simplicity). (S54)

38. **`modules/omen/test_gate.py:24,60` `Test*` class rename** to silence the
    PytestCollectionWarnings (`TestResult` dataclass + `TestGate` — pytest
    tries to collect them via `tests/test_test_gate.py`). (S54)
