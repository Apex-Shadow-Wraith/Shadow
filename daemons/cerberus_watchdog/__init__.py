"""Cerberus Watchdog daemon — external heartbeat monitor + emergency lockdown.

Promoted from `scripts/watchdog_cerberus.py` to match Void's daemon
convention (`daemons/<name>/` + `deploy/systemd/shadow-<name>.service`).
Runs as a user-mode systemd service, polls Cerberus's heartbeat file,
and on consecutive failures sends a Telegram alert and pkill's the
Shadow process.
"""

from daemons.cerberus_watchdog.watchdog import run

__all__ = ["run"]
