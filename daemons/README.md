# Shadow Daemons

Long-running background services that are **not** routing targets for
the Shadow orchestrator. A daemon runs out-of-process under user-mode
systemd, writes state to disk (usually SQLite, optionally JSON), and
is consulted by the rest of Shadow through those files rather than
through a Python call chain.

The distinction from `modules/`:

|                   | Module (`modules/<name>/`)            | Daemon (`daemons/<name>/`)                     |
|-------------------|---------------------------------------|------------------------------------------------|
| Lifecycle         | Instantiated by `main.py` at boot     | Started by user-mode systemd                   |
| Routing target    | Yes (via `ModuleRegistry`)            | No — deliberately invisible to the router      |
| Tool surface      | `get_tools()` → internal registry     | None                                           |
| State persistence | In-process + Grimoire/SQLite          | Own SQLite + optional snapshot JSON            |
| How others query  | Direct Python calls / tool dispatch   | Read the daemon's DB or snapshot file          |

## Current inhabitants

- [`void/`](void/) — passive system monitor. Polls CPU / RAM / disk /
  GPU / process metrics, writes to `data/void_metrics.db`, atomic-
  rewrites `data/void_latest.json` each tick. Demoted from
  `modules/void/` in Phase A.

## Installing / enabling

Systemd unit files live under [`deploy/systemd/`](../deploy/systemd/).
To install all Shadow daemon units at their supported state:

```bash
bash deploy/systemd/install.sh
```

That script installs to `~/.config/systemd/user/`, reloads the daemon,
enables + starts each unit, and prints `status`. Re-run it safely after
editing a unit file.

Manual equivalent:

```bash
install -m 0644 deploy/systemd/shadow-void.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now shadow-void.service
systemctl --user status shadow-void.service --no-pager
```

## Tailing logs

```bash
journalctl --user -u shadow-void -f
```

## Stopping / disabling

```bash
systemctl --user disable --now shadow-void.service
```

## Editing config

All daemon config lives in the standard Shadow settings singleton —
`config/config.yaml` (checked-in defaults) plus `config/config.local.yaml`
(per-machine overrides). After editing:

```bash
systemctl --user restart shadow-void.service
```

## Adding a new daemon

1. Create `daemons/<name>/` with `__init__.py`, `__main__.py` (thin
   entry point), and whatever internal modules the daemon needs.
2. Add a typed settings class to `daemons/<name>/config.py` and wire
   it into `shadow/config/__init__.py` as a top-level field.
3. Add a `.service` file under `deploy/systemd/` modeled on
   `shadow-void.service`.
4. Extend `deploy/systemd/install.sh` to install the new unit.
5. Update this README's "Current inhabitants" section.
