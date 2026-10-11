"""Follower counts for upcoming games, refreshed on a tiered schedule.

steamcommunity.com rate-limits hard (see docs/endpoints.md), so only games
that matter for the heatmap or have hype are tracked:
- games on Steam's Top Wishlisted list, and
- games with a day or month release date ending within --far-weeks.

Each tracked game gets a refresh interval from its tier (see `tier_for`).
Wishlist rank is the main hype signal; followers are a secondary one.

A run fetches every game that is due, most urgent tier first, until the
time budget runs out. Games never fetched are always due, so the first
run on an empty data dir is the full scrape. Progress is saved every
--checkpoint fetches, so a killed run loses little and the next run
picks up where it stopped.

Outputs (under --data-dir):
  followers/latest.csv                   newest count per game (also the resume state)
  followers/snapshots/YYYY-MM-DD.csv.gz  every count fetched that UTC day
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from datetime import time as dt_time
from pathlib import Path

from . import steam, storage
from .common import Budget, base_parser, run_pass, setup

FIELDS = ["appid", "followers", "fetched_at"]
log = logging.getLogger("collect_followers")


@dataclass(frozen=True)
class Policy:
    near_weeks: int = 8           # tier 0 if the whole date range ends within N weeks
    far_weeks: int = 26           # tier 1 if it ends within weeks near..far
    high_followers: int = 10_000  # tier 0 regardless of date
    intervals_days: tuple = (1, 3, 7)  # tiers 0..2


TIER_NAMES = ("daily", "every 3 days", "weekly")
PRECISE = {"day", "month"}


def tier_for(row: dict, followers: int | None, today: date, policy: Policy) -> int | None:
    """Refresh tier for one snapshot row, or None if the game is not tracked."""
    ranked = bool(row.get("wishlist_rank"))
    end = date.fromisoformat(row["date_end"]) if row.get("precision") in PRECISE else None
    in_window = end is not None and end <= today + timedelta(weeks=policy.far_weeks)
    if not (ranked or in_window):
        return None
    if followers is not None and followers >= policy.high_followers:
        return 0
    if end is not None and end <= today + timedelta(weeks=policy.near_weeks):
        return 0  # launching soon, or the date passed and it is still "coming soon"
    if in_window:
        return 1
    return 2


def plan(snapshot: list[dict], latest: dict[int, dict], now: datetime, policy: Policy) -> list[tuple[int, int]]:
    """(tier, appid) for every due game, most urgent first."""
    today = now.date()
    due = []
    for row in snapshot:
        appid = int(row["appid"])
        prev = latest.get(appid)
        followers = int(prev["followers"]) if prev and prev["followers"] else None
        tier = tier_for(row, followers, today, policy)
        if tier is None:
            continue
        if prev:
            age = now - datetime.fromisoformat(prev["fetched_at"])
            # 2 hours of slack so a daily job that starts a bit early still refreshes
            if age < timedelta(days=policy.intervals_days[tier]) - timedelta(hours=2):
                continue
            last = prev["fetched_at"]
        else:
            last = ""  # never fetched sorts first
        rank = int(row["wishlist_rank"]) if row.get("wishlist_rank") else 10**9
        due.append((tier, last, rank, appid))
    due.sort()
    return [(t, a) for t, _, _, a in due]


def latest_snapshot_path(data_dir: Path) -> Path:
    paths = sorted((data_dir / "upcoming" / "snapshots").glob("*.csv.gz"))
    if not paths:
        raise SystemExit("no upcoming snapshot found; run collect_upcoming first")
    return paths[-1]


def save(data_dir: Path, latest: dict[int, dict], fetched_by_day: dict[str, list[dict]]) -> None:
    storage.write_csv(data_dir / "followers" / "latest.csv", [latest[a] for a in sorted(latest)], FIELDS)
    for day, rows in fetched_by_day.items():
        path = data_dir / "followers" / "snapshots" / f"{day}.csv.gz"
        merged = {int(r["appid"]): r for r in storage.read_csv(path)}
        merged.update({int(r["appid"]): r for r in rows})
        storage.write_csv(path, [merged[a] for a in sorted(merged)], FIELDS)


def main(argv=None) -> int:
    p = base_parser(__doc__)
    p.add_argument("--budget-minutes", type=float, default=240)
    p.add_argument("--checkpoint", type=int, default=200, help="save every N fetches")
    p.add_argument("--max-consecutive-errors", type=int, default=25)
    p.add_argument("--high-followers", type=int, default=Policy.high_followers)
    p.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    p.add_argument("--fail-if-incomplete", action="store_true",
                   help="exit with code 3 if games are still due (for a retry loop)")
    args = p.parse_args(argv)
    client, today = setup(args)
    policy = Policy(high_followers=args.high_followers)

    snap_path = latest_snapshot_path(args.data_dir)
    snapshot = storage.read_csv(snap_path)
    latest = {int(r["appid"]): r for r in storage.read_csv(args.data_dir / "followers" / "latest.csv")}
    now = datetime.now(timezone.utc)
    if args.today:  # replay a past day: plan as of its noon UTC
        now = datetime.combine(args.today, dt_time(12), tzinfo=timezone.utc)
    todo = plan(snapshot, latest, now, policy)
    by_tier = [sum(1 for t, _ in todo if t == i) for i in range(len(TIER_NAMES))]
    log.info("snapshot %s: %d games, %d due %s", snap_path.name, len(snapshot), len(todo),
             dict(zip(TIER_NAMES, by_tier)))
    if args.dry_run:
        return 0

    fetched_by_day: dict[str, list[dict]] = {}

    def fetch(job):
        _, appid = job
        count = steam.follower_count(client, appid)
        stamp = datetime.now(timezone.utc).replace(microsecond=0)
        row = {"appid": appid, "followers": "" if count is None else count, "fetched_at": stamp.isoformat()}
        latest[appid] = row
        fetched_by_day.setdefault(stamp.date().isoformat(), []).append(row)
        return True

    def checkpoint():
        save(args.data_dir, latest, fetched_by_day)
        fetched_by_day.clear()

    try:
        run_pass(todo, fetch, "followers", Budget(args.budget_minutes), checkpoint,
                 checkpoint=args.checkpoint, max_consecutive_errors=args.max_consecutive_errors,
                 key=lambda job: job[1])
    except KeyboardInterrupt:
        log.info("interrupted, saving progress")
    finally:
        checkpoint()
    still_due = len(plan(snapshot, latest, now, policy))
    log.info("done: %d still due", still_due)
    return 3 if args.fail_if_incomplete and still_due else 0


if __name__ == "__main__":
    raise SystemExit(main())
