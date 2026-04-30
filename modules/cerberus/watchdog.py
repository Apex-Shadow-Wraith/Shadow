"""
Cerberus Watchdog — Heartbeat Monitoring and Emergency Lockdown
=================================================================
Two components:

1. HeartbeatWriter — Background thread that writes periodic heartbeat
   JSON for the external watchdog daemon (daemons/cerberus_watchdog/).

2. CerberusWatchdog — In-process monitor that checks heartbeat freshness
   and creates a lockfile to halt all Shadow operations if Cerberus goes
   down. The orchestrator checks CerberusWatchdog.is_locked() at Step 1
   of every request.

Heartbeat file format (data/cerberus_heartbeat.json):
  {
    "timestamp": <unix_time>,
    "cerberus_status": "healthy" | "degraded",
    "active_rules_count": <int>,
    "last_check_id": <str>,
    "status": "alive" | "stopped",   # legacy field for HeartbeatWriter compat
    "checks_performed": <int>
  }
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("shadow.cerberus.watchdog")

# Default paths
DEFAULT_HEARTBEAT_PATH = Path("C:/Shadow/data/cerberus_heartbeat.json")
DEFAULT_LOCK_PATH = Path("C:/Shadow/data/cerberus_lock")
DEFAULT_EMERGENCY_LOG = Path("C:/Shadow/data/emergency_shutdown.log")


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
        self._heartbeat_path = heartbeat_path or DEFAULT_HEARTBEAT_PATH
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


class CerberusWatchdog:
    """In-process watchdog that monitors Cerberus heartbeat and locks Shadow.

    The orchestrator calls is_locked() at Step 1 of every request.
    If Cerberus has missed too many heartbeats, the watchdog creates
    a lockfile that halts all Shadow operations until Cerberus recovers.

    Heartbeat is written by Cerberus.send_heartbeat() at the end of
    every safety_check call — no separate timer needed for Phase 1.
    """

    def __init__(
        self,
        heartbeat_path: Path | None = None,
        lock_path: Path | None = None,
        emergency_log_path: Path | None = None,
        heartbeat_timeout: float = 90.0,
    ) -> None:
        self._heartbeat_path = heartbeat_path or DEFAULT_HEARTBEAT_PATH
        self._lock_path = lock_path or DEFAULT_LOCK_PATH
        self._emergency_log_path = emergency_log_path or DEFAULT_EMERGENCY_LOG
        self._heartbeat_timeout = heartbeat_timeout

    def check_heartbeat(self) -> bool:
        """Check if the Cerberus heartbeat is fresh.

        Returns:
            True if Cerberus is healthy (heartbeat within timeout).
            False if Cerberus is down (stale or missing heartbeat).
        """
        if not self._heartbeat_path.exists():
            logger.warning("Heartbeat file not found: %s", self._heartbeat_path)
            return False

        try:
            with open(self._heartbeat_path, "r", encoding="utf-8") as f:
                heartbeat = json.load(f)

            timestamp = heartbeat.get("timestamp", 0)
            age = time.time() - timestamp

            if age > self._heartbeat_timeout:
                logger.warning(
                    "Cerberus heartbeat stale! Age: %.1fs (timeout: %.1fs). "
                    "Status: %s",
                    age,
                    self._heartbeat_timeout,
                    heartbeat.get("cerberus_status", "unknown"),
                )
                return False

            return True

        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read heartbeat: %s", e)
            return False

    def on_cerberus_down(self, last_heartbeat: dict) -> None:
        """Emergency response when Cerberus is detected as down.

        Creates a lockfile to halt all Shadow operations, sends a
        Telegram alert, and logs the emergency. Does NOT call sys.exit.

        Args:
            last_heartbeat: The last heartbeat data read from file.
        """
        timestamp = datetime.now().isoformat()
        last_ts = last_heartbeat.get("timestamp", "unknown")
        if isinstance(last_ts, (int, float)):
            last_ts = datetime.fromtimestamp(last_ts).isoformat()

        # 1. Create lockfile
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_data = {
            "locked_at": timestamp,
            "reason": "Cerberus heartbeat timeout",
            "last_heartbeat": last_heartbeat,
        }
        with open(self._lock_path, "w", encoding="utf-8") as f:
            json.dump(lock_data, f, indent=2)
        logger.critical("LOCKFILE CREATED: %s", self._lock_path)

        # 2. Write to emergency log
        self._emergency_log_path.parent.mkdir(parents=True, exist_ok=True)
        log_line = (
            f"[{timestamp}] CERBERUS DOWN — Lockfile created. "
            f"Last heartbeat: {last_ts}\n"
        )
        with open(self._emergency_log_path, "a", encoding="utf-8") as f:
            f.write(log_line)
        logger.critical("Emergency logged: %s", self._emergency_log_path)

        # 3. Send Telegram alert (best-effort)
        alert_msg = (
            f"CRITICAL: Cerberus watchdog detected Cerberus failure. "
            f"All Shadow operations halted. Last heartbeat: {last_ts}"
        )
        self._send_telegram_alert(alert_msg)

    @staticmethod
    def is_locked(lock_path: Path | None = None) -> bool:
        """Check if Shadow is locked due to Cerberus failure.

        The orchestrator calls this at Step 1 of every request.

        Args:
            lock_path: Override lock file path (for testing).

        Returns:
            True if the lockfile exists (Shadow should refuse all work).
        """
        path = lock_path or DEFAULT_LOCK_PATH
        return path.exists()

    @staticmethod
    def clear_lock(lock_path: Path | None = None) -> None:
        """Remove the lockfile when Cerberus recovers.

        Called when Cerberus comes back online and heartbeat resumes.

        Args:
            lock_path: Override lock file path (for testing).
        """
        path = lock_path or DEFAULT_LOCK_PATH
        if path.exists():
            path.unlink()
            logger.info("Cerberus lock cleared. Shadow operations resumed.")
        else:
            logger.info("No lockfile found — nothing to clear.")

    def _send_telegram_alert(self, message: str) -> bool:
        """Send emergency alert via Telegram bot. Best-effort."""
        try:
            from shadow.config import config as _shadow_config

            h = _shadow_config.harbinger
            token = (
                h.telegram_bot_token.get_secret_value()
                if h.telegram_bot_token
                else None
            )
            chat_id = (
                h.telegram_chat_id.get_secret_value()
                if h.telegram_chat_id
                else None
            )

            if not token or not chat_id:
                logger.warning("Telegram not configured — skipping alert")
                return False

            from urllib.request import Request, urlopen

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
            req = Request(url, data=data, headers={"Content-Type": "application/json"})
            urlopen(req, timeout=10)
            logger.info("Telegram alert sent")
            return True

        except Exception as e:
            logger.error("Failed to send Telegram alert: %s", e)
            return False
