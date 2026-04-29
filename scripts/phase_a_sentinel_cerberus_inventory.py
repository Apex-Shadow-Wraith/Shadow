"""Phase A Sentinel→Cerberus tool-inventory generator.

Dumps two JSON snapshots used to prove zero capability loss:

  docs/phase-a/sentinel-cerberus/tool_inventory_pre.json
      Pre-merge: full schemas of Sentinel.get_tools() + the original
      15 Cerberus tools (the latter derived by subtracting the 24
      absorbed names from the post-merge Cerberus.get_tools()).
      Total: 39 entries.

  docs/phase-a/sentinel-cerberus/tool_inventory_post.json
      Post-merge: Cerberus.get_tools() — 39 entries (15 original + 24
      absorbed Sentinel tools, zero renames, zero dedup).

The accompanying tool_diff.md is hand-written; this script only
generates the two JSON snapshots that the diff document references.

Run from the repo root:

    python scripts/phase_a_sentinel_cerberus_inventory.py

Idempotent — overwrites the JSON files if they already exist.
Requires the Sentinel module to still be on disk (i.e. before the
commit-11 deletion). After commit 11 the Sentinel-side dump is no
longer reproducible from the working tree; the JSON snapshots
checked in by commit 10 are the historical record.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "phase-a" / "sentinel-cerberus"
PRE_PATH = DOCS_DIR / "tool_inventory_pre.json"
POST_PATH = DOCS_DIR / "tool_inventory_post.json"


async def _build_inventory() -> tuple[list[dict], list[dict]]:
    """Return (pre_inventory, post_inventory) tool-schema lists."""
    sys.path.insert(0, str(REPO_ROOT))

    from modules.cerberus.cerberus import Cerberus
    from modules.cerberus.security import SECURITY_TOOLS
    from modules.sentinel.sentinel import Sentinel

    sentinel_tools = Sentinel().get_tools()

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        limits_path = td_path / "cerberus_limits.yaml"
        limits_path.write_text(
            "hard_limits: {}\n"
            "permission_tiers: {}\n"
            "approval_required_tools: []\n"
            "autonomous_tools: []\n"
            "hooks:\n"
            "  pre_tool: {deny: [], modify: []}\n"
            "  post_tool: {flag: []}\n"
        )
        cerberus = Cerberus({
            "limits_file": str(limits_path),
            "db_path": str(td_path / "audit.db"),
            "snapshot_dir": str(td_path / "snap"),
            "security": {
                "baseline_file": str(td_path / "baseline.json"),
                "quarantine_dir": str(td_path / "quarantine"),
            },
        })
        await cerberus.initialize()
        post_tools = cerberus.get_tools()
        await cerberus.shutdown()

    # Pre-merge Cerberus = post-merge Cerberus minus the absorbed surface.
    pre_cerberus_tools = [t for t in post_tools if t["name"] not in SECURITY_TOOLS]
    pre_inventory = sentinel_tools + pre_cerberus_tools
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
