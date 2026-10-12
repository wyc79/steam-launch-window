from datetime import date, datetime, timezone

import pytest

from pipeline import collect_followers as cf
from pipeline import common, steam
from pipeline.http import HTTPStatusError, RateLimited
from pipeline import collect_history as ch
from pipeline import collect_upcoming as cu
from pipeline import storage

TODAY = date(2026, 10, 11)
NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
POLICY = cf.Policy()


def snap(appid, d="", end="", rank="", precision=None):
    if precision is None:
        precision = "day" if d and d == end else ("unknown" if not d else "month")
    return {"appid": str(appid), "date": d, "date_end": end, "wishlist_rank": str(rank), "precision": precision}


# -- followers ---------------------------------------------------------------

def test_tier_by_when_the_whole_range_ends():
    assert cf.tier_for(snap(1, "2026-10-20", "2026-10-20"), None, TODAY, POLICY) == 0
    assert cf.tier_for(snap(1, "2026-11-01", "2026-11-30"), None, TODAY, POLICY) == 0  # November ends by week 8
    assert cf.tier_for(snap(1, "2027-01-01", "2027-01-31"), None, TODAY, POLICY) == 1
    assert cf.tier_for(snap(1, "2027-01-15", "2027-01-15"), None, TODAY, POLICY) == 1


def test_untracked_games():
    assert cf.tier_for(snap(1), None, TODAY, POLICY) is None                                      # TBA
    assert cf.tier_for(snap(1, "2027-06-01", "2027-06-30"), None, TODAY, POLICY) is None          # past week 26
    assert cf.tier_for(snap(1, "2026-10-01", "2026-12-31", precision="quarter"), None, TODAY, POLICY) is None
    assert cf.tier_for(snap(1, "2026-01-01", "2026-12-31", precision="year"), None, TODAY, POLICY) is None


def test_ranked_games_are_always_tracked():
    assert cf.tier_for(snap(1, rank=40), None, TODAY, POLICY) == 2
    assert cf.tier_for(snap(1, "2026-01-01", "2026-12-31", rank=40, precision="year"), None, TODAY, POLICY) == 2
    assert cf.tier_for(snap(1, "2026-10-20", "2026-10-20", rank=40), None, TODAY, POLICY) == 0


def test_tier_high_followers_and_overdue_dates_are_daily():
    assert cf.tier_for(snap(1, rank=40), POLICY.high_followers, TODAY, POLICY) == 0
    assert cf.tier_for(snap(1, "2026-09-01", "2026-09-01"), None, TODAY, POLICY) == 0


def test_plan_skips_fresh_and_untracked_and_orders_by_tier_then_staleness():
    snapshot = [snap(1, rank=7), snap(2, "2026-10-20", "2026-10-20"), snap(3, "2026-10-20", "2026-10-20"),
                snap(4, "2026-10-20", "2026-10-20"), snap(5)]
    latest = {
        2: {"followers": "5", "fetched_at": "2026-10-10T08:00:00+00:00"},  # 28h old, due daily
        3: {"followers": "5", "fetched_at": "2026-10-11T06:00:00+00:00"},  # 6h old, fresh
        1: {"followers": "5", "fetched_at": "2026-10-01T00:00:00+00:00"},  # ranked TBA, 10 days, due weekly
    }
    assert cf.plan(snapshot, latest, NOW, POLICY) == [(0, 4), (0, 2), (2, 1)]


def test_plan_slack_lets_a_slightly_early_daily_run_refresh():
    latest = {1: {"followers": "5", "fetched_at": "2026-10-10T13:00:00+00:00"}}  # 23h old
    assert cf.plan([snap(1, "2026-10-20", "2026-10-20")], latest, NOW, POLICY) == [(0, 1)]


# -- history -----------------------------------------------------------------

def test_launch_info_variants():
    assert ch.launch_info({"release": {"steam_release_date": 200}}) == (200, "full")
    assert ch.launch_info({"release": {"steam_release_date": 200, "original_steam_release_date": 100}}) == (100, "early_access")
    assert ch.launch_info({"release": {"steam_release_date": 200, "is_early_access": True}}) == (200, "early_access")
    assert ch.launch_info({"release": {"steam_release_date": 200, "release_from_early_access_date": 199}}) == (200, "ea_exit")


