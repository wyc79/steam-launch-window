from datetime import date, datetime, timedelta, timezone

import pytest

from pipeline import collect_gp as cg
from pipeline import storage
from pipeline.http import HTTPStatusError, RateLimited

TODAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 20, 19, tzinfo=timezone.utc)
POLICY = cg.Policy()


def launched(appid, launch_date, *, reviews=20, free=0, launch_type="full"):
    return {"appid": str(appid), "launch_date": launch_date, "is_free": str(free),
            "launch_type": launch_type, "reviews_total_now": str(reviews)}


def upcoming(appid, precision="day", date_end="2026-11-10", rank=""):
    return {"appid": str(appid), "precision": precision, "date_end": date_end if precision != "unknown" else "",
            "wishlist_rank": str(rank)}


def pulled(appid, kind, when, observed=None, status="ok"):
    return {(kind, appid): {"appid": str(appid), "kind": kind, "last_pulled": when, "status": status,
                            "last_observed_at": observed or when, "points": "5"}}


def jobs(snapshot=(), history=(), state=None):
    return [(j.priority, j.kind, j.appid) for j in cg.plan(list(snapshot), list(history), state or {}, TODAY, POLICY)]


# -- planning ----------------------------------------------------------------

def test_post_launch_followers_pull_after_8_days():
    assert jobs(history=[launched(1, "2026-10-13")]) == []                  # day 7
    assert jobs(history=[launched(1, "2026-10-12")]) == [(1, "followers", 1)]  # day 8


def test_post_launch_pull_happens_once_and_catches_up_for_60_days():
    done = pulled(1, "followers", "2026-10-20T19:00:00+00:00")
    assert jobs(history=[launched(1, "2026-10-12")], state=done) == []
    before_launch = pulled(1, "followers", "2026-08-01T19:00:00+00:00")
    def followers(history, state):
        return [j for j in jobs(history=history, state=state) if j[1] == "followers"]
    assert followers([launched(1, "2026-08-25")], before_launch) == [(1, "followers", 1)]  # day 56
    assert followers([launched(1, "2026-08-20")], before_launch) == []  # day 61: past the window


def test_players_pull_once_after_35_days():
    assert (0, "players", 1) not in jobs(history=[launched(1, "2026-09-16")])  # day 34
    assert (0, "players", 1) in jobs(history=[launched(1, "2026-09-15")])      # day 35
    done = pulled(1, "players", "2026-10-19T19:00:00+00:00")
    assert (0, "players", 1) not in jobs(history=[launched(1, "2026-09-15")], state=done)


def test_upcoming_games_with_a_date_or_rank_refresh_every_60_days():
    snap = [upcoming(1), upcoming(2, "unknown"), upcoming(3, "unknown", rank=40), upcoming(4, "year", "2027-12-31"),
            upcoming(5, "day", "2025-01-01")]  # 5: date long past, a stale page
    assert sorted(jobs(snapshot=snap)) == [(2, "followers", 1), (2, "followers", 3), (2, "followers", 4)]
    recent = pulled(1, "followers", "2026-08-22T19:00:00+00:00")  # 59 days ago
    assert (2, "followers", 1) not in jobs(snapshot=snap, state=recent)
    old = pulled(1, "followers", "2026-08-21T19:00:00+00:00")     # 60 days ago
    assert (2, "followers", 1) in jobs(snapshot=snap, state=old)


def test_upcoming_order_never_pulled_first_then_soonest():
    snap = [upcoming(1, date_end="2026-12-01"), upcoming(2, date_end="2026-10-25"), upcoming(3, date_end="2026-11-01")]
    state = pulled(2, "followers", "2026-07-01T00:00:00+00:00")
    assert [a for _, _, a in jobs(snapshot=snap, state=state)] == [3, 1, 2]


def test_backfill_order_and_cutoff():
    hist = [launched(1, "2024-03-14"),                  # before follower history starts
            launched(2, "2025-01-01", reviews=5),       # group 1
            launched(3, "2024-06-01", reviews=50),      # group 0
            launched(4, "2025-06-01", reviews=50),      # group 0, newer
            launched(5, "2025-06-01", reviews=50, free=1),  # free: group 2
            launched(6, "2025-06-01", reviews=0)]       # group 2
    assert [a for p, _, a in jobs(history=hist) if p == 3] == [4, 3, 2, 5, 6]
    assert jobs(history=hist, state=pulled(4, "followers", "2026-10-01T00:00:00+00:00"))[0][2] == 3


