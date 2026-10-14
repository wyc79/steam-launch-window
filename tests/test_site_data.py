import json
from datetime import date

import pytest

from analysis import heatmap as hm
from analysis import site_data as sd
from pipeline import storage

SNAP = ["appid", "release_ts", "display", "raw", "precision", "date", "date_end", "date_ok",
        "early_access", "wishlist_rank", "price_cents"]
APPS = ["appid", "name", "developers", "publishers", "franchises", "tags", "demo_appids", "is_free",
        "languages", "audio_languages", "first_seen", "last_seen"]
EVENTS = """events:
- name: Steam Autumn Sale
  type: seasonal_sale
  start: 2026-11-25
  end: 2026-12-02
  source: https://example.com
"""


def snap(appid, raw, precision, start="", end="", rank="", ea="0"):
    return {"appid": appid, "raw": raw, "precision": precision, "date": start, "date_end": end or start,
            "early_access": ea, "wishlist_rank": rank}


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "data"
    snaps = d / "upcoming" / "snapshots"
    day1 = [snap(1, "October 2026", "month", "2026-10-01", "2026-10-31"),
            snap(2, "Coming soon", "unknown"),
            snap(3, "Nov 4, 2026", "day", "2026-11-04")]
    day2 = [snap(1, "May 2027", "month", "2027-05-01", "2027-05-31", rank="40"),   # moved
            snap(2, "Dec 1, 2026", "day", "2026-12-01"),                          # got a date
            snap(3, "Nov 4, 2026", "day", "2026-11-04"),
            snap(4, "Coming soon", "unknown"),                                     # no date, no rank: left out
            snap(5, "To be announced", "unknown", rank="7"),                       # ranked: kept
            snap(6, "Jan 3, 2025", "day", "2025-01-03"),                           # stale page: left out
            snap(7, "2027", "year", "2027-01-01", "2027-12-31")]
    storage.write_csv(snaps / "2026-10-11.csv.gz", day1, SNAP)
    storage.write_csv(snaps / "2026-10-12.csv.gz", day2, SNAP)
    apps = [{"appid": 1, "name": "Mover", "tags": "1716:50|1774:900", "is_free": "0", "languages": "english"},
            {"appid": 2, "name": "Setter", "tags": "113:100|1774:90", "is_free": "0", "languages": "english|schinese"},
            {"appid": 3, "name": "Free Flag", "tags": "1774:10", "is_free": "1", "languages": "schinese"},
            {"appid": 5, "name": "Ranked", "tags": "1774:5|99999:4", "is_free": "0", "languages": "english"},
            {"appid": 7, "name": "Someday", "tags": "1774:5", "is_free": "0", "languages": "english"}]
    storage.write_csv(d / "upcoming" / "apps.csv", apps, APPS)
    storage.write_csv(d / "tags.csv", [{"tagid": 113, "name": "Free to Play"}, {"tagid": 1716, "name": "Roguelike"},
                                       {"tagid": 1774, "name": "Shooter"}], ["tagid", "name"])
    hist_fields = ["appid", "launch_date", "launch_type", "tags", "languages", "is_free", "price_cents", "reviews_30d"]
    storage.write_csv(d / "history" / "games.csv", [
        {"appid": 10, "launch_date": "2025-03-03", "launch_type": "full", "tags": "1774:9", "languages": "english",
         "is_free": "0", "price_cents": "999", "reviews_30d": "12"},
        {"appid": 11, "launch_date": "2025-03-04", "launch_type": "ea_exit", "tags": "1774:9",
         "languages": "english", "is_free": "0", "price_cents": "1999", "reviews_30d": "50"},
        {"appid": 12, "launch_date": "2026-10-01", "launch_type": "early_access", "tags": "1716:3",
         "languages": "english", "is_free": "0", "price_cents": "", "reviews_30d": ""},
    ], hist_fields)
    gp = tmp_path / "gp"
    gp_fields = ["appid", "followers", "observed_at", "fetched_at"]
    storage.write_csv(gp / "followers" / "2026-10-11.csv.gz", [
        {"appid": 1, "followers": "300", "observed_at": "2026-10-10T00:00:00+00:00"},
        {"appid": 1, "followers": "100", "observed_at": "2026-09-01T00:00:00+00:00"}], gp_fields)
    storage.write_csv(gp / "followers" / "2026-10-12.csv.gz", [
        {"appid": 1, "followers": "250", "observed_at": "2026-10-01T00:00:00+00:00"},  # older point, fetched later
        {"appid": 3, "followers": "", "observed_at": "2026-10-11T00:00:00+00:00"}], gp_fields)
    events = tmp_path / "events.yaml"
    events.write_text(EVENTS, encoding="ascii")
    return d, gp, events


