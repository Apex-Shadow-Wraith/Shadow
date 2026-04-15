"""
Ollama Supervisor — Process Health Monitor
============================================
Monitors Ollama process health and restarts on failure.

Runs a background health check every N seconds. If Ollama is
unresponsive, attempts restart. Logs all events. Alerts via
Harbinger after 3 consecutive failures.
"""

import asyncio
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

logger = logging.getLogger("shadow.ollama_supervisor")


class OllamaSupervisor:
    """Monitors Ollama process health and restarts on failure.

    Runs a background health check every N seconds. If Ollama is
    unresponsive, attempts restart. Logs all events. Alerts via
    Harbinger after 3 consecutive failures.
    """

    def __init__(
        self,
        check_interval: int = 300,
        max_retries: int = 5,
        ollama_bin: str = "ollama",
        harbinger: object | None = None,
    ) -> None:
        self.check_interval = check_interval
        self.max_retries = max_retries
        self.ollama_bin = ollama_bin
        self.harbinger = harbinger

        self._running = False
        self._task: asyncio.Task | None = None
        self._process: subprocess.Popen | None = None
        self._restart_count = 0
        self._consecutive_failures = 0
        self._start_time: float | None = None
        self._last_check: datetime | None = None
        self._ollama_healthy = False
        self._max_retries_exhausted = False

    async def start(self) -> None:
        """Begin background monitoring loop."""
        if self._running:
            logger.warning("OllamaSupervisor already running")
            return

        self._running = True
        self._start_time = time.monotonic()
        self._max_retries_exhausted = False
        logger.info(
            "OllamaSupervisor starting — check every %ds, max %d retries",
            self.check_interval,
            self.max_retries,
        )
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("OllamaSupervisor stopped — %d restarts performed", self._restart_count)

    async def health_check(self) -> bool:
        """Hit http://localhost:11434/api/tags, return True if 200."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "http://localhost:11434/api/tags",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    healthy = resp.status == 200
                    self._last_check = datetime.now(timezone.utc)
                    return healthy
        except Exception:
            self._last_check = datetime.now(timezone.utc)
            return False

    async def restart_ollama(self) -> bool:
        """Kill existing process, start new one with `ollama serve`, wait up to 30s for health."""
        logger.info("Attempting Ollama restart (attempt %d)", self._restart_count + 1)

        # Kill existing ollama processes
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "ollama.exe"],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            # On Linux, try killall
            try:
                subprocess.run(
                    ["killall", "ollama"],
                    capture_output=True,
                    timeout=10,
                )
            except Exception:
                pass

        # Wait briefly for process to die
        await asyncio.sleep(1)

        # Start ollama serve
        try:
            self._process = subprocess.Popen(
                [self.ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.error("Ollama binary not found: %s", self.ollama_bin)
            return False
        except Exception as e:
            logger.error("Failed to start Ollama: %s", e)
            return False

        # Wait up to 30s for health check to pass
        for _ in range(15):
            await asyncio.sleep(2)
            if await self.health_check():
                self._restart_count += 1
                self._consecutive_failures = 0
                self._ollama_healthy = True
                logger.info("Ollama restarted successfully (total restarts: %d)", self._restart_count)
                return True

        logger.error("Ollama failed to become healthy within 30s")
        return False

    def _on_failure(self, consecutive_failures: int) -> None:
        """Log warning. If >= 3, create Harbinger alert."""
        logger.warning(
            "Ollama health check failed — %d consecutive failure(s)",
            consecutive_failures,
        )

        if consecutive_failures >= 3 and self.harbinger is not None:
            try:
                self.harbinger.execute(
                    "notification_send",
                    {
                        "message": (
                            f"Ollama has failed {consecutive_failures} consecutive health checks. "
                            f"Restart attempts: {self._restart_count}. "
                            "Shadow's local AI runtime may be down."
                        ),
                        "severity": 4,
                        "category": "system_health",
                    },
                )
                logger.info("Harbinger alert sent for %d consecutive Ollama failures", consecutive_failures)
            except Exception as e:
                logger.error("Failed to send Harbinger alert: %s", e)

    def get_status(self) -> dict:
        """Return current supervisor status."""
        uptime = 0.0
        if self._start_time is not None:
            uptime = time.monotonic() - self._start_time

        return {
            "running": self._running,
            "uptime_seconds": round(uptime, 1),
            "restart_count": self._restart_count,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "consecutive_failures": self._consecutive_failures,
            "ollama_healthy": self._ollama_healthy,
            "max_retries_exhausted": self._max_retries_exhausted,
        }

    async def _monitor_loop(self) -> None:
        """Background loop that checks health and restarts on failure."""
        while self._running:
            try:
                healthy = await self.health_check()

                if healthy:
                    self._ollama_healthy = True
                    self._consecutive_failures = 0
                else:
                    self._ollama_healthy = False
                    self._consecutive_failures += 1
                    self._on_failure(self._consecutive_failures)

                    if self._restart_count >= self.max_retries:
                        logger.critical(
                            "Ollama max retries (%d) exhausted — supervisor giving up",
                            self.max_retries,
                        )
                        self._max_retries_exhausted = True
                        self._running = False
                        return

                    restarted = await self.restart_ollama()
                    if not restarted:
                        logger.error("Ollama restart failed")

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Unexpected error in monitor loop: %s", e)
                await asyncio.sleep(self.check_interval)
