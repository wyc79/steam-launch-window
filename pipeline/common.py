"""Shared command-line setup for the collectors."""

from __future__ import annotations

import argparse
import logging
import signal
import time
from datetime import date, datetime, timezone
from pathlib import Path

from .http import Client


def base_parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--data-dir", type=Path, default=Path("_data"),
                   help="where outputs go (the data branch checkout in CI)")
    p.add_argument("--cache-dir", type=Path, default=Path(".cache/http"),
                   help="HTTP cache, makes same-day reruns cheap")
    p.add_argument("--interval", type=float, default=1.0,
                   help="minimum seconds between requests to one host")
    p.add_argument("--today", type=date.fromisoformat, default=None,
                   help="override the run date (UTC), mostly for tests")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def _sigterm_to_interrupt(signum, frame):
    raise KeyboardInterrupt


def setup(args) -> tuple[Client, date]:
    # systemd stop, a reboot or a cancelled CI job sends SIGTERM; treat it like
    # Ctrl+C so the collectors save their progress before exiting.
    signal.signal(signal.SIGTERM, _sigterm_to_interrupt)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    client = Client(min_interval=args.interval, cache_dir=args.cache_dir)
    today = args.today or datetime.now(timezone.utc).date()
    return client, today


class Budget:
    """Wall-clock budget so a CI job stops cleanly before its time limit."""

    def __init__(self, minutes: float, clock=time.monotonic):
        self._clock = clock
        self._deadline = clock() + minutes * 60

    def left(self) -> float:
        return self._deadline - self._clock()

    def expired(self) -> bool:
        return self.left() <= 0
