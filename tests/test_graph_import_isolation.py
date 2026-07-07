"""Phase B / Track B — the post-flip import-isolation invariant.

The pre-flip invariant was "the live path imports nothing from
``modules.shadow.graph``" (``cutover-backlog.md`` item 8: ``grep -rn
'modules.shadow.graph' modules/ main.py | grep -v 'modules/shadow/graph/'`` →
empty). That grep still holds during this wiring dispatch and is checked
separately. The flip will intentionally break it — so this module defines and
asserts the invariant that REPLACES it at flip:

    The live path imports the compiled parent graph from exactly ONE entry point
    (``modules.shadow.graph.parent``); NO node imports a sibling node's
    internals (a node module imports only its delegation target +
    ``ShadowState`` / ``ToolResult``); and the orchestrator's ``_step*`` methods
    remain the delegated-to source of truth.

Two clauses are mechanically checkable now and are asserted here:

* **Single entry point.** ``build_parent_graph`` / ``compile_parent_graph`` are
  defined in exactly one module (``parent``) — the sole assembler.
* **No sibling-internal imports.** Every node / sub-graph module imports across
  the package only ``skeleton`` (for ``ShadowState``). The parent assembler is
  the one exempt composition point — it is *supposed* to import the siblings it
  wires.

The "live path imports from exactly one entry point" clause activates at flip
(when ``process_input`` / the async worker import ``parent``); its precondition —
that a single public assembler exists — is asserted here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import modules.shadow.graph as graph_pkg

# The package directory on disk.
_PKG_DIR = Path(graph_pkg.__file__).parent

# Modules exempt from the "no sibling import" rule:
# - ``parent``: the sole assembler / composition point (imports siblings by design).
# - ``skeleton``: shared state schema (the one allowed cross-package import target).
# - ``serde``: shared checkpoint serde (no nodes).
# - ``__init__``: the package facade (re-exports everything).
_ASSEMBLER = "parent"
_SHARED = {"skeleton", "serde"}
_FACADE = "__init__"

# The one cross-package import target a node module may name.
_ALLOWED_SIBLING_IMPORT = "skeleton"


def _graph_module_files() -> list[Path]:
    return sorted(p for p in _PKG_DIR.glob("*.py"))


def _sibling_imports(source: str) -> set[str]:
    """Return the set of sibling ``modules.shadow.graph.X`` modules ``source``
    imports (the bare ``X`` names), via either ``from ... import`` or ``import``.
    """
    tree = ast.parse(source)
    siblings: set[str] = set()
    prefix = "modules.shadow.graph"
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == prefix:
                # ``from modules.shadow.graph import X`` — names are siblings.
                for alias in node.names:
                    siblings.add(alias.name)
            elif mod.startswith(prefix + "."):
                siblings.add(mod[len(prefix) + 1 :].split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(prefix + "."):
                    siblings.add(alias.name[len(prefix) + 1 :].split(".")[0])
    return siblings


def test_single_parent_assembler_entry_point() -> None:
    """``build_parent_graph`` / ``compile_parent_graph`` live in exactly one module."""
    definers: list[str] = []
    for path in _graph_module_files():
        if path.stem == _FACADE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            n.name
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if {"build_parent_graph", "compile_parent_graph"} & names:
            definers.append(path.stem)

    assert definers == [_ASSEMBLER], (
        f"the parent assembler must be the single entry point; found definers "
        f"{definers}"
    )


def test_no_node_module_imports_a_sibling_node() -> None:
    """No node / sub-graph module imports across the package except ``skeleton``.

    The parent assembler is exempt — it is the one composition point and is
    expected to import the siblings it wires.
    """
    violations: dict[str, set[str]] = {}
    for path in _graph_module_files():
        stem = path.stem
        if stem in _SHARED or stem == _FACADE or stem == _ASSEMBLER:
            continue
        siblings = _sibling_imports(path.read_text(encoding="utf-8"))
        bad = siblings - {_ALLOWED_SIBLING_IMPORT}
        if bad:
            violations[stem] = bad

    assert not violations, (
        "node/sub-graph modules may import only 'skeleton' across the package "
        f"(parent.py is the sole composition point); violations: {violations}"
    )


def test_parent_assembler_is_the_composition_point() -> None:
    """The assembler DOES import siblings — confirming it is the composition seam.

    Guards against the invariant decaying into "nothing imports anything" (which a
    broken/empty parent would also satisfy): the assembler must actually wire the
    router, plan, gate, and dispatch fragments.
    """
    source = (_PKG_DIR / f"{_ASSEMBLER}.py").read_text(encoding="utf-8")
    imported = _sibling_imports(source)
    assert {"router_node", "plan_node", "dispatch_graph", "morpheus_gate"} <= imported, (
        f"parent.py must compose the node fragments; imports siblings: {imported}"
    )
