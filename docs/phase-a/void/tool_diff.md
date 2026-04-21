# Phase A — Void Demotion Tool-Inventory Diff

## Summary

|                | Pre-merge | Post-merge | Delta       |
|----------------|----------:|-----------:|------------:|
| Modules        | 12        | 11         | -1 (void)   |
| Tools          | 151       | 145        | -6 (void's) |
| Tools added    | 0         | —          | —           |
| Tools renamed  | 0         | —          | —           |

Both snapshots captured with `scripts/dump_tools.py`, which instantiates
every known module class with an empty config and serializes each
module's `get_tools()` output. Apex is skipped in both snapshots
because it refuses to instantiate without an API key and `dry_run=False`
(consistent across pre/post, so the diff is unaffected).

**Invariant satisfied:** every non-Void module's tool set is byte-identical
between pre and post. Only Void's 6 tools disappear, which is the
intended outcome of the demotion.

## Per-tool disposition

All 6 tools are **DROPPED** from the internal registry. Void is no
longer a routing target, so nothing in the router can dispatch to
these tools. Their underlying capabilities persist inside the
[`daemons/void/`](../../../daemons/void/) daemon but are exposed via
files on disk, not via tool schemas.

| Tool               | Pre permission      | Disposition | Replacement path                                                                                          |
|--------------------|---------------------|-------------|-----------------------------------------------------------------------------------------------------------|
| `system_snapshot`  | autonomous          | DROPPED     | Internal daemon tick. Output at `data/void_latest.json` (atomic JSON rewrite each poll cycle).            |
| `health_check`     | autonomous          | DROPPED     | Threshold evaluation runs every tick inside `daemons.void.thresholds.evaluate`; warning/critical crossings log to journald. |
| `metric_history`   | autonomous          | DROPPED     | Readable via direct SQLite on `data/void_metrics.db` (WAL-mode, concurrent readers safe). Schema unchanged from pre-demotion `modules/void/void.py`. |
| `service_check`    | autonomous          | DROPPED     | Daemon liveness is now `systemctl --user status shadow-void`. The Ollama liveness subset is covered by the Ollama systemd unit's own `Restart=always`. |
| `set_threshold`    | approval_required   | DROPPED     | Now a `config/config.yaml` edit under the top-level `void:` block, followed by `systemctl --user restart shadow-void`. No runtime mutation. |
| `void_report`      | autonomous          | DROPPED     | Harbinger's briefing assembly reads DB + `void_latest.json` directly (re-wiring deferred to a later session; current code degrades cleanly when `modules.get("void")` returns `None`). |

## Verification commands

```bash
# 1. Post-merge snapshot has no Void entry
jq 'keys | any(. == "void")' docs/phase-a/void/post_merge_tools.json
# expected: false

# 2. Every non-Void module's tool set matches between snapshots
python - <<'PY'
import json
pre  = json.load(open("docs/phase-a/void/pre_merge_tools.json"))
post = json.load(open("docs/phase-a/void/post_merge_tools.json"))
pre.pop("void", None)
for m in sorted(set(pre) | set(post)):
    assert pre.get(m) == post.get(m), f"drift in module '{m}'"
print("OK: non-void modules are byte-identical pre/post")
PY

# 3. Daemon still provides the capabilities by a different surface
python -m daemons.void &
sleep 70
sqlite3 data/void_metrics.db 'SELECT COUNT(*) FROM void_metrics;'
test -f data/void_latest.json && jq 'keys' data/void_latest.json
```
