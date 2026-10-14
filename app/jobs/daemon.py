"""Background daemon process to periodically trigger follow-up and vaccine reminders."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from datetime import UTC, datetime

from app.jobs.reminders import main as run_reminders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [reminders-daemon] %(message)s",
)
logger = logging.getLogger(__name__)

# Default interval: 24 hours (86400 seconds)
DEFAULT_INTERVAL_SECONDS = 86400


def get_interval_seconds() -> int:
    env_val = os.getenv("REMINDERS_INTERVAL_SECONDS")
    if env_val:
        try:
            return max(60, int(env_val))
        except ValueError:
            logger.warning("Invalid REMINDERS_INTERVAL_SECONDS=%s, using default %d", env_val, DEFAULT_INTERVAL_SECONDS)

    env_hours = os.getenv("REMINDERS_INTERVAL_HOURS")
    if env_hours:
        try:
            return max(60, int(float(env_hours) * 3600))
        except ValueError:
            logger.warning("Invalid REMINDERS_INTERVAL_HOURS=%s, using default %d", env_hours, DEFAULT_INTERVAL_SECONDS)

    return DEFAULT_INTERVAL_SECONDS


async def run_daemon() -> None:
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Fallback for platforms where signal handlers are not supported on event loop
            signal.signal(sig, lambda *_: stop_event.set())

    interval = get_interval_seconds()
    run_on_startup = os.getenv("REMINDERS_RUN_ON_STARTUP", "true").lower() in ("true", "1", "yes")

    logger.info("Reminders daemon starting up. Interval: %d seconds. Run on startup: %s", interval, run_on_startup)

    if run_on_startup:
        try:
            logger.info("Running initial reminders scan on startup...")
            await run_reminders()
        except Exception as exc:
            logger.exception("Initial reminders execution failed: %s", exc)

    while not stop_event.is_set():
        logger.info("Next reminders run in %d seconds (~%.1f hours)...", interval, interval / 3600)
        try:
            # Sleep in intervals or until shutdown signal
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except TimeoutError:
            pass

        if stop_event.is_set():
            break

        try:
            logger.info("Triggering scheduled reminder scan at %s...", datetime.now(UTC).isoformat())
            await run_reminders()
            logger.info("Reminder scan completed successfully.")
        except Exception as exc:
            logger.exception("Error during scheduled reminder execution: %s", exc)

    logger.info("Reminders daemon shutting down cleanly.")


if __name__ == "__main__":
    asyncio.run(run_daemon())
