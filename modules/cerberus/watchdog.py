"""
Cerberus Heartbeat Writer
===========================
Writes periodic heartbeat JSON so an external watchdog process
can verify Cerberus is alive. Runs in a daemon thread within
the main Shadow process.

The companion watchdog script lives at scripts/watchdog_cerberus.py
and runs as a completely separate process.
"""

import json
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger("shadow.cerberus.watchdog")


class HeartbeatWriter:
    """Writes periodic heartbeat files for external monitoring.

    The heartbeat is a JSON file updated every `interval` seconds:
      {"timestamp": <unix_time>, "status": "alive", "checks_performed": <count>}

    Uses atomic write (tmp file + rename) to prevent the external
    watchdog from reading a half-written file.
    """

    def __init__(
        self,
        heartbeat_path: Path | None = None,
        interval: float = 10.0,
    ) -> None:
        self._heartbeat_path = heartbeat_path or Path("C:/Shadow/data/cerberus_heartbeat.json")
        self._interval = interval
        self._checks_performed: int = 0
        self._running: bool = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the heartbeat background thread."""
        if self._running:
            logger.warning("HeartbeatWriter already running")
            return

        self._heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        self._running = True
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            name="cerberus-heartbeat",
            daemon=True,
        )
        self._thread.start()
        logger.info("HeartbeatWriter started (interval: %.1fs)", self._interval)

    def stop(self) -> None:
        """Stop the heartbeat thread and write a final 'stopped' heartbeat."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self._interval * 2)
            self._thread = None

        # Write final stopped heartbeat
        self._write_heartbeat("stopped")
        logger.info("HeartbeatWriter stopped")

    def increment_checks(self) -> None:
        """Increment the checks counter. Called by Cerberus after each safety check."""
        self._checks_performed += 1

    def _heartbeat_loop(self) -> None:
        """Main heartbeat loop. Runs in background thread."""
        while self._running:
            self._write_heartbeat("alive")
            # Sleep in small increments so stop() doesn't block long
            elapsed = 0.0
            while elapsed < self._interval and self._running:
                time.sleep(min(0.5, self._interval - elapsed))
                elapsed += 0.5

    def _write_heartbeat(self, status: str) -> None:
        """Atomic write of heartbeat JSON."""
        heartbeat = {
            "timestamp": time.time(),
            "status": status,
            "checks_performed": self._checks_performed,
        }
        tmp_path = self._heartbeat_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(heartbeat, f)
            tmp_path.replace(self._heartbeat_path)
        except OSError as e:
            logger.error("Failed to write heartbeat: %s", e)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def checks_performed(self) -> int:
        return self._checks_performed
