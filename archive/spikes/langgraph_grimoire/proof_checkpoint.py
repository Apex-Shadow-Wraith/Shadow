"""Cross-process checkpoint resume proof.

Demonstrates that LangGraph's ``SqliteSaver`` truly persists graph state to
disk and that a fresh Python process can resume execution from the
checkpoint left by a prior process.

Usage::

    # Process 1: runs through the store node, interrupts before search.
    python -m spikes.langgraph_grimoire.proof_checkpoint --phase=write \\
        --db /tmp/spike-cp.db --thread t1

    # Process 2 (new Python process): resumes from the checkpoint.
    python -m spikes.langgraph_grimoire.proof_checkpoint --phase=resume \\
        --db /tmp/spike-cp.db --thread t1

Uses the in-memory fake Grimoire so this proof does not require Ollama —
the point is checkpoint persistence, not Grimoire correctness.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from spikes.langgraph_grimoire.graph import InMemoryGrimoireFake, build_graph


SENTINEL_CONTENT = "checkpoint-spike: phase-1 wrote this; phase-2 must recall it"
SENTINEL_QUERY = "checkpoint-spike phase"


def run_write_phase(db_path: str, thread_id: str) -> int:
    fake = InMemoryGrimoireFake()
    builder = build_graph(
        store_fn=lambda c, _m: fake.remember(c),
        recall_fn=lambda q, n: fake.recall(q, n),
    )
    with SqliteSaver.from_conn_string(db_path) as saver:
        graph = builder.compile(checkpointer=saver, interrupt_after=["store"])
        config = {"configurable": {"thread_id": thread_id}}
        result = graph.invoke(
            {"content": SENTINEL_CONTENT, "query": SENTINEL_QUERY},
            config=config,
        )
        snapshot = graph.get_state(config)
        print(f"[write] memory_id={result.get('memory_id')}")
        print(f"[write] interrupt next={snapshot.next}")
        print(f"[write] checkpoint file: {Path(db_path).stat().st_size} bytes")
        if snapshot.next != ("search",):
            print(f"[write] FAIL: expected interrupt before 'search', got {snapshot.next}")
            return 1
    print("[write] OK — interrupted after store, checkpoint persisted")
    return 0


def run_resume_phase(db_path: str, thread_id: str) -> int:
    # NB: the in-memory fake's _store is empty in this fresh process. The
    # checkpoint persists graph STATE (memory_id, tool_results, etc.); it
    # does NOT persist Grimoire's underlying store. For the resume proof we
    # care that the graph resumes from the search node with the prior
    # memory_id intact in state — not that recall finds the sentinel (the
    # real Grimoire on Citadel would, since its SQLite/Chroma files persist
    # independently of the checkpointer).
    fake = InMemoryGrimoireFake()
    fake.remember(SENTINEL_CONTENT)  # simulate Grimoire persistence

    builder = build_graph(
        store_fn=lambda c, _m: fake.remember(c),
        recall_fn=lambda q, n: fake.recall(q, n),
    )
    with SqliteSaver.from_conn_string(db_path) as saver:
        graph = builder.compile(checkpointer=saver)
        config = {"configurable": {"thread_id": thread_id}}

        snapshot_before = graph.get_state(config)
        print(f"[resume] checkpoint values before resume: keys={list(snapshot_before.values.keys())}")
        print(f"[resume] next node to run: {snapshot_before.next}")
        prior_memory_id = snapshot_before.values.get("memory_id")
        print(f"[resume] memory_id from checkpoint: {prior_memory_id}")
        if not prior_memory_id:
            print("[resume] FAIL: no memory_id in checkpoint — write phase didn't persist")
            return 1
        if snapshot_before.next != ("search",):
            print(f"[resume] FAIL: expected next=('search',), got {snapshot_before.next}")
            return 1

        result = graph.invoke(None, config=config)
        print(f"[resume] post-resume memory_id={result.get('memory_id')}")
        print(f"[resume] recall hits={len(result.get('recall', []))}")
        if result.get("memory_id") != prior_memory_id:
            print("[resume] FAIL: memory_id changed across resume")
            return 1
    print("[resume] OK — resumed from checkpoint, state intact")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["write", "resume"], required=True)
    parser.add_argument("--db", required=True, help="SqliteSaver checkpoint DB path")
    parser.add_argument("--thread", default="proof-checkpoint", help="thread_id")
    args = parser.parse_args()

    if args.phase == "write":
        return run_write_phase(args.db, args.thread)
    return run_resume_phase(args.db, args.thread)


if __name__ == "__main__":
    sys.exit(main())
