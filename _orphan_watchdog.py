"""Auto-shutdown when the launching parent process dies.

Drop-in module for Python MCP servers wrapped by ``uv run``, ``uvx``,
``npx``, ``disclaimer`` (Claude.app), or any other launcher chain that
fails to propagate stdin-close / SIGTERM down to the actual server.

When the parent of this process exits, the OS reparents us to PID 1
(launchd on macOS, systemd/init on Linux). This module's daemon thread
notices the PPID change and calls ``os._exit(0)`` immediately,
preventing the orphan accumulation that otherwise piles up across
Claude Code / Claude.app session restarts.

Usage:

    # at the top of your MCP server entrypoint, before ``mcp.run()``
    from _orphan_watchdog import install
    install()

Disable (e.g. in pytest) with the env var ``PARENT_WATCHDOG_DISABLE=1``.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_INSTALLED = False


def install(
    poll_interval: float = 2.0,
    on_shutdown: Optional[Callable[[], None]] = None,
) -> None:
    """Spawn a daemon thread that exits the process when the parent dies.

    Args:
        poll_interval: Seconds between PPID checks. Defaults to 2s.
        on_shutdown: Optional callable invoked just before ``os._exit(0)``.
            Use for last-chance cleanup. Exceptions are suppressed.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    if os.environ.get("PARENT_WATCHDOG_DISABLE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    _INSTALLED = True

    initial_ppid = os.getppid()
    # If we were already started as PID 1's child (rare; daemonized launch),
    # the watchdog has nothing meaningful to watch — skip.
    if initial_ppid == 1:
        return

    def _exit(reason: str) -> None:
        try:
            sys.stderr.write(f"[orphan_watchdog] {reason}; shutting down\n")
            sys.stderr.flush()
        except Exception:  # nosec B110 -- best-effort logging during shutdown; failure must not block os._exit
            pass
        if on_shutdown is not None:
            try:
                on_shutdown()
            except Exception:  # nosec B110 -- caller-supplied cleanup is best-effort; never block shutdown
                pass
        os._exit(0)

    def _watch() -> None:
        while True:
            time.sleep(poll_interval)
            try:
                current_ppid = os.getppid()
            except Exception:  # nosec B112 -- transient OS errors must not kill the watchdog thread; retry next poll
                continue
            if current_ppid != initial_ppid or current_ppid == 1:
                _exit(
                    f"parent {initial_ppid} exited "
                    f"(reparented to {current_ppid})"
                )

    threading.Thread(
        target=_watch,
        name="orphan-watchdog",
        daemon=True,
    ).start()
    logger.debug(
        "orphan_watchdog installed (initial ppid=%d, poll=%.1fs)",
        initial_ppid,
        poll_interval,
    )