def test_priorities_are_ordered_and_each_game_appears_once_per_kind():
    hist = [launched(1, "2026-10-12"), launched(2, "2025-06-01")]
    got = jobs(snapshot=[upcoming(3)], history=hist)
    assert got == [(1, "followers", 1), (2, "followers", 3), (3, "followers", 2)]


# -- running -----------------------------------------------------------------

class FakeGP:
    """Fake HTTP client: per appid, a list of replies (dict or Exception), used in order."""

    def __init__(self, replies):
        self.replies = {k: list(v) for k, v in replies.items()}
        self.requests_made = 0
        self.calls = []

    def get_json(self, url, params=None):
        self.requests_made += 1
        appid = int(url.rsplit("/", 1)[1])
        self.calls.append((url, dict(params or {})))
        reply = self.replies[appid].pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def page(kind, *points, cursor=None):
    return {"history": [{kind: v, "added": t} for t, v in points], "nextCursor": cursor}


def job(appid, kind="followers", since=None, priority=2):
    return cg.Job(priority=priority, order=(), kind=kind, appid=appid, since=since)


def run(tmp_path, client, todo, state=None, budget=900):
    return cg.run(todo, client, "KEY", state if state is not None else {}, tmp_path, NOW, budget)


def test_run_writes_points_state_and_a_run_row(tmp_path):
    client = FakeGP({1: [page("followers", ("2026-10-20T10:00:00", 12), ("2026-10-19T10:00:00", 11))],
                     2: [page("followers")], 3: [HTTPStatusError(404, "u")]})
    state = {}
    stats = run(tmp_path, client, [job(1), job(2), job(3)], state)
    rows = storage.read_csv(tmp_path / "followers" / "2026-10-20.csv.gz")
    assert [(r["appid"], r["followers"], r["observed_at"]) for r in rows] == [
        ("1", "11", "2026-10-19T10:00:00+00:00"), ("1", "12", "2026-10-20T10:00:00+00:00")]
    assert {k: v["status"] for k, v in state.items()} == {
        ("followers", 1): "ok", ("followers", 2): "null", ("followers", 3): "not_in_dataset"}
    saved = storage.read_csv(tmp_path / "state.csv")
    assert {r["appid"]: r["last_observed_at"] for r in saved}["1"] == "2026-10-20T10:00:00+00:00"
    assert stats["requests"] == 3 and stats["stopped"] == "done"
    run_row = storage.read_csv(tmp_path / "runs.csv")[0]
    assert (run_row["date"], run_row["requests"], run_row["points"]) == ("2026-10-20", "3", "2")


def test_run_stops_at_the_budget(tmp_path):
    client = FakeGP({i: [page("followers", ("2026-10-20T10:00:00", i))] for i in range(1, 6)})
    stats = run(tmp_path, client, [job(i) for i in range(1, 6)], budget=3)
    assert stats["requests"] == 3 and stats["stopped"] == "budget"


def test_run_counts_requests_already_made_today(tmp_path):
    storage.write_csv(tmp_path / "runs.csv", [{"date": "2026-10-20", "started_at": "x", "requests": 899}],
                      cg.RUN_FIELDS)
    client = FakeGP({1: [page("followers", ("2026-10-20T10:00:00", 1))], 2: [page("followers")]})
    stats = run(tmp_path, client, [job(1), job(2)], budget=900)
    assert stats["requests"] == 1 and stats["stopped"] == "budget"


def test_run_stops_on_rate_limit_and_keeps_what_it_got(tmp_path):
    client = FakeGP({1: [page("followers", ("2026-10-20T10:00:00", 7))], 2: [RateLimited("u")], 3: [page("followers")]})
    state = {}
    stats = run(tmp_path, client, [job(1), job(2), job(3)], state)
    assert stats["stopped"] == "rate_limited" and set(state) == {("followers", 1)}
    assert len(storage.read_csv(tmp_path / "followers" / "2026-10-20.csv.gz")) == 1


def test_run_skips_a_failing_game_and_leaves_it_due(tmp_path):
    client = FakeGP({1: [HTTPStatusError(500, "u")], 2: [page("followers", ("2026-10-20T10:00:00", 2))]})
    state = {}
    stats = run(tmp_path, client, [job(1), job(2)], state)
    assert stats["errors"] == 1 and state[("followers", 2)]["status"] == "ok"
    failed = state[("followers", 1)]
    assert (failed["status"], failed["tries"], failed["last_pulled"], failed["last_observed_at"]) == ("error", "1", "", "")
    # due again the next day, as a backfill game and as an upcoming game
    tomorrow = date(2026, 10, 21)
    assert [j.appid for j in cg.plan([], [launched(1, "2025-06-01")], state, tomorrow, POLICY)] == [1]
    assert [j.appid for j in cg.plan([upcoming(1)], [], state, tomorrow, POLICY)] == [1]