def built(data, tmp_path, gp=True):
    d, gp_dir, events = data
    out = tmp_path / "site"
    stats = sd.build(d, events, out, gp_dir if gp else None)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    up = {g["appid"]: g for g in sd.load_table(out / "upcoming.json", meta)}
    hist = {g["appid"]: g for g in sd.load_table(out / "history.json", meta)}
    return stats, meta, up, hist, out


def test_upcoming_keeps_dated_or_ranked_games_and_drops_stale_pages(data, tmp_path):
    stats, meta, up, _, _ = built(data, tmp_path)
    assert sorted(up) == [1, 2, 3, 5, 7]
    assert meta["snapshot_date"] == "2026-10-12"
    assert up[5]["precision"] == "unknown" and up[5]["wishlist_rank"] == 7
    assert up[7]["date"] == "2027-01-01" and up[7]["date_end"] == "2027-12-31"


def test_the_store_text_is_kept_only_for_games_with_no_date(data, tmp_path):
    _, _, up, _, out = built(data, tmp_path)
    assert up[5]["date_text"] == "To be announced"
    assert {a: g["date_text"] for a, g in up.items() if a != 5} == {1: None, 2: None, 3: None, 7: None}
    table = json.loads((out / "upcoming.json").read_text(encoding="utf-8"))
    assert table["columns"] == sd.UPCOMING_COLUMNS


def test_tags_heaviest_first_and_free_flag(data, tmp_path):
    _, meta, up, _, _ = built(data, tmp_path)
    assert up[1]["tags"] == [1774, 1716]
    assert up[2]["free"] is True   # Free to Play in the top 10
    assert up[3]["free"] is True   # Steam's flag
    assert up[1]["free"] is False
    assert up[5]["tags"] == [1774, 99999]  # a tag missing from tags.csv is kept
    assert [99999, None, 1, 0] in meta["tags"]
    assert up[2]["langs"] == ["english", "schinese"]


def test_moved_marker_from_the_last_30_days(data, tmp_path):
    stats, _, up, _, _ = built(data, tmp_path)
    assert up[1]["moved"] == ["moved", "October 2026", "2026-10-12"]
    assert up[2]["moved"] == ["date_set", "Coming soon", "2026-10-12"]
    assert up[3]["moved"] is None and up[7]["moved"] is None  # unchanged, or new on the list
    assert stats["moved"] == 2


def test_recent_changes_ignores_changes_older_than_the_window(tmp_path):
    snaps = tmp_path / "s"
    storage.write_csv(snaps / "2026-08-01.csv.gz", [snap(1, "2026", "year", "2026-01-01", "2026-12-31")], SNAP)
    storage.write_csv(snaps / "2026-08-02.csv.gz", [snap(1, "Q4 2026", "quarter", "2026-10-01", "2026-12-31")], SNAP)
    storage.write_csv(snaps / "2026-10-12.csv.gz", [snap(1, "Q4 2026", "quarter", "2026-10-01", "2026-12-31")], SNAP)
    assert sd.recent_changes(snaps, date(2026, 10, 12)) == {}


def test_followers_take_the_newest_point_and_rank_estimates_need_enough_games(data, tmp_path):
    stats, meta, up, _, _ = built(data, tmp_path)
    assert up[1]["followers"] == 300 and up[1]["hype_src"] == "f"
    assert up[3]["followers"] is None   # Games Popularity had no value
    assert up[5]["followers"] is None and meta["rank_curve"] is None  # one ranked game with followers: no curve
    _, _, up, _, _ = built(data, tmp_path, gp=False)
    assert all(g["followers"] is None for g in up.values())


def test_followers_come_from_latest_followers_csv_when_present(data, tmp_path):
    from pipeline import collect_gp

    _, gp, _ = data
    scanned = sd.newest_followers(gp)
    collect_gp.build_latest(gp)  # built by the collector from the same day files
    assert sd.newest_followers(gp) == scanned == {1: 300}
    storage.write_csv(gp / "latest_followers.csv", [{"appid": 1, "followers": 310, "observed_at": "x"}],
                      collect_gp.LATEST_FIELDS)
    _, _, up, _, _ = built(data, tmp_path)
    assert up[1]["followers"] == 310   # the day files are not read