def test_game_row_demo_before_launch():
    item = {"appid": 7, "name": "X", "release": {"steam_release_date": 1_700_000_000},
            "related_items": {"demo_appid": [8]},
            "reviews": {"summary_filtered": {"review_count": 12}}}
    row = ch.game_row(item, {8: 1_690_000_000})
    assert row["demo_before_launch"] == 1
    assert row["reviews_total_now"] == 12
    assert ch.game_row({**item, "related_items": {}}, {})["demo_before_launch"] == ""


def test_merge_keeps_counts_unless_launch_moved():
    old = {"launch_ts": "100", "reviews_30d": "5", "reviews_30d_positive": "4",
           "reviews_30d_source": "api", "reviews_30d_fetched": "2026-01-01"}
    assert ch.merge(old, {"launch_ts": 100})["reviews_30d"] == "5"
    assert ch.merge(old, {"launch_ts": 101})["reviews_30d"] == ""


def test_prior_reviews_relabel_full_launch_as_ea_exit():
    assert ch.apply_prior_check({"launch_type": "full", "reviews_before_launch": "61331"})["launch_type"] == "ea_exit"
    assert ch.apply_prior_check({"launch_type": "full", "reviews_before_launch": "0"})["launch_type"] == "full"
    assert ch.apply_prior_check({"launch_type": "full", "reviews_before_launch": ""})["launch_type"] == "full"
    assert ch.apply_prior_check({"launch_type": "early_access", "reviews_before_launch": "5"})["launch_type"] == "early_access"


def test_merge_keeps_prior_check_so_relisting_does_not_undo_the_relabel():
    old = {"launch_ts": "100", "reviews_before_launch": "12", "prior_check_fetched": "2026-10-11"}
    row = ch.merge(old, {"launch_ts": 100, "launch_type": "full"})
    assert (row["launch_type"], row["reviews_before_launch"]) == ("ea_exit", "12")


def test_needs_prior_check():
    row = {"launch_type": "full", "prior_check_fetched": "", "reviews_total_now": "50"}
    assert ch.needs_prior_check(row, 50)
    assert not ch.needs_prior_check({**row, "reviews_total_now": "49"}, 50)
    assert not ch.needs_prior_check({**row, "prior_check_fetched": "2026-10-11"}, 50)
    assert not ch.needs_prior_check({**row, "launch_type": "early_access"}, 50)
    assert ch.needs_prior_check({k: v for k, v in row.items() if k != "prior_check_fetched"}, 50)  # old file


class NeverExpires:
    def expired(self):
        return False


def run(todo, fetch, saves):
    return common.run_pass(todo, fetch, "test", NeverExpires(), lambda: saves.append(1),
                           checkpoint=2, max_consecutive_errors=2)


def test_run_pass_checkpoints_and_stops_on_repeated_errors():
    saves = []

    def fetch(i):
        if i >= 3:
            raise RuntimeError("boom")
        return True

    assert run(list(range(1, 6)), fetch, saves) is False
    assert saves == [1]  # one checkpoint after 2 fetches, then 2 errors in a row stop it


def test_run_pass_stops_at_the_first_rate_limit():
    calls = []

    def fetch(i):
        calls.append(i)
        raise RateLimited("https://steamcommunity.com/x")

    assert run([1, 2, 3], fetch, []) is False
    assert calls == [1]


def test_run_pass_skips_single_errors_and_finishes():
    def fetch(i):
        if i == 2:
            raise RuntimeError("one bad item")
        return True

    assert run([1, 2, 3], fetch, []) is True


@pytest.mark.parametrize("err, gone", [
    (steam.Unavailable("no data"), True),
    (HTTPStatusError(404, "u"), True),
    (HTTPStatusError(403, "u"), True),
    (HTTPStatusError(503, "u"), False),
    (HTTPStatusError(429, "u"), False),  # rate limit that outlasted the retries
    (RateLimited("u"), False),
    (RuntimeError("network"), False),
])
def test_is_gone(err, gone):
    assert ch.is_gone(err) is gone


def test_unavailable_rows_are_retried_only_after_90_days():
    row = {"reviews_30d": "", "reviews_30d_source": "unavailable", "launch_ts": "1000",
           "reviews_30d_fetched": "2026-07-14"}
    assert not ch.needs_reviews(row, 10**10, date(2026, 10, 11))  # 89 days ago
    assert ch.needs_reviews(row, 10**10, date(2026, 10, 12))      # 90 days ago
    assert not ch.needs_reviews({**row, "reviews_30d_fetched": ""}, 10**10, date(2026, 10, 12))


def test_skip_listing_without_file_fails_loudly(tmp_path):
    with pytest.raises(SystemExit, match="missing or empty"):
        ch.main(["--data-dir", str(tmp_path), "--skip-listing", "--cache-dir", str(tmp_path / "c")])


