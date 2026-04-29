"""Phase A Cipher→Omen tool-inventory generator.

Dumps two JSON snapshots used to prove zero capability loss:

  docs/phase-a/cipher-omen/tool_inventory_pre.json
      Pre-merge: full schemas of Cipher.get_tools() + the original
      40 Omen tools (the latter derived by subtracting the 7
      absorbed Cipher tool names from the post-merge
      Omen.get_tools()). Total: 47 entries.

  docs/phase-a/cipher-omen/tool_inventory_post.json
      Post-merge: Omen.get_tools() — 47 entries (40 original + 7
      absorbed Cipher tools, zero renames, zero dedup).

The accompanying tool_diff.md is hand-written; this script only
generates the two JSON snapshots that the diff document references.

Run from the repo root:

    python scripts/phase_a_cipher_omen_inventory.py

Idempotent — overwrites the JSON files if they already exist.
Requires the Cipher module to still be on disk (i.e. before the
commit-7 deletion). After commit 7 the Cipher-side dump is no
longer reproducible from the working tree; the JSON snapshots
checked in by commit 6 are the historical record.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "phase-a" / "cipher-omen"
PRE_PATH = DOCS_DIR / "tool_inventory_pre.json"
POST_PATH = DOCS_DIR / "tool_inventory_post.json"

# The 7 Cipher tool names absorbed into Omen in Phase A.  Used to derive
# pre-merge Omen tools from the post-merge Omen.get_tools() output (i.e.
# pre-merge Omen = post-merge Omen minus these names).
ABSORBED_CIPHER_TOOL_NAMES = {
    "calculate",
    "unit_convert",
    "date_math",
    "percentage",
    "financial",
    "statistics",
    "logic_check",
}


async def _build_inventory() -> tuple[list[dict], list[dict]]:
    """Return (pre_inventory, post_inventory) tool-schema lists."""
    sys.path.insert(0, str(REPO_ROOT))

    from modules.cipher.cipher import Cipher
    from modules.omen.omen import Omen

    cipher_tools = Cipher().get_tools()

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        omen = Omen({
            "project_root": str(td_path),
            "db_path": str(td_path / "omen_code.db"),
            "sandbox_root": str(td_path / "sandbox"),
            "scratchpad_dir": str(td_path / "scratchpads"),
            "benchmarks_dir": str(td_path / "benchmarks"),
            "samples_dir": str(td_path / "samples"),
        })
        await omen.initialize()
        post_tools = omen.get_tools()
        await omen.shutdown()

    # Pre-merge Omen = post-merge Omen minus the absorbed surface.
    pre_omen_tools = [
        t for t in post_tools if t["name"] not in ABSORBED_CIPHER_TOOL_NAMES
    ]
    pre_inventory = cipher_tools + pre_omen_tools
    return pre_inventory, post_tools


def main() -> int:
    pre, post = asyncio.run(_build_inventory())

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    PRE_PATH.write_text(json.dumps(pre, indent=2, sort_keys=True) + "\n")
    POST_PATH.write_text(json.dumps(post, indent=2, sort_keys=True) + "\n")

    print(f"Wrote {PRE_PATH.relative_to(REPO_ROOT)} ({len(pre)} entries)")
    print(f"Wrote {POST_PATH.relative_to(REPO_ROOT)} ({len(post)} entries)")

    pre_names = {t["name"] for t in pre}
    post_names = {t["name"] for t in post}
    missing = pre_names - post_names
    extra = post_names - pre_names
    print(f"Pre names: {len(pre_names)}  Post names: {len(post_names)}")
    print(f"Missing in post (lost on merge): {sorted(missing) or 'none'}")
    print(f"Extra in post (added on merge): {sorted(extra) or 'none'}")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
