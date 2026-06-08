# Grimoire LangGraph Spike

Phase B / Track B investigation. Proves that Grimoire works as a LangGraph
sub-graph before the cutover prompt commits to the full migration.

**Not wired into the live orchestrator.** Importable only under the
`spikes.langgraph_grimoire` namespace. Writes only to test temp dirs.

## What this proves

| Proof | Where |
|---|---|
| **a.** store/query round-trip through compiled graph | `tests/test_langgraph_spike.py::test_proof_a_round_trip` (`run_spike.py` end-to-end) |
| **b.** pydantic config singleton works inside graph nodes | `tests/test_langgraph_spike.py::test_proof_b_config_singleton` |
| **c.** SQLite checkpointing persists across process restarts | `tests/test_langgraph_spike.py::test_proof_c_process_restart` (uses `proof_checkpoint.py` via `subprocess`) |
| **d.** `observed_span` parent/child nesting inside graph nodes | `tests/test_langgraph_spike.py::test_proof_d_observed_span_nesting` |
| **e.** `ToolResult` passes through graph state unmodified | `tests/test_langgraph_spike.py::test_proof_e_toolresult_passthrough` |
| **f.** Async execution compatible with Grimoire's async surface | `tests/test_langgraph_spike.py::test_proof_f_async_compat` |

## Running

### Tests (no live stack required)

```bash
source ~/dev/Shadow/shadow_env/bin/activate
pytest tests/test_langgraph_spike.py -v
```

Proof (a) runs against the real Grimoire if Ollama + `nomic-embed-text` are
reachable; otherwise it skips with a message. Proofs (b)–(f) always run.

### End-to-end script (requires Ollama on Citadel)

```bash
source ~/dev/Shadow/shadow_env/bin/activate
python -m spikes.langgraph_grimoire.run_spike
```

Stores a sentence about Citadel's hardware, recalls it via semantic search,
prints the round-trip in human-readable form.

### Cross-process checkpoint proof (manual)

```bash
DB=/tmp/spike-cp.db
rm -f "$DB"
python -m spikes.langgraph_grimoire.proof_checkpoint --phase=write   --db "$DB" --thread t1
python -m spikes.langgraph_grimoire.proof_checkpoint --phase=resume  --db "$DB" --thread t1
```

The second invocation is a fresh Python process. It re-instantiates the
graph against the same checkpoint file and resumes execution from where
the first process was interrupted.

## Design notes

- Graph state uses `Annotated[list[ToolResult], add]` so retries / multi-tool
  plans can append without overwriting. This is the pattern the cutover
  should adopt for the real orchestrator's `tool_results` field.
- The sync variant (`build_graph`) is what fits Grimoire's actual surface;
  the async variant (`build_async_graph`) wraps calls in `asyncio.to_thread`
  and is the recommended cutover pattern given Grimoire's blocking
  `requests.post` embeddings call.
- `observed_span` is imported from `modules.shadow.observability` and used
  unchanged — it degrades to no-ops when Langfuse is unreachable.
- `InMemoryGrimoireFake` lets the spike (and tests) exercise the graph
  topology without needing Ollama. The real `Grimoire` class is only used
  by `run_spike.py` and the optional proof-(a) test.

## What this spike does NOT prove

- Cerberus safety gating inside a graph (separate sub-graph; later spike).
- The fast-path classifier as a pre-graph short-circuit (design doc only).
- Retry-engine wrapping as a sub-graph (later spike).
- Postgres checkpointer swap (Track A, after PostgreSQL migration).
- Behavioral equivalence of the full ~397-test routing/orchestrator gate.

See `docs/phase-b/track-b/langgraph-cutover-design.md` for the topology
proposal, migration sequence, and behavioral-contract checklist.