def test_needs_reviews_waits_for_window_to_close():
    row = {"reviews_30d": "", "reviews_30d_source": "", "launch_ts": "1000"}
    assert not ch.needs_reviews(row, 1000 + ch.WINDOW - 1)
    assert ch.needs_reviews(row, 1000 + ch.WINDOW)
    assert not ch.needs_reviews({**row, "reviews_30d": "0", "reviews_30d_source": "zero_total"}, 10**10)


def test_month_starts():
    assert list(ch.month_starts(date(2025, 11, 15), date(2026, 1, 2))) == [
        date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1)]


# -- upcoming ----------------------------------------------------------------

def test_build_snapshot_attaches_wishlist_rank():
    items = [{"appid": 5, "release": {"coming_soon_display": "text_tba"}},
             {"appid": 3, "release": {"coming_soon_display": "date_year", "steam_release_date": 1830240000},
              "best_purchase_option": {"final_price_in_cents": "1999"}}]
    rows = cu.build_snapshot(items, [3, 99])
    assert [(r["appid"], r["wishlist_rank"], r["precision"], r["price_cents"]) for r in rows] == [
        (3, 1, "year", 1999), (5, "", "unknown", "")]


def test_merge_apps_keeps_first_seen():
    existing = [{"appid": "3", "name": "Old", "first_seen": "2026-01-01"}]
    rows = cu.merge_apps(existing, [{"appid": 3, "name": "New"}, {"appid": 4, "name": "B"}], "2026-10-11")
    assert [(r["appid"], r["name"], r["first_seen"]) for r in rows] == [
        (3, "New", "2026-01-01"), (4, "B", "2026-10-11")]


# -- storage -----------------------------------------------------------------

def test_csv_round_trip_and_deterministic_gzip(tmp_path):
    rows = [{"a": 1, "b": "x,y"}, {"a": 2, "b": ""}]
    storage.write_csv(tmp_path / "t.csv.gz", rows, ["a", "b"])
    first = (tmp_path / "t.csv.gz").read_bytes()
    storage.write_csv(tmp_path / "t.csv.gz", rows, ["a", "b"])
    assert (tmp_path / "t.csv.gz").read_bytes() == first
    assert storage.read_csv(tmp_path / "t.csv.gz") == [{"a": "1", "b": "x,y"}, {"a": "2", "b": ""}]
    assert storage.read_csv(tmp_path / "missing.csv") == []


def test_replace_row_keeps_one_row_per_key(tmp_path):
    path = tmp_path / "runs.csv"
    storage.replace_row(path, {"date": "2026-10-11", "n": 1}, ["date", "n"], key="date")
    storage.replace_row(path, {"date": "2026-10-12", "n": 2}, ["date", "n"], key="date")
    storage.replace_row(path, {"date": "2026-10-11", "n": 3}, ["date", "n"], key="date")
    assert storage.read_csv(path) == [{"date": "2026-10-11", "n": "3"}, {"date": "2026-10-12", "n": "2"}]


def test_merge_apps_records_last_seen():
    existing = [{"appid": "3", "name": "Old", "first_seen": "2026-01-01", "last_seen": "2026-01-05"},
                {"appid": "9", "name": "Launched", "first_seen": "2026-01-01", "last_seen": "2026-02-01"}]
    rows = cu.merge_apps(existing, [{"appid": 3, "name": "New"}], "2026-10-11")
    assert [(str(r["appid"]), r["last_seen"]) for r in rows] == [("3", "2026-10-11"), ("9", "2026-02-01")]


def _fake_upcoming(monkeypatch, ranking):
    items = [{"appid": 5, "name": "A", "release": {"coming_soon_display": "text_tba"}}]
    monkeypatch.setattr(steam, "tag_list", lambda client: ("v", {492: "Indie"}))
    monkeypatch.setattr(steam, "store_query", lambda *a, **k: items)
    monkeypatch.setattr(steam, "wishlist_ranking", ranking)


def test_upcoming_keeps_the_snapshot_when_the_wishlist_crawl_fails(tmp_path, monkeypatch):
    def broken(client, cache_ttl=None):
        raise HTTPStatusError(429, "https://store.steampowered.com/search/results/")
    _fake_upcoming(monkeypatch, broken)
    code = cu.main(["--data-dir", str(tmp_path), "--cache-dir", str(tmp_path / "c"), "--today", "2026-10-11"])
    assert code == 1  # the job still fails, so GitHub reports it
    snap = storage.read_csv(tmp_path / "upcoming/snapshots/2026-10-11.csv.gz")
    assert [(r["appid"], r["wishlist_rank"]) for r in snap] == [("5", "")]
    runs = storage.read_csv(tmp_path / "upcoming/runs.csv")
    assert runs[0]["ranking_ok"] == "0"


