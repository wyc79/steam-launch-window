from datetime import date, datetime, timezone

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
    assert jobs(history=[launched(1, "2026-10-12")]) == [(0, "followers", 1)]  # day 8


def test_post_launch_pull_happens_once_and_catches_up_for_60_days():
    done = pulled(1, "followers", "2026-10-20T19:00:00+00:00")
    assert jobs(history=[launched(1, "2026-10-12")], state=done) == []
    before_launch = pulled(1, "followers", "2026-08-01T19:00:00+00:00")
    def followers(history, state):
        return [j for j in jobs(history=history, state=state) if j[1] == "followers"]
    assert followers([launched(1, "2026-08-25")], before_launch) == [(0, "followers", 1)]  # day 56
    assert followers([launched(1, "2026-08-20")], before_launch) == []  # day 61: past the window


def test_players_pull_once_after_35_days():
    assert (1, "players", 1) not in jobs(history=[launched(1, "2026-09-16")])  # day 34
    assert (1, "players", 1) in jobs(history=[launched(1, "2026-09-15")])      # day 35
    done = pulled(1, "players", "2026-10-19T19:00:00+00:00")
    assert (1, "players", 1) not in jobs(history=[launched(1, "2026-09-15")], state=done)


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
    assert got == [(0, "followers", 1), (2, "followers", 3), (3, "followers", 2)]


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
    assert stats["errors"] == 1 and set(state) == {("followers", 2)}


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
    assert cg.load_state(tmp_path) == state


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


def test_players_pull_is_skipped_after_42_days():
    assert (1, "players", 1) in jobs(history=[launched(1, "2026-09-08")])      # day 42
    assert (1, "players", 1) not in jobs(history=[launched(1, "2026-09-07")])  # day 43: more than one page


def test_run_stops_when_429s_persist_after_the_clients_retries(tmp_path):
    client = FakeGP({1: [HTTPStatusError(429, "u")], 2: [page("followers")]})
    stats = run(tmp_path, client, [job(1), job(2)], {})
    assert stats["stopped"] == "rate_limited" and client.requests_made == 1
