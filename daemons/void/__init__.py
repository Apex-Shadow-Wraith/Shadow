"""Void daemon — passive system monitoring.

Demoted from `modules/void/void.py` in Phase A. Void is no longer a
routing target; it runs as a user-mode systemd service that polls
metrics on a schedule, writes them to SQLite, and atomically rewrites
`data/void_latest.json` each tick.
"""

from daemons.void.monitor import run

__all__ = ["run"]
