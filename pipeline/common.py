"""Shared command-line setup for the collectors."""

from __future__ import annotations

import argparse
import logging
import signal
import time
from datetime import date, datetime, timezone
from pathlib import Path

from .http import Client, RateLimited

STORE_HOST = "store.steampowered.com"
COMMUNITY_HOST = "steamcommunity.com"

log = logging.getLogger(__name__)


def base_parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--data-dir", type=Path, default=Path("_data"),
                   help="where outputs go (the data branch checkout in CI)")
    p.add_argument("--cache-dir", type=Path, default=Path(".cache/http"),
                   help="HTTP cache, makes same-day reruns cheap")
    p.add_argument("--interval", type=float, default=1.0,
                   help="minimum seconds between requests to one host")
    p.add_argument("--store-interval", type=float, default=1.0,
                   help=f"seconds between requests to {STORE_HOST} (use 2 on GitHub runners)")
    p.add_argument("--community-interval", type=float, default=5.0,
                   help=f"seconds between requests to {COMMUNITY_HOST}, which blocks for a long time on 429")
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
    client = Client(
        min_interval=args.interval,
        host_intervals={STORE_HOST: args.store_interval, COMMUNITY_HOST: args.community_interval},
        # A 429 from the community site means a block that retrying extends: stop instead.
        stop_on_429_hosts={COMMUNITY_HOST},
        cache_dir=args.cache_dir,
    )
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


def run_pass(todo, fetch, label: str, budget: Budget, save, *,
             checkpoint: int, max_consecutive_errors: int, key=lambda item: item) -> bool:
    """Call fetch(item) for each item until done, out of budget, or blocked.

    `fetch` returns True if it made a request (counts toward checkpoints).
    Errors skip the item, which stays due for the next run. A RateLimited
    error, or too many errors in a row, stops the pass at once.
    Returns False if the pass stopped early.
    """
    fetched = errors = consecutive = 0
    for item in todo:
        if budget.expired():
            log.info("%s: budget used up", label)
            return False
        try:
            made_request = fetch(item)
            consecutive = 0
        except RateLimited as e:
            log.error("%s: rate limited (%s), stopping the run; retry later", label, e)
            return False
        except Exception as e:  # noqa: BLE001 - leave the item for the next run
            errors += 1
            consecutive += 1
            log.warning("%s failed for %s: %s", label, key(item), e)
            if consecutive >= max_consecutive_errors:
                log.error("%s: %d errors in a row, stopping", label, consecutive)
                return False
            continue
        if made_request:
            fetched += 1
            if fetched % checkpoint == 0:
                save()
                log.info("%s: %d/%d fetched, %d errors", label, fetched, len(todo), errors)
    return True