def test_upcoming_rerun_replaces_the_days_run_row(tmp_path, monkeypatch):
    _fake_upcoming(monkeypatch, lambda client, cache_ttl=None: [5])
    args = ["--data-dir", str(tmp_path), "--cache-dir", str(tmp_path / "c"), "--today", "2026-10-11"]
    assert cu.main(args) == 0 and cu.main(args) == 0
    runs = storage.read_csv(tmp_path / "upcoming/runs.csv")
    assert len(runs) == 1 and runs[0]["ranking_ok"] == "1" and runs[0]["ranked"] == "1"


# -- history: listing merge and early review windows ---------------------------

def _item(appid, ts, reviews=5):
    return {"appid": appid, "name": f"G{appid}", "release": {"steam_release_date": ts},
            "reviews": {"summary_filtered": {"review_count": reviews}}}


def _run_history(tmp_path, monkeypatch, listed, existing=(), counts=None, extra=()):
    monkeypatch.setattr(ch, "list_month", lambda client, month: listed if month.month == 9 else [])
    monkeypatch.setattr(steam, "get_items", lambda *a, **k: {})
    calls = []

    def review_counts(client, appid, start, end, purchase_type=steam.PURCHASE_STEAM):
        calls.append((int(appid), end - start) if purchase_type == steam.PURCHASE_STEAM
                     else (int(appid), end - start, "all"))
        return (counts or {}).get((int(appid), end - start), {"total": 3, "positive": 2, "negative": 1})
    monkeypatch.setattr(steam, "review_counts", review_counts)
    path = tmp_path / "history" / "games.csv"
    if existing:
        storage.write_csv(path, list(existing), ch.FIELDS)
    ch.main(["--data-dir", str(tmp_path), "--cache-dir", str(tmp_path / "c"), "--since", "2026-09-01",
             "--today", "2026-10-20", *extra])
    return {r["appid"]: r for r in storage.read_csv(path)}, calls


SEP_1 = 1788246000  # 2026-09-01 00:00 Pacific
SEP_5 = SEP_1 + 4 * 86400


def test_history_keeps_rows_that_drop_out_of_the_listing(tmp_path, monkeypatch):
    gone = {"appid": 99, "name": "Delisted", "launch_date": "2026-09-02", "launch_ts": SEP_1 + 86400,
            "launch_type": "full", "reviews_total_now": 4, "reviews_30d": 4, "reviews_30d_source": "api",
            "reviews_30d_fetched": "2026-10-03", "first_listed": "2026-10-01", "last_listed": "2026-10-10"}
    rows, _ = _run_history(tmp_path, monkeypatch, [_item(7, SEP_5)], existing=[gone])
    assert rows["99"]["reviews_30d"] == "4" and rows["99"]["last_listed"] == "2026-10-10"
    assert rows["7"]["first_listed"] == "2026-10-20" and rows["7"]["last_listed"] == "2026-10-20"


def test_history_first_listed_survives_relisting(tmp_path, monkeypatch):
    old = {"appid": 7, "launch_ts": SEP_5, "launch_type": "full", "first_listed": "2026-10-01",
           "reviews_30d_source": "api", "reviews_30d": 3}
    rows, _ = _run_history(tmp_path, monkeypatch, [_item(7, SEP_5)], existing=[old])
    assert rows["7"]["first_listed"] == "2026-10-01" and rows["7"]["last_listed"] == "2026-10-20"


def test_early_review_windows_for_new_launches(tmp_path, monkeypatch):
    counts = {(7, 86400): {"total": 1, "positive": 1, "negative": 0},
              (7, 7 * 86400): {"total": 2, "positive": 2, "negative": 0}}
    rows, calls = _run_history(tmp_path, monkeypatch, [_item(7, SEP_5)], counts=counts,
                               extra=["--early-since", "2026-09-01"])
    assert (rows["7"]["reviews_1d"], rows["7"]["reviews_7d"]) == ("1", "2")
    assert rows["7"]["reviews_early_fetched"] == "2026-10-20"
    assert sorted(w for a, w in calls if a == 7) == [86400, 7 * 86400, 30 * 86400]


