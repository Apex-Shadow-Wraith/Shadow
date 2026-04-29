"""Dump the internal-registry tool inventory to JSON.

Used by Phase A merges to produce pre/post snapshots that prove zero
tool loss (or explicit drops). Instantiates every known module class
with an empty config, calls `get_tools()`, and writes the result as
`{ module_name: [tool_schema, ...] }` keyed JSON.

Does NOT call `initialize()` — `get_tools()` must return static metadata
without side effects. Any module that violates that is a separate bug.

Usage:
    python scripts/dump_tools.py docs/phase-a/void/pre_merge_tools.json
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

# Script lives at scripts/dump_tools.py; ensure repo root is on sys.path
# so `import modules.*` works regardless of invocation cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# (codename, "module.path", "ClassName")
# Phase A consolidation: Sentinel → Cerberus, Cipher → Omen, Void → daemon.
# Only the active modules remain — sentinel/cipher/void entries removed.
KNOWN_MODULES: list[tuple[str, str, str]] = [
    ("apex", "modules.apex.apex", "Apex"),
    ("cerberus", "modules.cerberus.cerberus", "Cerberus"),
    ("grimoire", "modules.grimoire.grimoire_module", "GrimoireModule"),
    ("harbinger", "modules.harbinger.harbinger", "Harbinger"),
    ("morpheus", "modules.morpheus.morpheus", "Morpheus"),
    ("nova", "modules.nova.nova", "Nova"),
    ("omen", "modules.omen.omen", "Omen"),
    ("reaper", "modules.reaper.reaper_module", "ReaperModule"),
    ("shadow", "modules.shadow.shadow_module", "ShadowModule"),
    ("wraith", "modules.wraith.wraith", "Wraith"),
]


def _instantiate(cls: Any, cls_name: str) -> Any:
    """Try a few call signatures; modules vary on typed-settings migration.

    ShadowModule needs a dummy registry as its second positional arg.
    Empty-dict goes first so modules like Cerberus (which calls `.get()`
    on self._config inside __init__-adjacent paths) don't NoneType-crash.
    """
    if cls_name == "ShadowModule":
        # Fabricate a minimal registry so get_tools() can be called.
        from modules.base import ModuleRegistry
        return cls({}, ModuleRegistry())

    for args in (({},), (None,), ()):
        try:
            return cls(*args)
        except TypeError:
            continue
    return cls()


def main(out_path: str) -> int:
    inventory: dict[str, list[dict[str, Any]]] = {}
    for codename, mod_path, cls_name in KNOWN_MODULES:
        try:
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, cls_name)
            instance = _instantiate(cls, cls_name)
            tools = instance.get_tools()
        except Exception as e:
            print(f"  skip {codename}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        inventory[codename] = tools

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, sort_keys=True)
        f.write("\n")

    total = sum(len(v) for v in inventory.values())
    print(f"Wrote {out_path}: {len(inventory)} modules, {total} tools")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/dump_tools.py <output.json>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