def test_rank_curve_fits_a_power_law():
    pairs = [(r, round(1e6 * r ** -0.8)) for r in range(1, 61)]
    a, b = sd.rank_curve(pairs)
    assert b == pytest.approx(-0.8, abs=0.01)
    assert sd.rank_curve(pairs[:10]) is None


def test_history_leaves_out_ea_exit(data, tmp_path):
    _, _, _, hist, _ = built(data, tmp_path)
    assert sorted(hist) == [10, 12]
    assert hist[10] == {"appid": 10, "launch_date": "2025-03-03", "launch_type": "full", "tags": [1774],
                        "langs": ["english"], "free": False, "price_cents": 999, "reviews_30d": 12, "listed": True}
    assert hist[12]["reviews_30d"] is None and hist[12]["price_cents"] is None


def test_history_marks_games_the_newest_listing_run_no_longer_lists(data, tmp_path):
    d = data[0]
    fields = ["appid", "launch_date", "launch_type", "tags", "languages", "is_free", "price_cents", "reviews_30d",
              "last_listed"]
    row = {"launch_type": "full", "tags": "1774:9", "languages": "english", "is_free": "0", "price_cents": "999",
           "reviews_30d": "1"}
    storage.write_csv(d / "history" / "games.csv", [
        {**row, "appid": 10, "launch_date": "2025-03-03", "last_listed": "2026-10-19"},
        {**row, "appid": 12, "launch_date": "2026-10-01", "last_listed": "2026-10-12"},  # removed since
        {**row, "appid": 13, "launch_date": "2026-10-02", "last_listed": ""},  # never stamped: counts as listed
    ], fields)
    hist = built(data, tmp_path)[3]
    assert {a: g["listed"] for a, g in hist.items()} == {10: True, 12: False, 13: True}


def test_events_get_their_utc_window(data, tmp_path):
    *_, out = built(data, tmp_path)
    (event,) = json.loads((out / "events.json").read_text(encoding="utf-8"))
    assert event["start"] == "2026-11-25"
    assert event["starts_at"] == "2026-11-25T18:00:00Z"  # 10:00 Pacific
    assert event["ends_at"] == "2026-12-02T18:00:00Z"


def test_rebuilds_are_identical(data, tmp_path):
    d, gp, events = data
    sd.build(d, events, tmp_path / "a", gp)
    sd.build(d, events, tmp_path / "b", gp)
    for name in ("meta.json", "upcoming.json", "history.json", "events.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_the_reference_numbers_run_on_built_files(data, tmp_path):
    _, meta, up, hist, _ = built(data, tmp_path)
    h = hm.heatmap(list(up.values()), date.fromisoformat(meta["snapshot_date"]), [1774])
    assert h["matched"] == {"paid": 3, "free": 2}  # 2 has Free to Play in its tags, 3 Steam's flag
    assert sum(c["exact"] for c in h["paid"] + h["free"]) == 2   # Nov 4 (free flag) and Dec 1 (free tag)
    assert h["sometime"]["2027"]["paid"]["games"] == 1
    assert hm.history_panel(list(hist.values()), [1774])["matched"] == {"paid": 1, "free": 0}


def test_cli_refuses_to_write_into_the_data_folder(data):
    d, _, events = data
    with pytest.raises(SystemExit, match="data folder"):
        sd.main(["--data-dir", str(d), "--out", str(d), "--events", str(events)])


def test_new_wording_for_the_same_dates_is_not_a_move(tmp_path):
    snaps = tmp_path / "s"
    storage.write_csv(snaps / "2026-10-11.csv.gz", [snap(1, "Q4 2026", "quarter", "2026-10-01", "2026-12-31"),
                                                   snap(2, "Nov 2026", "month", "2026-11-01", "2026-11-30")], SNAP)
    storage.write_csv(snaps / "2026-10-12.csv.gz", [snap(1, "Q4, 2026", "quarter", "2026-10-01", "2026-12-31")], SNAP)
    storage.write_csv(snaps / "2026-10-13.csv.gz", [snap(1, "Q4, 2026", "quarter", "2026-10-01", "2026-12-31"),
                                                   snap(2, "Dec 3, 2026", "day", "2026-12-03")], SNAP)
    # game 1 only changed wording; game 2 left for a day and came back with a new date
    assert sd.recent_changes(snaps, date(2026, 10, 13)) == {2: ["moved", "Nov 2026", "2026-10-13"]}


def test_build_without_snapshots_says_so(tmp_path):
    with pytest.raises(SystemExit, match="no upcoming snapshot"):
        sd.build(tmp_path, tmp_path / "events.yaml", tmp_path / "out")