def test_early_review_windows_skip_requests_when_30_day_count_is_zero(tmp_path, monkeypatch):
    rows, calls = _run_history(tmp_path, monkeypatch, [_item(7, SEP_5, reviews=0)],
                               extra=["--early-since", "2026-09-01"])
    assert (rows["7"]["reviews_1d"], rows["7"]["reviews_7d"]) == ("0", "0")
    assert calls == []


def test_early_review_windows_only_after_early_since(tmp_path, monkeypatch):
    rows, calls = _run_history(tmp_path, monkeypatch, [_item(7, SEP_5)], extra=["--early-since", "2026-10-01"])
    assert rows["7"]["reviews_1d"] == "" and [w for _, w in calls] == [30 * 86400]


def test_history_reads_an_older_format_file_without_losing_data(tmp_path, monkeypatch):
    old_header = ("appid,name,launch_date,launch_ts,steam_release_ts,launch_type,early_access_now,price_cents,"
                  "is_free,tags,developers,publishers,franchises,demo_appids,demo_release_ts,demo_before_launch,"
                  "reviews_total_now,reviews_30d,reviews_30d_positive,reviews_30d_source,reviews_30d_fetched\n")
    path = tmp_path / "history" / "games.csv"
    path.parent.mkdir(parents=True)
    path.write_text(old_header +
                    f"7,G7,2026-09-05,{SEP_5},,full,0,,0,,,,,,,,5,4,3,api,2026-10-06\n"
                    f"99,Gone,2026-09-02,{SEP_1 + 86400},,full,0,,0,,,,,,,,2,2,2,api,2026-10-03\n")
    rows, calls = _run_history(tmp_path, monkeypatch, [_item(7, SEP_5)])
    assert (rows["7"]["reviews_30d"], rows["7"]["first_listed"]) == ("4", "2026-10-20")
    assert (rows["99"]["reviews_30d"], rows["99"]["first_listed"]) == ("2", "")
    assert [w for _, w in calls] == []  # counts already there, nothing refetched
    assert set(ch.FIELDS) <= set(rows["7"])


def test_run_pass_stops_when_a_429_outlasts_the_retries():
    calls = []

    def fetch(i):
        calls.append(i)
        raise HTTPStatusError(429, "https://api.steampowered.com/x")

    assert run([1, 2, 3], fetch, []) is False
    assert calls == [1]


def test_history_rate_limit_leaves_the_game_due_instead_of_unavailable(tmp_path, monkeypatch):
    def limited(client, appid, start, end, purchase_type=steam.PURCHASE_STEAM):
        raise HTTPStatusError(429, "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/")

    monkeypatch.setattr(ch, "list_month", lambda client, month: [_item(7, SEP_5)] if month.month == 9 else [])
    monkeypatch.setattr(steam, "get_items", lambda *a, **k: {})
    monkeypatch.setattr(steam, "review_counts", limited)
    ch.main(["--data-dir", str(tmp_path), "--cache-dir", str(tmp_path / "c"), "--since", "2026-09-01",
             "--today", "2026-10-20", "--early-since", "2026-09-01"])
    row = storage.read_csv(tmp_path / "history" / "games.csv")[0]
    assert (row["reviews_30d_source"], row["reviews_30d_fetched"], row["reviews_early_fetched"]) == ("", "", "")
    assert ch.needs_reviews(row, ch.pacific_ts(date(2026, 10, 20)), date(2026, 10, 20))


def _free_item(appid, ts, reviews=5, flag=True, tags=None):
    item = _item(appid, ts, reviews)
    item["is_free"] = flag
    if tags:
        item["tags"] = [{"tagid": t, "weight": 10 - i} for i, t in enumerate(tags)]
    return item


def test_history_counts_all_reviews_for_free_games(tmp_path, monkeypatch):
    listed = [_free_item(7, SEP_5), _free_item(8, SEP_5, flag=False, tags=[492, 113]), _item(9, SEP_5)]
    rows, calls = _run_history(tmp_path, monkeypatch, listed)
    window = ch.WINDOW
    assert (7, window, "all") in calls and (8, window, "all") in calls  # Steam's flag, or the Free to Play tag
    assert (9, window) in calls                                          # paid: Steam purchases only
    assert [rows[a]["reviews_purchase"] for a in ("7", "8", "9")] == ["all", "all", "steam"]


