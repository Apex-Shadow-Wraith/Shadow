"""End-to-end spike runner: real Grimoire (Ollama embeddings) + LangGraph.

Run from the repo root with the venv active:

    source ~/dev/Shadow/shadow_env/bin/activate
    python -m spikes.langgraph_grimoire.run_spike

Requires Ollama at http://localhost:11434 with ``nomic-embed-text`` loaded.
Writes only to a tempdir — does not touch the live ``data/`` paths.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from modules.grimoire.grimoire import Grimoire
from spikes.langgraph_grimoire.graph import build_graph


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]

    with tempfile.TemporaryDirectory(prefix="spike-grimoire-") as td:
        td_path = Path(td)
        db_path = td_path / "spike_memory.db"
        vec_path = td_path / "spike_vectors"
        cp_path = td_path / "checkpoints.db"
        vec_path.mkdir(parents=True, exist_ok=True)

        print(f"[spike] tempdir: {td}")
        print(f"[spike] grimoire db: {db_path}")
        print(f"[spike] vectors: {vec_path}")
        print(f"[spike] checkpoints: {cp_path}")

        grimoire = Grimoire(db_path=str(db_path), vector_path=str(vec_path))
        try:
            builder = build_graph(
                store_fn=lambda c, _m: grimoire.remember(c),
                recall_fn=lambda q, n: grimoire.recall(q, n_results=n),
            )
            with SqliteSaver.from_conn_string(str(cp_path)) as saver:
                graph = builder.compile(checkpointer=saver)
                config = {"configurable": {"thread_id": "spike-run-001"}}

                result = graph.invoke(
                    {
                        "content": (
                            "Project Shadow runs on Citadel, an Ubuntu 24.04 box "
                            "with an RTX 5090 and 128 GB of DDR5."
                        ),
                        "query": "what hardware does Shadow run on?",
                    },
                    config=config,
                )

                print()
                print(f"[spike] stored memory_id: {result.get('memory_id')}")
                print(f"[spike] recall hits: {len(result.get('recall', []))}")
                for i, hit in enumerate(result.get("recall", [])[:3]):
                    print(
                        f"[spike]   #{i + 1} relevance={hit.get('relevance'):.3f} "
                        f"trust={hit.get('trust_level')} content={hit.get('content')[:80]!r}"
                    )
                print(f"[spike] tool_results: {len(result.get('tool_results', []))}")
                for tr in result.get("tool_results", []):
                    print(
                        f"[spike]   {tr.tool_name} success={tr.success} "
                        f"latency_ms={tr.execution_time_ms:.1f}"
                    )

                snapshot = graph.get_state(config)
                print(f"[spike] final checkpoint next={snapshot.next}")
                print(f"[spike] cp file size: {cp_path.stat().st_size} bytes")
        finally:
            grimoire.close()

    print("[spike] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
