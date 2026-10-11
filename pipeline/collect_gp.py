"""Follower and player history from Games Popularity, within a daily request budget.

One request returns a game's whole daily follower series, so how often a game
is pulled only decides how fresh its newest value is. Jobs, most urgent first:
  0. followers, about 8 days after launch (whole pre-launch series plus launch week);
     missed ones are caught up for 60 days
  1. players, 35 to 42 days after launch (hourly counts for the first month, one page)
  2. followers for every upcoming game with a date or a wishlist rank, every 60 days
  3. backfill: followers for games launched since 2024-03-15 (and more than 60 days
     ago; newer ones get job 0) that were never pulled;
     paid launches with 10+ reviews first, then 1+, then the rest; newest first

The run stops when the day's budget is used (requests already made today, from
runs.csv, count too), at the first 429, or after too many errors in a row.

Reads (under --data-dir): the newest upcoming snapshot and history/games.csv.
Writes (under --gp-dir; the daily job syncs it with a private Hugging Face dataset):
  followers/YYYY-MM-DD.csv.gz  points fetched that UTC day: appid, followers, observed_at, fetched_at
  players/YYYY-MM-DD.csv.gz    same, with players
  state.csv                    per (appid, kind): last_pulled, status, last_observed_at, points
  runs.csv                     one row per run: requests, results, why it stopped
status is ok, null (no data), not_in_dataset (404), stale (newest point older than
14 days) or partial (stopped after max pages; older points not fetched).
observed_at is Games Popularity's own time for the point, fetched_at is ours.
"""

from __future__ import annotations

import collections
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from . import gp, storage
from .common import base_parser, setup
from .collect_followers import latest_snapshot_path
from .http import Client, HTTPStatusError

STATE_FIELDS = ["appid", "kind", "last_pulled", "status", "last_observed_at", "points"]
RUN_FIELDS = ["date", "started_at", "requests", "jobs", "ok", "null", "not_in_dataset", "stale",
              "partial", "points", "errors", "stopped"]
MAX_PAGES = 5

log = logging.getLogger("collect_gp")


@dataclass(frozen=True)
class Policy:
    post_launch_days: int = 8
    post_launch_window: int = 60
    players_days: int = 35
    players_window: int = 42     # one page of hourly points covers about 41 days
    refresh_days: int = 60
    stale_page_days: int = 30      # upcoming dates this far past are stale store pages, not tracked
    stale_days: int = 14
    backfill_since: date = date(2024, 3, 15)


@dataclass(frozen=True, order=True)
class Job:
    priority: int
    order: tuple
    kind: str = field(compare=False)
    appid: int = field(compare=False)
    since: datetime | None = field(default=None, compare=False)