def test_history_recounts_free_games_counted_with_purchases_only(tmp_path, monkeypatch):
    old = {"appid": 7, "name": "G7", "launch_date": "2026-09-05", "launch_ts": SEP_5, "launch_type": "full",
           "is_free": 1, "reviews_total_now": 900, "reviews_30d": 0, "reviews_30d_positive": 0,
           "reviews_30d_source": "api", "reviews_30d_fetched": "2026-10-10", "reviews_before_launch": 0,
           "prior_check_fetched": "2026-10-10", "reviews_1d": 0, "reviews_7d": 0,
           "reviews_early_fetched": "2026-10-10", "first_listed": "2026-10-01", "last_listed": "2026-10-10"}
    paid = {**old, "appid": 9, "name": "G9", "is_free": 0}
    rows, calls = _run_history(tmp_path, monkeypatch, [_free_item(7, SEP_5, 900), _item(9, SEP_5, 900)],
                               existing=[old, paid], extra=["--early-since", "2026-09-01"])
    free = rows["7"]
    assert (free["reviews_30d"], free["reviews_purchase"], free["reviews_30d_fetched"]) == ("3", "all", "2026-10-20")
    assert [c for c in calls if c[0] == 7] == [(7, ch.WINDOW, "all"), (7, 86400, "all"), (7, 7 * 86400, "all"),
                                               (7, SEP_5 - ch.PRIOR_GAP - 1, "all")]
    assert free["reviews_7d"] == "3" and free["reviews_before_launch"] == "3"
    assert not [c for c in calls if c[0] == 9]   # paid rows counted before the column existed stay as they are
    assert rows["9"]["reviews_purchase"] == "" and rows["9"]["reviews_30d"] == "0"
    # and a second run does not count the free game again
    _, again = _run_history(tmp_path, monkeypatch, [_free_item(7, SEP_5, 900), _item(9, SEP_5, 900)])
    assert not [c for c in again if c[0] == 7]


OCT_2 = SEP_1 + 31 * 86400  # 2026-10-02 00:00 Pacific


def test_history_fixes_free_games_whose_30_day_window_is_still_open(tmp_path, monkeypatch):
    # counted on the old basis before its 30-day window closed: only the first-week counts exist
    young = {"appid": 7, "name": "G7", "launch_date": "2026-10-02", "launch_ts": OCT_2, "launch_type": "full",
             "is_free": 1, "reviews_total_now": 40, "reviews_1d": 0, "reviews_7d": 0,
             "reviews_early_fetched": "2026-10-12", "first_listed": "2026-10-03", "last_listed": "2026-10-12"}
    monkeypatch.setattr(ch, "list_month", lambda client, month: [])
    rows, calls = _run_history(tmp_path, monkeypatch, [], existing=[young],
                               extra=["--skip-listing", "--early-since", "2026-09-01"])
    row = rows["7"]
    assert calls == [(7, 86400, "all"), (7, 7 * 86400, "all")]  # no 30-day count yet: its window is open
    assert (row["reviews_7d"], row["reviews_purchase"], row["reviews_30d_source"]) == ("3", "all", "")


def test_history_keeps_a_free_games_nonzero_prelaunch_count_and_its_label(tmp_path, monkeypatch):
    relabeled = {"appid": 7, "name": "G7", "launch_date": "2026-09-05", "launch_ts": SEP_5, "launch_type": "ea_exit",
                 "is_free": 1, "reviews_total_now": 900, "reviews_30d": 1, "reviews_30d_positive": 1,
                 "reviews_30d_source": "api", "reviews_30d_fetched": "2026-10-10", "reviews_before_launch": 12,
                 "prior_check_fetched": "2026-10-10", "first_listed": "2026-10-01", "last_listed": "2026-10-10"}
    rows, calls = _run_history(tmp_path, monkeypatch, [], existing=[relabeled], extra=["--skip-listing"])
    row = rows["7"]
    assert calls == [(7, ch.WINDOW, "all")]  # counting everyone can only raise 12: no new check
    assert (row["launch_type"], row["reviews_before_launch"], row["reviews_30d"]) == ("ea_exit", "12", "3")


def test_free_game_uses_the_heaviest_tags_with_ties_by_id():
    assert steam.tag_ids("5:1|113:1|9:2") == [9, 5, 113]
    many = "|".join(f"{t}:10" for t in range(1, 11)) + "|113:10"  # 113 is 11th once ties go by id
    assert not steam.free_game(0, steam.tag_ids(many))
    assert steam.free_game(1, []) and steam.free_game("1", [])
    assert ch.is_free({"is_free": "0", "tags": "113:50|492:10"})
