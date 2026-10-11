"""Follower counts for upcoming games, refreshed on a tiered schedule.

Each game gets a refresh interval from its tier (see `tier_for`). A run
fetches every game that is due, most urgent tier first, until the time
budget runs out. Games never fetched are always due, so the first run on
an empty data dir is the full scrape. Progress is saved every
--checkpoint fetches, so a killed run loses little and the next run
picks up where it stopped.

Outputs (under --data-dir):
  followers/latest.csv                   newest count per game (also the resume state)
  followers/snapshots/YYYY-MM-DD.csv.gz  every count fetched that UTC day
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import steam, storage
from .common import Budget, base_parser, setup

FIELDS = ["appid", "followers", "fetched_at"]
log = logging.getLogger("collect_followers")


@dataclass(frozen=True)
class Policy:
    near_weeks: int = 8          # tier 0 if the date range overlaps the next N weeks
    far_weeks: int = 26          # tier 1 if it overlaps weeks near..far
    high_followers: int = 10_000  # tier 0 regardless of date
    intervals_days: tuple = (1, 3, 7, 30)  # tiers 0..3: near/high, mid, far, undated


TIER_NAMES = ("near or high followers", "mid range", "far", "undated")


def tier_for(row: dict, followers: int | None, today: date, policy: Policy) -> int:
    if followers is not None and followers >= policy.high_followers:
        return 0
    if not row.get("date"):
        return 3
    start, end = date.fromisoformat(row["date"]), date.fromisoformat(row["date_end"])
    if end < today:  # date passed but still listed as coming soon: watch closely
        return 0
    if start <= today + timedelta(weeks=policy.near_weeks):
        return 0
    if start <= today + timedelta(weeks=policy.far_weeks):
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
    args = p.parse_args(argv)
    client, _ = setup(args)
    policy = Policy(high_followers=args.high_followers)

    snap_path = latest_snapshot_path(args.data_dir)
    snapshot = storage.read_csv(snap_path)
    latest = {int(r["appid"]): r for r in storage.read_csv(args.data_dir / "followers" / "latest.csv")}
    now = datetime.now(timezone.utc)
    todo = plan(snapshot, latest, now, policy)
    by_tier = [sum(1 for t, _ in todo if t == i) for i in range(4)]
    log.info("snapshot %s: %d games, %d due %s", snap_path.name, len(snapshot), len(todo),
             dict(zip(TIER_NAMES, by_tier)))
    if args.dry_run:
        return 0

    budget = Budget(args.budget_minutes)
    fetched_by_day: dict[str, list[dict]] = {}
    done = errors = consecutive = 0
    t0 = time.monotonic()
    try:
        for tier, appid in todo:
            if budget.expired():
                log.info("budget used up")
                break
            try:
                count = steam.follower_count(client, appid)
                consecutive = 0
            except Exception as e:  # noqa: BLE001 - skip this game, it stays due
                errors += 1
                consecutive += 1
                log.warning("followers for %s failed: %s", appid, e)
                if consecutive >= args.max_consecutive_errors:
                    log.error("%d errors in a row, stopping (blocked or endpoint changed?)", consecutive)
                    break
                continue
            stamp = datetime.now(timezone.utc).replace(microsecond=0)
            row = {"appid": appid, "followers": "" if count is None else count, "fetched_at": stamp.isoformat()}
            latest[appid] = row
            fetched_by_day.setdefault(stamp.date().isoformat(), []).append(row)
            done += 1
            if done % args.checkpoint == 0:
                save(args.data_dir, latest, fetched_by_day)
                fetched_by_day = {}
                rate = done / (time.monotonic() - t0)
                log.info("%d/%d fetched (%.2f/s, tier %d), %d errors", done, len(todo), rate, tier, errors)
    except KeyboardInterrupt:
        log.info("interrupted, saving progress")
    finally:
        save(args.data_dir, latest, fetched_by_day)
    log.info("done: %d fetched, %d errors, %d still due", done, errors, len(todo) - done)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
