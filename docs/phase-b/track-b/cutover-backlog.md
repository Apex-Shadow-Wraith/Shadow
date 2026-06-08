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