def _ts(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None


def _midnight(d: date) -> datetime:
    return datetime.combine(d, time(0), tzinfo=timezone.utc)


def _backfill_group(row: dict) -> int:
    reviews = int(row.get("reviews_total_now") or 0)
    paid = row.get("is_free") == "0" and row.get("launch_type") != "ea_exit"
    if paid and reviews >= 10:
        return 0
    if paid and reviews >= 1:
        return 1
    return 2


def plan(snapshot: list[dict], history: list[dict], state: dict, today: date, policy: Policy) -> list[Job]:
    """Due jobs, most urgent first, one per (kind, appid)."""
    best: dict[tuple[str, int], Job] = {}

    def add(job: Job):
        key = (job.kind, job.appid)
        if key not in best or job < best[key]:
            best[key] = job

    for row in history:
        appid = int(row["appid"])
        launch = date.fromisoformat(row["launch_date"])
        age = (today - launch).days
        followers = state.get(("followers", appid))
        last = _ts(followers["last_pulled"]) if followers else None
        since = _ts(followers["last_observed_at"]) if followers else None
        if policy.post_launch_days <= age <= policy.post_launch_window and (
                last is None or last.date() < launch + timedelta(days=policy.post_launch_days - 1)):
            add(Job(0, (launch.toordinal(), appid), "followers", appid, since))
        if policy.players_days <= age <= policy.players_window and ("players", appid) not in state:
            add(Job(1, (launch.toordinal(), appid), "players", appid, _midnight(launch - timedelta(days=1))))
        if launch >= policy.backfill_since and age > policy.post_launch_window and followers is None:
            add(Job(3, (_backfill_group(row), -launch.toordinal(), appid), "followers", appid))

    stale_before = (today - timedelta(days=policy.stale_page_days)).isoformat()
    for row in snapshot:
        dated = row.get("precision") not in ("", "unknown", None)
        if not (dated or row.get("wishlist_rank")):
            continue
        if dated and row["date_end"] < stale_before:
            continue
        appid = int(row["appid"])
        followers = state.get(("followers", appid))
        if followers and (today - _ts(followers["last_pulled"]).date()).days < policy.refresh_days:
            continue
        rank = int(row["wishlist_rank"]) if row.get("wishlist_rank") else 10**9
        order = (0 if followers is None else 1, row.get("date_end") or "9999", rank, appid)
        add(Job(2, order, "followers", appid, _ts(followers["last_observed_at"]) if followers else None))
    return sorted(best.values())


# -- state and output files ----------------------------------------------------

def load_state(gp_dir: Path) -> dict:
    return {(r["kind"], int(r["appid"])): r for r in storage.read_csv(gp_dir / "state.csv")}


def save_state(gp_dir: Path, state: dict) -> None:
    storage.write_csv(gp_dir / "state.csv", [state[k] for k in sorted(state)], STATE_FIELDS)


def _save_points(gp_dir: Path, day: str, points: dict[str, list[dict]]) -> None:
    for kind, rows in points.items():
        if not rows:
            continue
        path = gp_dir / kind / f"{day}.csv.gz"
        merged = {(r["appid"], r["observed_at"]): r for r in storage.read_csv(path)}
        merged.update({(str(r["appid"]), r["observed_at"]): r for r in rows})
        storage.write_csv(path, [merged[k] for k in sorted(merged, key=lambda k: (int(k[0]), k[1]))],
                          ["appid", kind, "observed_at", "fetched_at"])
        rows.clear()


def used_today(gp_dir: Path, day: str) -> int:
    return sum(int(r["requests"] or 0) for r in storage.read_csv(gp_dir / "runs.csv") if r["date"] == day)


# -- running -------------------------------------------------------------------

def run(todo: list[Job], client, key: str, state: dict, gp_dir: Path, now: datetime, budget: int, *,
        policy: Policy = Policy(), checkpoint: int = 100, max_consecutive_errors: int = 10) -> dict:
    day = now.date().isoformat()
    allowed = budget - used_today(gp_dir, day)
    start = client.requests_made
    stamp = now.replace(microsecond=0).isoformat()
    points: dict[str, list[dict]] = {k: [] for k in gp.KINDS}
    stats = collections.Counter()
    stopped, consecutive = "done", 0

    def save():
        _save_points(gp_dir, day, points)
        save_state(gp_dir, state)

    try:
        for i, job in enumerate(todo):
            left = allowed - (client.requests_made - start)
            if left <= 0:
                stopped = "budget"
                break
            try:
                res = gp.history(client, job.kind, job.appid, key, since=job.since,
                                 max_pages=min(MAX_PAGES, left))
            except Exception as e:  # noqa: BLE001 - leave the game due for the next run
                if isinstance(e, HTTPStatusError) and e.status == 429:
                    # The client already retried; a 429 that persists means the day's quota is used up.
                    log.error("rate limited (%s); stopping", e)
                    stopped = "rate_limited"
                    break
                stats["errors"] += 1
                consecutive += 1
                log.warning("%s %s failed: %s", job.kind, job.appid, e)
                if consecutive >= max_consecutive_errors:
                    stopped = "errors"
                    break
                continue
            consecutive = 0
            old = state.get((job.kind, job.appid), {})
            newest = max([t for t, _ in res.points] + ([_ts(old["last_observed_at"])] if old.get("last_observed_at") else []),
                         default=None)
            status = res.status
            if status == "ok":
                if not res.complete:
                    status = "partial"
                elif newest is not None and newest < now - timedelta(days=policy.stale_days):
                    status = "stale"
            state[(job.kind, job.appid)] = {
                "appid": str(job.appid), "kind": job.kind, "last_pulled": stamp, "status": status,
                "last_observed_at": newest.isoformat() if newest else "",
                "points": str(int(old.get("points") or 0) + len(res.points)),
            }
            points[job.kind].extend({"appid": job.appid, job.kind: v, "observed_at": t.isoformat(),
                                     "fetched_at": stamp} for t, v in res.points)
            stats["jobs"] += 1
            stats[status] += 1
            stats["points"] += len(res.points)
            if (i + 1) % checkpoint == 0:
                save()
                log.info("%d jobs, %d requests", stats["jobs"], client.requests_made - start)
    except KeyboardInterrupt:
        stopped = "interrupted"
        log.info("interrupted, saving progress")
    finally:
        save()
        row = {"date": day, "started_at": stamp, "requests": client.requests_made - start,
               "stopped": stopped, **{f: stats[f] for f in RUN_FIELDS if f in stats}}
        storage.replace_row(gp_dir / "runs.csv", {f: row.get(f, 0) for f in RUN_FIELDS}, RUN_FIELDS,
                            key="started_at")
    result = {"requests": client.requests_made - start, "stopped": stopped, **stats}
    log.info("run: %s", result)
    return result


def main(argv=None) -> int:
    p = base_parser(__doc__)
    p.add_argument("--gp-dir", type=Path, default=Path("_gp"),
                   help="state and fetched points (synced with the private dataset in CI)")
    p.add_argument("--budget", type=int, default=int(os.environ.get("GP_DAILY_BUDGET") or 900),
                   help="requests allowed per UTC day, including earlier runs that day")
    p.add_argument("--gp-interval", type=float, default=1.2, help=f"seconds between requests to {gp.HOST}")
    p.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    args = p.parse_args(argv)
    _, today = setup(args)
    now = datetime.now(timezone.utc)
    if args.today:
        now = datetime.combine(args.today, time(19), tzinfo=timezone.utc)

    snapshot = storage.read_csv(latest_snapshot_path(args.data_dir))
    history = storage.read_csv(args.data_dir / "history" / "games.csv")
    state = load_state(args.gp_dir)
    todo = plan(snapshot, history, state, now.date(), Policy())
    by_priority = collections.Counter(j.priority for j in todo)
    log.info("%d jobs due: %s (0 post-launch followers, 1 players, 2 upcoming, 3 backfill); budget %d, used today %d",
             len(todo), dict(sorted(by_priority.items())), args.budget, used_today(args.gp_dir, now.date().isoformat()))
    if args.dry_run:
        return 0
    key = os.environ.get("GP_API_KEY", "").strip()
    if not key:
        raise SystemExit("set GP_API_KEY to fetch, or use --dry-run")
    # A single 429 can be passing (seen 2026-10-11), so the client retries twice before giving up.
    client = Client(host_intervals={gp.HOST: args.gp_interval}, host_max_retries={gp.HOST: 2})
    stats = run(todo, client, key, state, args.gp_dir, now, args.budget)
    return 0 if stats["stopped"] in ("done", "budget") else 1


if __name__ == "__main__":
    raise SystemExit(main())
