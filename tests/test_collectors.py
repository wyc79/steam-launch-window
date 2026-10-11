from datetime import date, datetime, timezone

from pipeline import collect_followers as cf
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
    row = {"launch_type": "full", "reviews_before_launch": "", "reviews_total_now": "50"}
    assert ch.needs_prior_check(row, 50)
    assert not ch.needs_prior_check({**row, "reviews_total_now": "49"}, 50)
    assert not ch.needs_prior_check({**row, "reviews_before_launch": "0"}, 50)
    assert not ch.needs_prior_check({**row, "launch_type": "early_access"}, 50)
    assert ch.needs_prior_check({k: v for k, v in row.items() if k != "reviews_before_launch"}, 50)  # old file


class Args:
    checkpoint = 2
    max_consecutive_errors = 2


class NeverExpires:
    def expired(self):
        return False


def test_run_pass_checkpoints_and_stops_on_repeated_errors():
    saves = []

    def fetch(row):
        if row["appid"] >= 3:
            raise RuntimeError("blocked")
        return True

    todo = [{"appid": i} for i in range(1, 6)]
    assert ch.run_pass(todo, fetch, "test", NeverExpires(), lambda: saves.append(1), Args()) is False
    assert saves == [1]  # one checkpoint after 2 fetches, then 2 errors in a row stop it


def test_needs_reviews_waits_for_window_to_close():
    row = {"reviews_30d": "", "launch_ts": "1000"}
    assert not ch.needs_reviews(row, 1000 + ch.WINDOW - 1)
    assert ch.needs_reviews(row, 1000 + ch.WINDOW)
    assert not ch.needs_reviews({**row, "reviews_30d": "0"}, 10**10)


def test_month_starts():
    assert list(ch.month_starts(date(2025, 11, 15), date(2026, 1, 2))) == [
        date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1)]


# -- upcoming ----------------------------------------------------------------

def test_build_snapshot_attaches_wishlist_rank():
    items = [{"appid": 5, "release": {"coming_soon_display": "text_tba"}},
             {"appid": 3, "release": {"coming_soon_display": "date_year", "steam_release_date": 1830240000}}]
    rows = cu.build_snapshot(items, [3, 99])
    assert [(r["appid"], r["wishlist_rank"], r["precision"]) for r in rows] == [(3, 1, "year"), (5, "", "unknown")]


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