def test_incremental_pull_passes_since_and_keeps_the_old_observation_time(tmp_path):
    since = datetime(2026, 10, 19, 10, tzinfo=timezone.utc)
    client = FakeGP({1: [page("followers", ("2026-10-20T10:00:00", 12), ("2026-10-19T10:00:00", 11))]})
    state = pulled(1, "followers", "2026-10-19T19:00:00+00:00", observed="2026-10-19T10:00:00+00:00")
    run(tmp_path, client, [job(1, since=since)], state)
    assert [r["followers"] for r in storage.read_csv(tmp_path / "followers" / "2026-10-20.csv.gz")] == ["12"]
    assert state[("followers", 1)]["points"] == "6"


def test_no_new_points_keeps_status_ok_but_stale_if_old(tmp_path):
    since = datetime(2026, 8, 1, tzinfo=timezone.utc)
    client = FakeGP({1: [page("followers", ("2026-08-01T00:00:00", 3))]})
    state = pulled(1, "followers", "2026-08-02T00:00:00+00:00", observed="2026-08-01T00:00:00+00:00")
    run(tmp_path, client, [job(1, since=since)], state)
    assert state[("followers", 1)]["status"] == "stale"


def test_rerun_on_the_same_day_does_not_duplicate_points(tmp_path):
    for _ in range(2):
        client = FakeGP({1: [page("followers", ("2026-10-20T10:00:00", 12))]})
        run(tmp_path, client, [job(1)], {})
    assert len(storage.read_csv(tmp_path / "followers" / "2026-10-20.csv.gz")) == 1


def test_players_go_to_their_own_file(tmp_path):
    client = FakeGP({1: [page("players", ("2026-10-20T10:00:00", 40))]})
    run(tmp_path, client, [job(1, kind="players")], {})
    assert storage.read_csv(tmp_path / "players" / "2026-10-20.csv.gz")[0]["players"] == "40"


def test_load_state_round_trip(tmp_path):
    state = pulled(1, "followers", "2026-10-20T19:00:00+00:00")
    cg.save_state(tmp_path, state)
    assert cg.load_state(tmp_path) == {k: {f: v.get(f, "") for f in cg.STATE_FIELDS} for k, v in state.items()}


def test_state_written_before_the_retry_columns_still_loads_and_plans(tmp_path):
    (tmp_path / "state.csv").write_text(
        "appid,kind,last_pulled,status,last_observed_at,points\n"
        "1,followers,2026-10-12T19:00:00+00:00,null,,0\n"
        "2,followers,2026-10-12T19:00:00+00:00,ok,2026-10-19T10:00:00+00:00,30\n")
    state = cg.load_state(tmp_path)
    assert cg._tries(state[("followers", 1)]) == 1 and cg._tries(state[("followers", 2)]) == 0
    got = cg.plan([], [launched(1, "2026-10-04"), launched(2, "2026-10-04")], state, TODAY, POLICY)
    assert [(j.priority, j.appid) for j in got] == [(1, 1)]  # 2 already has its launch week
    cg.save_state(tmp_path, state)
    assert list(storage.read_csv(tmp_path / "state.csv")[0]) == cg.STATE_FIELDS


