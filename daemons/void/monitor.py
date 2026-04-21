"""Void daemon poll loop + signal handling.

One asyncio task ticks every `poll_interval_seconds`:
    1. Collect a snapshot (metrics.collect_snapshot)
    2. Insert metric rows into `data/void_metrics.db`
    3. Atomically rewrite `data/void_latest.json`
    4. Evaluate thresholds and log crossings at WARNING / ERROR
    5. Once per hour, prune rows older than `retention_days`

Exits cleanly on SIGTERM / SIGINT (commits pending writes, closes DB,
returns 0). If `enabled=False`, logs and exits 0 immediately — systemd
will NOT restart because exit status is 0, not a failure.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timedelta

from daemons.void.config import VoidDaemonSettings
from daemons.void.metrics import collect_snapshot, snapshot_to_metric_rows
from daemons.void.storage import MetricStore, write_latest_snapshot
from daemons.void.thresholds import evaluate

logger = logging.getLogger("shadow.daemons.void")

_SEVERITY_LOG_LEVEL = {
    "healthy": logging.DEBUG,
    "warning": logging.WARNING,
    "critical": logging.ERROR,
}


async def _tick(settings: VoidDaemonSettings, store: MetricStore) -> dict:
    """Run a single collection tick. Returns the snapshot dict."""
    snapshot = collect_snapshot()
    store.insert_metrics(snapshot_to_metric_rows(snapshot))
    write_latest_snapshot(settings.latest_snapshot_path, snapshot)

    verdict = evaluate(snapshot, settings.thresholds)
    level = _SEVERITY_LOG_LEVEL.get(verdict["status"], logging.INFO)
    if verdict["status"] == "healthy":
        logger.log(level, "tick: healthy (cpu=%.1f ram=%.1f disk=%.1f)",
                   snapshot["cpu_percent"], snapshot["ram_percent"], snapshot["disk_percent"])
    else:
        for alert in verdict["alerts"]:
            logger.log(
                level,
                "threshold %s: %s=%.1f crossed %s (%.1f)",
                alert["severity"],
                alert["metric"],
                alert["value"],
                alert["severity"],
                alert["threshold"],
            )
    return snapshot


async def run(settings: VoidDaemonSettings) -> int:
    """Run the Void daemon until cancelled. Returns an exit code."""
    if not settings.enabled:
        logger.info("Void daemon disabled (config.void.enabled=False); exiting cleanly.")
        return 0

    logger.info(
        "Void daemon starting: poll_interval=%ss db=%s latest=%s retention_days=%s",
        settings.poll_interval_seconds,
        settings.db_path,
        settings.latest_snapshot_path,
        settings.retention_days,
    )

    store = MetricStore(settings.db_path)
    store.open()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Signal handlers not supported on this platform (rare under systemd).
            pass

    last_prune = datetime.now() - timedelta(hours=1)
    try:
        while not stop_event.is_set():
            try:
                await _tick(settings, store)
            except Exception as e:
                logger.exception("tick failed: %s", e)

            if datetime.now() - last_prune >= timedelta(hours=1):
                try:
                    pruned = store.prune_older_than(settings.retention_days)
                    if pruned:
                        logger.info("Pruned %d rows older than %d days",
                                    pruned, settings.retention_days)
                except Exception as e:
                    logger.warning("prune failed: %s", e)
                last_prune = datetime.now()

            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass  # normal tick boundary

        logger.info("Void daemon received stop signal; shutting down.")
    finally:
        store.close()

    return 0
