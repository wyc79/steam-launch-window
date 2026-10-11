"""Games released on Steam since --since, with first-30-day review counts.

Steps:
1. List released games month by month (IStoreQueryService/Query with a
   release date filter). Cheap; refreshed every run.
2. Look up demo release dates in bulk.
3. For each game whose 30-day window has closed and has no count yet,
   ask appreviews for the number of reviews written in that window.
   Games with zero reviews in total skip the call. This step is slow
   (one request per game), so it runs until --budget-minutes and is
   saved every --checkpoint games. Rerun to continue.
4. Hidden Early Access check: for "full" launches with at least
   --prior-min-reviews reviews, count reviews written more than a week
   before launch. Steam drops Early Access flags when a game leaves EA
   and sometimes keeps no EA start date (Baldur's Gate 3), but reviews
   keep their timestamps. Any such review means the game was on sale
   before its "launch", so it is relabeled ea_exit.

Output: history/games.csv under --data-dir, one row per game.
reviews_30d_source is api, zero_total (no reviews at all, no call made), or
unavailable (Steam has no review data for the app; not retried).

Launch date and Early Access:
- Query files Early Access games that left EA under their 1.0 date.
  When Steam gives the EA start (original_steam_release_date), we use it
  as the launch date and set launch_type=early_access.
- When Steam only says the game left EA (release_from_early_access_date)
  without the start date, launch_type=ea_exit: the row is the 1.0 launch
  of a game that was already on sale. Analyses should treat these apart.
- Games still in Early Access have launch_type=early_access.
- Step 4 relabels hidden cases as ea_exit and keeps the count in
  reviews_before_launch. Games under --prior-min-reviews are not checked
  (a 200-game sample put hidden EA at about 1.5% of full launches).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from . import steam, storage
from .common import Budget, base_parser, run_pass, setup
from .http import HTTPStatusError, RateLimited

FIELDS = [
    "appid", "name", "launch_date", "launch_ts", "steam_release_ts", "launch_type",
    "early_access_now", "price_cents", "is_free", "tags", "developers", "publishers",
    "franchises", "demo_appids", "demo_release_ts", "demo_before_launch",
    "reviews_total_now", "reviews_30d", "reviews_30d_positive", "reviews_30d_source",
    "reviews_30d_fetched", "reviews_before_launch", "prior_check_fetched",
]
COUNT_FIELDS = ("reviews_30d", "reviews_30d_positive", "reviews_30d_source", "reviews_30d_fetched",
                "reviews_before_launch", "prior_check_fetched")
PRIOR_GAP = 7 * 86400  # reviews this long before launch mean the game was already on sale
DATA_REQUEST = {"include_release": True, "include_tag_count": 20, "include_basic_info": True,
                "include_reviews": True}
WINDOW = 30 * 86400
LISTING_TTL = 6 * 86400  # month listings are refetched about weekly

log = logging.getLogger("collect_history")


def month_starts(since: date, until: date):
    d = since.replace(day=1)
    while d <= until:
        yield d
        d = (d + timedelta(days=32)).replace(day=1)


def pacific_ts(d: date) -> int:
    return int(datetime.combine(d, time(0), tzinfo=steam.PACIFIC).timestamp())


def list_month(client, month: date) -> list[dict]:
    nxt = (month + timedelta(days=32)).replace(day=1)
    filters = {
        "released_only": True,
        "type_filters": steam.GAMES_ONLY,
        "release_date_filter": {"release_date_type": 1, "start_date": pacific_ts(month),
                                "end_date": pacific_ts(nxt) - 1},
    }
    return steam.store_query(client, filters, DATA_REQUEST, cache_ttl=LISTING_TTL)


def launch_info(item: dict) -> tuple[int | None, str]:
    rel = item.get("release") or {}
    ts = rel.get("steam_release_date")
    original = rel.get("original_steam_release_date")
    if original and ts and original < ts:
        return original, "early_access"
    if rel.get("is_early_access"):
        return ts, "early_access"
    if rel.get("release_from_early_access_date"):
        return ts, "ea_exit"
    return ts, "full"


def game_row(item: dict, demo_release: dict[int, int]) -> dict | None:
    launch_ts, launch_type = launch_info(item)
    if not launch_ts:
        return None
    meta = steam.meta_fields(item)
    demos = [int(d) for d in meta["demo_appids"].split("|") if d]
    demo_ts = min((demo_release[d] for d in demos if d in demo_release), default=None)
    reviews = ((item.get("reviews") or {}).get("summary_filtered") or {}).get("review_count", 0)
    return {
        "appid": item["appid"],
        "name": meta["name"],
        "launch_date": steam.pacific_date(launch_ts).isoformat(),
        "launch_ts": launch_ts,
        "steam_release_ts": (item.get("release") or {}).get("steam_release_date", ""),
        "launch_type": launch_type,
        "early_access_now": int(bool((item.get("release") or {}).get("is_early_access"))),
        "price_cents": steam.price_cents(item),
        "is_free": meta["is_free"],
        "tags": meta["tags"],
        "developers": meta["developers"],
        "publishers": meta["publishers"],
        "franchises": meta["franchises"],
        "demo_appids": meta["demo_appids"],
        "demo_release_ts": demo_ts or "",
        "demo_before_launch": "" if demo_ts is None else int(demo_ts < launch_ts),
        "reviews_total_now": reviews,
    }


def apply_prior_check(row: dict) -> dict:
    if row.get("launch_type") == "full" and str(row.get("reviews_before_launch") or "0") != "0":
        row["launch_type"] = "ea_exit"
    return row


def merge(old: dict | None, new: dict) -> dict:
    """Keep the review counts from a previous run unless the launch date moved."""
    if old and str(old.get("launch_ts")) == str(new["launch_ts"]):
        return apply_prior_check({**new, **{k: old.get(k, "") for k in COUNT_FIELDS}})
    return {**new, **{k: "" for k in COUNT_FIELDS}}


def needs_reviews(row: dict, cutoff_ts: int) -> bool:
    return row["reviews_30d_source"] == "" and int(row["launch_ts"]) + WINDOW <= cutoff_ts


def needs_prior_check(row: dict, min_reviews: int) -> bool:
    return (row["launch_type"] == "full" and not row.get("prior_check_fetched")
            and int(row["reviews_total_now"] or 0) >= min_reviews)


def is_gone(e: Exception) -> bool:
    """Errors that will repeat on every retry: Steam has no data for this app."""
    if isinstance(e, steam.Unavailable):
        return True
    return isinstance(e, HTTPStatusError) and not isinstance(e, RateLimited) and 400 <= e.status < 500


def main(argv=None) -> int:
    p = base_parser(__doc__)
    p.add_argument("--since", type=date.fromisoformat, default=date(2022, 1, 1))
    p.add_argument("--budget-minutes", type=float, default=300)
    p.add_argument("--checkpoint", type=int, default=200)
    p.add_argument("--max-consecutive-errors", type=int, default=25)
    p.add_argument("--skip-listing", action="store_true",
                   help="reuse history/games.csv as is and only fill review counts")
    p.add_argument("--prior-min-reviews", type=int, default=50,
                   help="only check full launches with at least this many reviews for hidden Early Access")
    p.add_argument("--fail-if-incomplete", action="store_true",
                   help="exit with code 3 if games still need a count (for a retry loop)")
    args = p.parse_args(argv)
    client, today = setup(args)
    budget = Budget(args.budget_minutes)
    path = args.data_dir / "history" / "games.csv"
    existing = {int(r["appid"]): r for r in storage.read_csv(path)}

    if args.skip_listing:
        if not existing:
            raise SystemExit(f"--skip-listing needs {path}, which is missing or empty")
        rows = existing
    else:
        items: dict[int, dict] = {}
        for month in month_starts(args.since, today):
            got = list_month(client, month)
            items.update((it["appid"], it) for it in got)
            log.info("%s: %d games", month.strftime("%Y-%m"), len(got))
        demo_ids = sorted({int(d) for it in items.values()
                           for d in (it.get("related_items") or {}).get("demo_appid") or []})
        demos = steam.get_items(client, demo_ids, {"include_release": True}, cache_ttl=LISTING_TTL)
        demo_release = {a: d["release"]["steam_release_date"] for a, d in demos.items()
                        if (d.get("release") or {}).get("steam_release_date")}
        since_ts = pacific_ts(args.since)
        rows = {}
        for appid, it in items.items():
            row = game_row(it, demo_release)
            if row and row["launch_ts"] >= since_ts:
                rows[appid] = merge(existing.get(appid), row)
        dropped = len(set(existing) - set(rows))
        log.info("history: %d games (%d demos looked up, %d rows dropped since last run)",
                 len(rows), len(demo_release), dropped)
        storage.write_csv(path, [rows[a] for a in sorted(rows)], FIELDS)

    cutoff_ts = pacific_ts(today)
    stamp = today.isoformat()

    def save():
        storage.write_csv(path, [rows[a] for a in sorted(rows)], FIELDS)

    def thirty_day(row):
        if int(row["reviews_total_now"] or 0) == 0:
            row.update(reviews_30d=0, reviews_30d_positive=0, reviews_30d_source="zero_total",
                       reviews_30d_fetched=stamp)
            return False
        start = int(row["launch_ts"])
        try:
            counts = steam.review_counts(client, row["appid"], start, start + WINDOW)
        except Exception as e:
            if not is_gone(e):
                raise
            log.info("no review data for %s (%s); marked unavailable", row["appid"], e)
            row.update(reviews_30d_source="unavailable", reviews_30d_fetched=stamp)
            return True
        row.update(reviews_30d=counts["total"], reviews_30d_positive=counts["positive"],
                   reviews_30d_source="api", reviews_30d_fetched=stamp)
        return True

    def prior(row):
        try:
            counts = steam.review_counts(client, row["appid"], 1, int(row["launch_ts"]) - PRIOR_GAP)
        except Exception as e:
            if not is_gone(e):
                raise
            row.update(prior_check_fetched=stamp)  # reviews_before_launch stays unknown
            return True
        row.update(reviews_before_launch=counts["total"], prior_check_fetched=stamp)
        apply_prior_check(row)
        return True

    passes = [
        ("30-day review count", thirty_day, lambda r: needs_reviews(r, cutoff_ts)),
        ("hidden Early Access check", prior, lambda r: needs_prior_check(r, args.prior_min_reviews)),
    ]
    try:
        for label, fetch, needed in passes:
            todo = sorted((r for r in rows.values() if needed(r)), key=lambda r: -int(r["launch_ts"]))
            log.info("%s: %d games", label, len(todo))
            if not run_pass(todo, fetch, label, budget, save, checkpoint=args.checkpoint,
                            max_consecutive_errors=args.max_consecutive_errors,
                            key=lambda r: r["appid"]):
                break
    except KeyboardInterrupt:
        log.info("interrupted, saving progress")
    finally:
        save()
    left = {label: sum(1 for r in rows.values() if needed(r)) for label, _, needed in passes}
    relabeled = sum(1 for r in rows.values() if str(r.get("reviews_before_launch") or "0") != "0")
    log.info("done: still to do %s; %d hidden Early Access games found so far", left, relabeled)
    return 3 if args.fail_if_incomplete and any(left.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