def test_main_dry_run_needs_no_key(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GP_API_KEY", raising=False)
    data = tmp_path / "data"
    storage.write_csv(data / "upcoming" / "snapshots" / "2026-10-20.csv.gz", [upcoming(1)],
                      ["appid", "precision", "date_end", "wishlist_rank"])
    assert cg.main(["--data-dir", str(data), "--gp-dir", str(tmp_path / "gp"), "--today", "2026-10-20",
                    "--dry-run"]) == 0


def test_main_without_key_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.delenv("GP_API_KEY", raising=False)
    data = tmp_path / "data"
    storage.write_csv(data / "upcoming" / "snapshots" / "2026-10-20.csv.gz", [upcoming(1)],
                      ["appid", "precision", "date_end", "wishlist_rank"])
    with pytest.raises(SystemExit, match="GP_API_KEY"):
        cg.main(["--data-dir", str(data), "--gp-dir", str(tmp_path / "gp"), "--today", "2026-10-20"])


def test_players_never_pulled_are_caught_up_until_day_60():
    assert (0, "players", 1) in jobs(history=[launched(1, "2026-09-08")])      # day 42
    assert (0, "players", 1) in jobs(history=[launched(1, "2026-08-21")])      # day 60: two pages
    assert (0, "players", 1) not in jobs(history=[launched(1, "2026-08-20")])  # day 61


def test_run_stops_when_429s_persist_after_the_clients_retries(tmp_path):
    client = FakeGP({1: [HTTPStatusError(429, "u")], 2: [page("followers")]})
    stats = run(tmp_path, client, [job(1), job(2)], {})
    assert stats["stopped"] == "rate_limited" and client.requests_made == 1


def test_a_pull_cut_short_by_the_budget_is_kept_and_resumed(tmp_path):
    storage.write_csv(tmp_path / "runs.csv", [{"date": "2026-10-20", "started_at": "x", "requests": 899}],
                      cg.RUN_FIELDS)
    first = page("followers", ("2026-10-20T10:00:00", 9), cursor="2026-10-19T00:00:00")
    client = FakeGP({1: [first]})
    state = {}
    run(tmp_path, client, [job(1)], state, budget=900)
    row = state[("followers", 1)]
    assert (row["status"], row["resume_cursor"], row["resume_since"]) == ("partial", "2026-10-19T00:00:00", "")
    assert len(storage.read_csv(tmp_path / "followers" / "2026-10-20.csv.gz")) == 1
    # the next day it goes on from the cursor, not from the newest point
    nxt = cg.plan([], [launched(1, "2025-06-01")], state, date(2026, 10, 21), POLICY)
    assert [(j.priority, j.appid, j.cursor, j.since) for j in nxt] == [(0, 1, "2026-10-19T00:00:00", None)]


# -- missing data is retried, within limits -------------------------------------

def _plan(state, *, history=(), snapshot=(), today=TODAY):
    return [(j.priority, j.kind, j.appid) for j in cg.plan(list(snapshot), list(history), state, today, POLICY)]


def test_post_launch_followers_missing_then_available_is_retried_and_recovered(tmp_path):
    hist = [launched(1, "2026-10-12")]
    state = {}
    day8 = datetime(2026, 10, 20, 19, tzinfo=timezone.utc)
    cg.run(cg.plan([], hist, state, day8.date(), POLICY), FakeGP({1: [HTTPStatusError(404, "u")]}), "KEY",
           state, tmp_path, day8, 900)
    assert state[("followers", 1)]["status"] == "not_in_dataset"
    assert _plan(state, history=hist, today=date(2026, 10, 21)) == [(1, "followers", 1)]  # 1 day later
    day9 = datetime(2026, 10, 21, 19, tzinfo=timezone.utc)
    cg.run(cg.plan([], hist, state, day9.date(), POLICY), FakeGP({1: [page("followers")]}), "KEY",
           state, tmp_path, day9, 900)
    assert (state[("followers", 1)]["status"], state[("followers", 1)]["tries"]) == ("null", "2")
    assert _plan(state, history=hist, today=date(2026, 10, 22)) == []                    # waits 2 days
    assert _plan(state, history=hist, today=date(2026, 10, 23)) == [(1, "followers", 1)]
    day11 = datetime(2026, 10, 23, 19, tzinfo=timezone.utc)
    reply = page("followers", ("2026-10-23T08:00:00", 120), ("2026-10-11T08:00:00", 40))
    cg.run(cg.plan([], hist, state, day11.date(), POLICY), FakeGP({1: [reply]}), "KEY", state, tmp_path, day11, 900)
    row = state[("followers", 1)]
    assert (row["status"], row["tries"], row["points"]) == ("ok", "0", "2")
    assert _plan(state, history=hist, today=date(2026, 10, 24)) == []  # launch week is in: done


def test_post_launch_retries_give_up_after_max_tries():
    hist = [launched(1, "2026-10-01")]
    row = {"appid": "1", "kind": "followers", "last_pulled": "2026-10-12T19:00:00+00:00",
           "last_tried": "2026-10-12T19:00:00+00:00", "status": "null", "last_observed_at": "", "points": "0",
           "tries": "4"}
    assert _plan({("followers", 1): row}, history=hist) == [(1, "followers", 1)]   # 8 days after try 4
    assert _plan({("followers", 1): {**row, "tries": "5"}}, history=hist) == []    # confirmed unavailable


def test_launch_week_that_gp_has_not_reached_yet_is_pulled_again():
    hist = [launched(1, "2026-10-10")]
    row = {"appid": "1", "kind": "followers", "last_pulled": "2026-10-18T19:00:00+00:00",
           "last_tried": "2026-10-18T19:00:00+00:00", "status": "ok",
           "last_observed_at": "2026-10-13T08:00:00+00:00", "points": "200", "tries": "0"}
    assert _plan({("followers", 1): row}, history=hist) == [(1, "followers", 1)]
    seen = {**row, "last_observed_at": "2026-10-16T08:00:00+00:00"}
    assert _plan({("followers", 1): seen}, history=hist) == []


def test_players_with_no_data_are_retried_inside_the_post_launch_window():
    row = {"appid": "1", "kind": "players", "last_pulled": "2026-10-10T19:00:00+00:00",
           "last_tried": "2026-10-10T19:00:00+00:00", "status": "null", "last_observed_at": "", "points": "0",
           "tries": "1"}
    assert (0, "players", 1) in _plan({("players", 1): row}, history=[launched(1, "2026-09-05")])     # day 45
    assert (0, "players", 1) not in _plan({("players", 1): row}, history=[launched(1, "2026-08-20")])  # day 61
    got = {**row, "status": "ok", "tries": "0", "points": "900"}
    assert (0, "players", 1) not in _plan({("players", 1): got}, history=[launched(1, "2026-09-05")])


def test_backfill_retries_failed_requests_but_not_confirmed_missing_data():
    hist = [launched(1, "2025-06-01")]
    error = {"appid": "1", "kind": "followers", "last_pulled": "", "last_tried": "2026-10-19T19:00:00+00:00",
             "status": "error", "last_observed_at": "", "points": "0", "tries": "1"}
    assert _plan({("followers", 1): error}, history=hist) == [(3, "followers", 1)]
    assert _plan({("followers", 1): {**error, "tries": "2"}}, history=hist) == []  # waits 2 days
    missing = {**error, "status": "not_in_dataset", "last_pulled": "2026-10-01T19:00:00+00:00"}
    assert _plan({("followers", 1): missing}, history=hist) == []


def test_a_failed_refresh_keeps_earlier_data(tmp_path):
    state = pulled(1, "followers", "2026-08-01T19:00:00+00:00", observed="2026-08-01T08:00:00+00:00")
    run(tmp_path, FakeGP({1: [HTTPStatusError(503, "u")]}), [job(1)], state)
    row = state[("followers", 1)]
    assert (row["status"], row["last_pulled"], row["last_observed_at"], row["points"]) == (
        "error", "2026-08-01T19:00:00+00:00", "2026-08-01T08:00:00+00:00", "5")


def test_zero_is_kept_as_a_value_and_missing_values_are_not_zero(tmp_path):
    reply = {"history": [{"players": 0, "added": "2026-10-20T10:00:00"},
                         {"players": None, "added": "2026-10-20T09:00:00"},
                         {"players": 3, "added": "2026-10-20T08:00:00"}], "nextCursor": None}
    run(tmp_path, FakeGP({1: [reply]}), [job(1, kind="players")], {})
    rows = storage.read_csv(tmp_path / "players" / "2026-10-20.csv.gz")
    assert [(r["observed_at"][11:13], r["players"]) for r in rows] == [("08", "3"), ("10", "0")]


def test_a_day_that_ended_rate_limited_does_not_start_again(tmp_path):
    storage.write_csv(tmp_path / "runs.csv", [{"date": "2026-10-20", "started_at": "x", "requests": 3,
                                               "stopped": "rate_limited"}], cg.RUN_FIELDS)
    client = FakeGP({1: [page("followers", ("2026-10-20T10:00:00", 1))]})
    stats = run(tmp_path, client, [job(1)])
    assert client.requests_made == 0 and stats["stopped"] == "budget"


def test_a_429_is_not_counted_against_the_game(tmp_path):
    state = {}
    run(tmp_path, FakeGP({1: [HTTPStatusError(429, "u")]}), [job(1)], state)
    assert state == {}


# -- histories longer than the page cap ---------------------------------------

class PagedGP:
    """Fake Games Popularity history for one game: `n` daily points, `per_page` per page,
    newest first. The cursor is the time of the next page's first point, and that point
    is repeated at the end of the page before (to check that overlaps give no duplicates)."""

    def __init__(self, n, per_page, newest="2026-10-20T08:00:00", fail_at=None):
        end = datetime.fromisoformat(newest)
        self.times = [(end - timedelta(days=i)).isoformat() for i in range(n)]
        self.per_page, self.fail_at = per_page, fail_at
        self.requests_made = 0

    def get_json(self, url, params=None):
        self.requests_made += 1
        if self.fail_at is not None and self.requests_made == self.fail_at:
            raise HTTPStatusError(503, "u")
        start = self.times.index(params["cursor"]) if "cursor" in params else 0
        chunk = self.times[start:start + self.per_page + 1]  # one extra: the overlap
        nxt = self.times[start + self.per_page] if start + self.per_page < len(self.times) else None
        return {"history": [{"followers": 10000 - self.times.index(t), "added": t} for t in chunk],
                "nextCursor": nxt}


def _collect_days(tmp_path, client, days, hist):
    state = {}
    for d in range(days):
        now = datetime(2026, 10, 20 + d, 19, tzinfo=timezone.utc)
        cg.run(cg.plan([], hist, state, now.date(), POLICY), client, "KEY", state, tmp_path, now, 900)
    return state


def test_history_longer_than_five_pages_is_completed_over_several_runs(tmp_path):
    client = PagedGP(n=23, per_page=2)  # 12 pages
    state = _collect_days(tmp_path, client, 4, [launched(1, "2025-06-01")])
    rows = [r for f in sorted((tmp_path / "followers").glob("*.csv.gz")) for r in storage.read_csv(f)]
    times = sorted(r["observed_at"][:19] for r in rows)
    assert times == sorted(client.times) and len(set(times)) == len(times)  # all of them, once each
    row = state[("followers", 1)]
    assert (row["status"], row["resume_cursor"], row["points"]) == ("ok", "", "23")
    assert row["last_observed_at"].startswith("2026-10-20T08:00:00")
    assert client.requests_made == 12


def test_interrupted_pagination_resumes_without_gaps_or_duplicates(tmp_path):
    client = PagedGP(n=15, per_page=2, fail_at=7)  # page 2 of the resume fails
    state = _collect_days(tmp_path, client, 5, [launched(1, "2025-06-01")])
    rows = [r for f in sorted((tmp_path / "followers").glob("*.csv.gz")) for r in storage.read_csv(f)]
    times = sorted(r["observed_at"][:19] for r in rows)
    assert times == sorted(client.times) and len(set(times)) == len(times)
    assert state[("followers", 1)]["resume_cursor"] == "" and state[("followers", 1)]["points"] == "15"


def test_a_refresh_after_a_partial_pull_does_not_skip_the_gap(tmp_path):
    client = PagedGP(n=12, per_page=2)
    hist = [launched(1, "2025-06-01")]
    state = {}
    now = datetime(2026, 10, 20, 19, tzinfo=timezone.utc)
    cg.run(cg.plan([], hist, state, now.date(), POLICY), client, "KEY", state, tmp_path, now, 900)
    assert state[("followers", 1)]["status"] == "partial"
    # an upcoming-game refresh is held back until the older pages are in
    assert [(j.priority, j.cursor is not None) for j in cg.plan([upcoming(1)], hist, state, date(2026, 10, 21),
                                                                 POLICY)] == [(0, True)]


def test_players_come_before_follower_catch_up():
    # a game on day 41 must get its players pull before any followers catch-up uses the budget
    hist = [launched(1, "2026-10-12"), launched(2, "2026-09-09"), launched(3, "2026-09-15")]
    assert jobs(history=hist)[:3] == [(0, "players", 2), (0, "players", 3), (1, "followers", 2)]


def test_a_killed_run_has_already_counted_its_requests(tmp_path):
    seen = {}

    class Killed(FakeGP):
        def get_json(self, url, params=None):
            if self.requests_made == 3:  # what a run killed now would leave behind
                seen["runs"] = storage.read_csv(tmp_path / "runs.csv")
            return super().get_json(url, params)

    client = Killed({i: [page("followers", ("2026-10-20T10:00:00", i))] for i in range(1, 5)})
    cg.run([job(i) for i in range(1, 5)], client, "KEY", {}, tmp_path, NOW, 900, checkpoint=2)
    assert [(r["requests"], r["stopped"]) for r in seen["runs"]] == [("2", "running")]
    assert cg.used_today(tmp_path, "2026-10-20") == 4  # the finished run replaced its own row
    assert storage.read_csv(tmp_path / "runs.csv")[0]["stopped"] == "done"
