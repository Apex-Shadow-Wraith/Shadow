"""Item 11 — benchmark model provenance.

The benchmark run record must stamp the real generation model (e.g.
``gemma4:26b``), not ``"unknown"``. Before the fix ``self._model_name`` was never
set, so the benchmark config fell back to ``"unknown"`` (orchestrator.py).
"""

from __future__ import annotations

from pathlib import Path

from tests.test_orchestrator import TEST_CONFIG
from tests.test_parent_graph import _make_orch


def test_model_name_is_stamped_not_unknown(tmp_path: Path) -> None:
    """``_model_name`` resolves to the configured generation model, not unknown."""
    orch = _make_orch(tmp_path)
    assert orch._model_name == TEST_CONFIG["models"]["smart_brain"]["name"]
    assert orch._model_name != "unknown"
    # This is exactly the value the benchmark command stamps into the run record.
    import_config = {"model_name": getattr(orch, "_model_name", "unknown")}
    assert import_config["model_name"] == orch._smart_brain
