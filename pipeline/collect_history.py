"""Games released on Steam since --since, with first-30-day review counts.

Steps:
1. List released games month by month (IStoreQueryService/Query with a
   release date filter). Cheap; refreshed every run.
2. Look up demo release dates in bulk.
3. For each game whose 30-day window has closed and has no count yet,
   ask Steam (IUserReviewsService/GetAppReviews) for the number of reviews
   written in that window.
   Games with zero reviews in total skip the call. This step is slow
   (one request per game), so it runs until --budget-minutes and is
   saved every --checkpoint games. Rerun to continue.
4. Hidden Early Access check: for "full" launches with at least
   --prior-min-reviews reviews, count reviews written more than a week
   before launch. Steam drops Early Access flags when a game leaves EA
   and sometimes keeps no EA start date (Baldur's Gate 3), but reviews
   keep their timestamps. Any such review means the game was on sale
   before its "launch", so it is relabeled ea_exit.

5. First-day and first-week review counts (reviews_1d, reviews_7d) for games
   launched on or after --early-since, once their first week has closed.
   Games with no reviews in their first 30 days get 0 without a request.

Output: history/games.csv under --data-dir, one row per game.
reviews_30d_source is api, zero_total (no reviews at all, no call made), or
unavailable (Steam has no review data for the app; retried after 90 days).
reviews_purchase says whose reviews the counts include: "steam" (bought on
Steam, the store's own count) for paid games, "all" for free games (Steam's
free flag or "Free to Play" in the top 10 tags), whose players buy nothing.
Rows counted before this column existed have it empty, which means "steam".
At the start of each run, a free game whose counts are on the "steam" basis
loses the ones a pass of this run will count again (its 30-day count, its
first-week counts, and a pre-launch count of 0) and is marked "all"; an
interrupted run goes on where it stopped. A pre-launch count above 0 stays as a
lower bound (counting everyone can only add), and so does its ea_exit label.
The column is set per row when it is counted, so trust it over is_free: a game
that turns paid later keeps "all" counts from its free days.

Rows are never dropped. A game that is no longer listed (delisted, or missed
by one listing) keeps its row; last_listed says when it was last seen, and
first_listed when it first appeared. Rows from before these columns get the
date of the first listing run that adds them; rows no longer listed by then
keep both empty.

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
    "franchises", "languages", "audio_languages", "demo_appids", "demo_release_ts",
    "demo_before_launch",
    "reviews_total_now", "reviews_30d", "reviews_30d_positive", "reviews_30d_source",
    "reviews_30d_fetched", "reviews_before_launch", "prior_check_fetched",
    "reviews_1d", "reviews_7d", "reviews_early_fetched", "first_listed", "last_listed",
    "reviews_purchase",
]
COUNT_FIELDS = ("reviews_30d", "reviews_30d_positive", "reviews_30d_source", "reviews_30d_fetched",
                "reviews_before_launch", "prior_check_fetched",
                "reviews_1d", "reviews_7d", "reviews_early_fetched", "reviews_purchase")
PRIOR_GAP = 7 * 86400  # reviews this long before launch mean the game was already on sale
DATA_REQUEST = {"include_release": True, "include_tag_count": 20, "include_basic_info": True,
                "include_supported_languages": True,
                "include_reviews": True}
WINDOW = 30 * 86400
EARLY_WINDOWS = {"reviews_1d": 86400, "reviews_7d": 7 * 86400}
UNAVAILABLE_RETRY_DAYS = 90
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
    demo_ts = steam.first_demo(steam.demo_appids(item), demo_release)
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
        "languages": meta["languages"],
        "audio_languages": meta["audio_languages"],
        "demo_appids": meta["demo_appids"],
        "demo_release_ts": demo_ts or "",
        "demo_before_launch": "" if demo_ts is None else int(demo_ts < launch_ts),
        "reviews_total_now": reviews,
    }


def apply_prior_check(row: dict) -> dict:
    if row.get("launch_type") == "full" and str(row.get("reviews_before_launch") or "0") != "0":
        row["launch_type"] = "ea_exit"
    return row


def merge(old: dict | None, new: dict, today: str = "") -> dict:
    """Keep the review counts from a previous run unless the launch date moved."""
    listed = {"first_listed": (old or {}).get("first_listed") or today, "last_listed": today}
    if old and str(old.get("launch_ts")) == str(new["launch_ts"]):
        return apply_prior_check({**new, **{k: old.get(k, "") for k in COUNT_FIELDS}, **listed})
    return {**new, **{k: "" for k in COUNT_FIELDS}, **listed}


def is_free(row: dict) -> bool:
    return steam.free_game(row.get("is_free"), steam.tag_ids(row.get("tags")))


def purchase(row: dict) -> tuple[int, str]:
    """Whose reviews to count for this game, as (API value, reviews_purchase label)."""
    return (steam.PURCHASE_ALL, "all") if is_free(row) else (steam.PURCHASE_STEAM, "steam")


def to_all_reviews(row: dict, early_since_ts: int, prior_min: int) -> bool:
    """For a free game still counted on the "steam" basis: drop the counts that basis got
    wrong and that a pass of this run will count again with everyone's reviews, and mark
    the row "all". First-week counts are only redone from early_since_ts on, and the
    hidden Early Access check only for full launches with prior_min reviews, so other
    rows keep theirs. A pre-launch count above 0 stays (counting everyone can only raise
    it), and so does the launch type it set. True if a count was dropped."""
    if not is_free(row) or row.get("reviews_purchase") == "all":
        return False
    dropped = False
    if row.get("reviews_30d_source") == "api":
        row.update(reviews_30d="", reviews_30d_positive="", reviews_30d_source="", reviews_30d_fetched="")
        dropped = True
    if row.get("reviews_early_fetched") and int(row["launch_ts"]) >= early_since_ts:
        row.update(reviews_1d="", reviews_7d="", reviews_early_fetched="")
        dropped = True
    if (row.get("prior_check_fetched") and str(row.get("reviews_before_launch") or "0") == "0"
            and row.get("launch_type") == "full" and int(row.get("reviews_total_now") or 0) >= prior_min):
        row.update(reviews_before_launch="", prior_check_fetched="")
        dropped = True
    row["reviews_purchase"] = "all"
    return dropped


def needs_reviews(row: dict, cutoff_ts: int, today: date | None = None) -> bool:
    if int(row["launch_ts"]) + WINDOW > cutoff_ts:
        return False
    source = row.get("reviews_30d_source", "")
    if source == "":
        return True
    fetched = row.get("reviews_30d_fetched")
    return (source == "unavailable" and today is not None and bool(fetched)
            and (today - date.fromisoformat(fetched)).days >= UNAVAILABLE_RETRY_DAYS)


def needs_early(row: dict, cutoff_ts: int, since_ts: int) -> bool:
    launch = int(row["launch_ts"])
    return not row.get("reviews_early_fetched") and launch >= since_ts and launch + EARLY_WINDOWS["reviews_7d"] <= cutoff_ts


def needs_prior_check(row: dict, min_reviews: int) -> bool:
    return (row["launch_type"] == "full" and not row.get("prior_check_fetched")
            and int(row["reviews_total_now"] or 0) >= min_reviews)


def is_gone(e: Exception) -> bool:
    """Errors that will repeat on every retry: Steam has no data for this app."""
    if isinstance(e, steam.Unavailable):
        return True
    # A 429 that outlasted the retries is a rate limit, not a missing app: marking the game
    # would record unknown counts as done (or delay it 90 days).
    return isinstance(e, HTTPStatusError) and not isinstance(e, RateLimited) and 400 <= e.status < 500         and e.status != 429


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
    p.add_argument("--early-since", type=date.fromisoformat, default=date(2026, 10, 1),
                   help="first-day and first-week review counts for games launched on or after this date")
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
        demo_release = steam.demo_release(client, items.values(), cache_ttl=LISTING_TTL)
        since_ts = pacific_ts(args.since)
        rows = {}
        for appid, it in items.items():
            row = game_row(it, demo_release)
            if row and row["launch_ts"] >= since_ts:
                rows[appid] = merge(existing.get(appid), row, today.isoformat())
        unlisted = set(existing) - set(rows)
        for appid in unlisted:  # keep, with its old last_listed, so collected counts are not lost
            rows[appid] = existing[appid]
        log.info("history: %d games (%d demos looked up, %d no longer listed but kept)",
                 len(rows), len(demo_release), len(unlisted))
        storage.write_csv(path, [rows[a] for a in sorted(rows)], FIELDS)

    cutoff_ts = pacific_ts(today)
    stamp = today.isoformat()
    moved = sum(to_all_reviews(r, pacific_ts(args.early_since), args.prior_min_reviews) for r in rows.values())
    if moved:
        log.info("%d free games were counted with Steam purchases only: counting them again with all reviews", moved)

    def save():
        storage.write_csv(path, [rows[a] for a in sorted(rows)], FIELDS)

    def thirty_day(row):
        kind, label = purchase(row)
        if int(row["reviews_total_now"] or 0) == 0:
            row.update(reviews_30d=0, reviews_30d_positive=0, reviews_30d_source="zero_total",
                       reviews_30d_fetched=stamp, reviews_purchase=label)
            return False
        start = int(row["launch_ts"])
        try:
            counts = steam.review_counts(client, row["appid"], start, start + WINDOW, kind)
        except Exception as e:
            if not is_gone(e):
                raise
            log.info("no review data for %s (%s); marked unavailable", row["appid"], e)
            row.update(reviews_30d_source="unavailable", reviews_30d_fetched=stamp)
            return True
        row.update(reviews_30d=counts["total"], reviews_30d_positive=counts["positive"],
                   reviews_30d_source="api", reviews_30d_fetched=stamp, reviews_purchase=label)
        return True

    def early(row):
        if int(row["reviews_total_now"] or 0) == 0 or (
                row.get("reviews_30d_source") in ("api", "zero_total") and str(row.get("reviews_30d")) == "0"):
            row.update(reviews_1d=0, reviews_7d=0, reviews_early_fetched=stamp)
            return False
        start = int(row["launch_ts"])
        try:
            got = {field: steam.review_counts(client, row["appid"], start, start + span, purchase(row)[0])["total"]
                   for field, span in EARLY_WINDOWS.items()}
        except Exception as e:
            if not is_gone(e):
                raise
            row.update(reviews_early_fetched=stamp)  # counts stay unknown
            return True
        row.update(**got, reviews_early_fetched=stamp)
        return True

    def prior(row):
        try:
            counts = steam.review_counts(client, row["appid"], 1, int(row["launch_ts"]) - PRIOR_GAP, purchase(row)[0])
        except Exception as e:
            if not is_gone(e):
                raise
            row.update(prior_check_fetched=stamp)  # reviews_before_launch stays unknown
            return True
        row.update(reviews_before_launch=counts["total"], prior_check_fetched=stamp)
        apply_prior_check(row)
        return True

    passes = [
        ("30-day review count", thirty_day, lambda r: needs_reviews(r, cutoff_ts, today)),
        ("first-day and first-week review counts", early,
         lambda r: needs_early(r, cutoff_ts, pacific_ts(args.early_since))),
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
