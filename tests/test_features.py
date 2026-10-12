import gzip
import math
from datetime import date, datetime, timedelta, timezone

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("scipy")

from analysis import features as F  # noqa: E402
from pipeline import storage  # noqa: E402
from pipeline.collect_history import FIELDS  # noqa: E402
from pipeline.events import PACIFIC  # noqa: E402

ROGUE, ACTION, PUZZLE, INDIE = 1716, 19, 1664, 492
NAMES = {ROGUE: "Roguelike", ACTION: "Action", PUZZLE: "Puzzle", INDIE: "Indie"}
WED = date(2024, 6, 12)  # a Wednesday


def at(d: date, hour: int = 10, minute: int = 0, second: int = 0) -> int:
    return int(datetime(d.year, d.month, d.day, hour, minute, second, tzinfo=PACIFIC).timestamp())


def row(appid, day=WED, tags=((ROGUE, 100),), langs="english", price=999, free="0", hour=10, **kw):
    r = dict.fromkeys(FIELDS, "")
    r.update(appid=appid, name=f"g{appid}", launch_date=day.isoformat(), launch_ts=at(day, hour), launch_type="full",
             price_cents=price, is_free=free, tags="|".join(f"{t}:{w}" for t, w in tags), languages=langs,
             reviews_30d=5, reviews_30d_source="api")
    r.update(kw)
    return r


def frame(tmp_path, rows):
    path = tmp_path / "games.csv"
    storage.write_csv(path, rows, FIELDS)
    return F.load_history(path)


def test_parse_tags_heaviest_first():
    assert F.parse_tags("19:5|1716:9|492:5") == [(1716, 9), (19, 5), (492, 5)]
    assert F.parse_tags("") == []


def test_load_history_fields(tmp_path):
    df = frame(tmp_path, [row(1, price="", free="1", audio_languages="english|french", demo_before_launch="1",
                              publishers="A|B", franchises="F", reviews_30d="")])
    g = df.iloc[0]
    assert g["free"] and math.isnan(g["price"]) and g["en_audio"] and g["demo"] and g["franchise"]
    assert g["publishers"] == ["A", "B"] and math.isnan(g["reviews_30d"])
    assert g["week"] == date(2024, 6, 10) and g["dow"] == 2 and g["hour"] == 10


def test_free_to_play_tag_in_top_10_makes_a_game_free(tmp_path):
    df = frame(tmp_path, [row(1, tags=((113, 50), (ROGUE, 100)))])
    assert df.iloc[0]["free"]


# --- sample -----------------------------------------------------------------

def test_sample_filters_and_counts(tmp_path):
    today = date(2026, 10, 12)
    df = frame(tmp_path, [
        row(1),
        row(2, launch_type="early_access"),
        row(3, launch_type="ea_exit"),
        row(4, reviews_30d="", reviews_30d_source="unavailable"),
        row(5, day=today - timedelta(days=30)),             # window not closed
        row(6, day=today - timedelta(days=31)),             # just in
        row(7, day=date(2021, 12, 31)),                     # before the sample
        row(8, day=date(2022, 1, 2)),                       # its week started in 2021
        row(9, day=date(2022, 1, 3)),
        row(10, reviews_30d="", reviews_30d_source=""),
    ])
    kept, counts = F.sample(df, today)
    assert sorted(kept["appid"]) == [1, 2, 6, 9]
    assert counts["ea_exit"] == 1 and counts["unavailable_reviews"] == 1 and counts["no_review_count"] == 1
    assert counts["week_before_data"] == 1 and counts["in_period"] == 8 and counts["kept"] == 4
    assert counts["sample_end"] == "2026-09-11"


def test_prelaunch_tags_override_only_before_launch(tmp_path):
    df = frame(tmp_path, [row(1), row(2)])
    apps = tmp_path / "apps.csv"
    storage.write_csv(apps, [{"appid": 1, "tags": f"{PUZZLE}:7", "last_seen": "2024-06-11"},
                             {"appid": 2, "tags": f"{PUZZLE}:7", "last_seen": "2024-06-12"}],
                      ["appid", "tags", "last_seen"])
    assert F.prelaunch_tags(df, apps) == 1
    assert df.iloc[0]["tags"] == [(PUZZLE, 7)] and df.iloc[1]["tags"] == [(ROGUE, 100)]


# --- niche competition ------------------------------------------------------

def test_cosine_threshold(tmp_path):
    df = frame(tmp_path, [
        row(1, tags=((ROGUE, 1),)),
        row(2, tags=((ROGUE, 1), (ACTION, 3))),   # cosine 1/sqrt(10) = 0.316: same niche
        row(3, tags=((ROGUE, 1), (ACTION, 4))),   # 1/sqrt(17) = 0.243: not
        row(4, tags=((PUZZLE, 9),)),              # no shared tag
    ])
    counts = F.similar_counts(df.iloc[:1], df)
    assert list(counts) == [1]


def test_needs_a_shared_major_language(tmp_path):
    df = frame(tmp_path, [
        row(1, langs="english|polish"),
        row(2, langs="schinese"),            # no shared language
        row(3, langs="polish"),              # shares only a minor language
        row(4, langs="english|schinese"),
        row(5, langs="japanese|english"),
    ])
    assert list(F.similar_counts(df.iloc[:1], df)) == [2]
    assert list(F.similar_counts(df.iloc[1:2], df)) == [1]   # schinese meets only game 4


def test_same_week_and_placebo_shift(tmp_path):
    monday = WED - timedelta(days=2)
    df = frame(tmp_path, [
        row(1),
        row(2, day=monday),
        row(3, day=monday + timedelta(days=6)),          # Sunday, same week
        row(4, day=monday + timedelta(days=7)),          # next Monday
        row(5, day=monday - timedelta(days=1)),          # Sunday before
        row(6, day=WED + timedelta(weeks=8)),
        row(7, day=WED + timedelta(weeks=8, days=1)),
    ])
    target = df.iloc[:1]
    assert list(F.similar_counts(target, df)) == [2]
    assert list(F.similar_counts(target, df, offset_weeks=8)) == [2]
    assert list(F.similar_counts(target, df, offset_weeks=1)) == [1]


def test_top_n_tags_change_the_niche(tmp_path):
    df2 = frame(tmp_path, [
        row(1, tags=[(t, 100) for t in range(1, 6)] + [(ROGUE, 99)]),
        row(2, tags=[(ROGUE, 100)]),
    ])
    assert list(F.similar_counts(df2.iloc[:1], df2, top=5)) == [0]
    assert list(F.similar_counts(df2.iloc[:1], df2, top=10)) == [1]  # cosine 99/sqrt(5*100^2+99^2) = 0.40


def test_primary_tag_rule_and_same_tier(tmp_path):
    df = frame(tmp_path, [
        row(1, tags=((ROGUE, 10), (ACTION, 9)), price=999),
        row(2, tags=((ROGUE, 10),), price=1000),     # same primary tag, $10: other tier
        row(3, tags=((ACTION, 10), (ROGUE, 9)), price=500),
    ])
    t = df.iloc[:1]
    assert list(F.similar_counts(t, df, rule="primary")) == [1]
    assert list(F.similar_counts(t, df)) == [2]
    assert list(F.similar_counts(t, df, same_tier=True)) == [1]


def test_tiers():
    assert [F.tier(p) for p in (math.nan, 0, 4.99, 9.99, 10, 25, 25.01)] == [-1, -1, 0, 0, 1, 1, 2]


def test_niche_median_price(tmp_path):
    rows = [row(1, price=2500)] + [row(i, price=p) for i, p in zip(range(2, 8), (100, 200, 300, 400, 500, 600))]
    rows += [row(20, tags=((PUZZLE, 1),), price=9999), row(21, price=0), row(22, langs="schinese", price=9999)]
    df = frame(tmp_path, rows)
    med = F.niche_median_price(df, df)
    assert med[0] == pytest.approx(3.5)        # $1 to $6; itself, the puzzle, the $0 and the Chinese-only game left out
    assert med[1] == pytest.approx(4.5)        # $2 to $6 and $25
    assert math.isnan(med[7])                  # the puzzle game has no niche


# --- events -----------------------------------------------------------------

def ev(name, kind, start, end=None, **kw):
    return {"name": name, "type": kind, "start": start, "end": end or start, **kw}


SALE = ev("Steam Summer Sale 2024", "seasonal_sale", date(2024, 6, 27), date(2024, 7, 11))


def events_for(tmp_path, rows, events):
    df = frame(tmp_path, rows)
    return df, F.event_features(df, events, NAMES)


def test_sale_window_in_pacific_time(tmp_path):
    start = date(2024, 6, 27)
    rows = [row(1, day=start, hour=9, launch_ts=at(start, 9, 59, 59)),
            row(2, day=start, launch_ts=at(start, 10)),
            row(3, day=date(2024, 7, 11), launch_ts=at(date(2024, 7, 11), 9, 59)),
            row(4, day=date(2024, 7, 11), launch_ts=at(date(2024, 7, 11), 10)),
            row(5, day=date(2024, 6, 20), launch_ts=at(date(2024, 6, 20), 10)),        # exactly 7 days before
            row(6, day=date(2024, 6, 20), launch_ts=at(date(2024, 6, 20), 9, 59))]     # just over 7 days
    _, e = events_for(tmp_path, rows, [SALE])
    assert list(e["sale"]) == [0, 1, 1, 0, 0, 0]
    assert list(e["pre_sale"]) == [1, 0, 0, 0, 1, 0]


def test_sale_window_uses_utc_launch_time_not_date(tmp_path):
    # 17:30 UTC on Jun 27 is 10:30 Pacific (summer time): inside
    ts = int(datetime(2024, 6, 27, 17, 30, tzinfo=timezone.utc).timestamp())
    _, e = events_for(tmp_path, [row(1, day=date(2024, 6, 27), launch_ts=ts)], [SALE])
    assert e["sale"].iloc[0] == 1


def test_next_fest_and_demo_in_the_last_fest(tmp_path):
    fests = [ev("Steam Next Fest February 2024", "next_fest", date(2024, 2, 5), date(2024, 2, 12)),
             ev("Steam Next Fest June 2024", "next_fest", date(2024, 6, 10), date(2024, 6, 17))]
    feb_end = at(date(2024, 2, 12))
    rows = [row(1, day=WED),                                                            # during June fest
            row(2, day=date(2024, 3, 6), demo_release_ts=feb_end - 1, demo_before_launch="1"),
            row(3, day=date(2024, 3, 6), demo_release_ts=feb_end + 1, demo_before_launch="1"),
            row(4, day=date(2024, 3, 6)),
            row(5, day=WED, demo_release_ts=feb_end - 1),                               # last ended fest: Feb
            row(6, day=date(2024, 1, 10), demo_release_ts=at(date(2024, 1, 1)))]       # no fest before
    _, e = events_for(tmp_path, rows, fests)
    assert list(e["next_fest"]) == [1, 0, 0, 0, 1, 0]
    assert list(e["demo_last_fest"]) == [0, 1, 0, 0, 1, 0]


def test_themed_fest_needs_a_top_10_tag(tmp_path):
    fest = ev("Steam Going Rogue Fest 2024", "themed_fest", date(2024, 6, 10), date(2024, 6, 17), tags=["Roguelike"])
    untagged = ev("Steam Some Fest 2024", "themed_fest", date(2024, 6, 10), date(2024, 6, 17))
    eleventh = [(t, 100) for t in range(1, 11)] + [(ROGUE, 1)]
    rows = [row(1), row(2, tags=((PUZZLE, 1),)), row(3, tags=eleventh), row(4, day=date(2024, 6, 18))]
    _, e = events_for(tmp_path, rows, [fest, untagged])
    assert list(e["themed_fest"]) == [1, 0, 0, 0]


def test_big_competitor_rules(tmp_path):
    day = date(2024, 6, 12)
    rel = dict(on_steam_at_launch=True, release_kind="full", steam_appid=999)
    events = [ev("Big Game", "major_release", day, **rel)]
    rows = [row(1, day=day + timedelta(days=3)), row(2, day=day - timedelta(days=3)),
            row(3, day=day + timedelta(days=4)), row(999, day=day)]
    _, e = events_for(tmp_path, rows, events)
    assert list(e["big_competitor"]) == [1, 1, 0, 0]
    variants = [ev("F2P", "major_release", day, **rel, free_to_play=True),
                ev("Console", "major_release", day, on_steam_at_launch=False, release_kind="full"),
                ev("Shadow", "major_release", day, **rel, surprise="shadow_drop"),
                ev("DLC", "major_release", day, **{**rel, "release_kind": "expansion"})]
    for event, big, attention in zip(variants, (0, 0, 0, 0), (1, 1, 0, 0)):
        _, e = events_for(tmp_path, [row(1, day=day)], [event])
        assert (e["big_competitor"].iloc[0], e["attention_release"].iloc[0]) == (big, attention), event["name"]


def test_holidays_cover_whole_pacific_days(tmp_path):
    hol = ev("China Spring Festival holiday 2024", "regional_holiday", date(2024, 2, 10), date(2024, 2, 17),
             region="CN")
    rows = [row(1, day=date(2024, 2, 10), launch_ts=at(date(2024, 2, 10), 0)),
            row(2, day=date(2024, 2, 17), launch_ts=at(date(2024, 2, 17), 23, 59)),
            row(3, day=date(2024, 2, 18), launch_ts=at(date(2024, 2, 18), 0))]
    _, e = events_for(tmp_path, rows, [hol])
    assert list(e["cn_spring"]) == [1, 1, 0]


# --- followers --------------------------------------------------------------

def test_followers_at_interpolates_and_limits_one_sided():
    day = F.DAY
    series = (pd.Series([0, 10 * day]).to_numpy(dtype=float), pd.Series([100, 200]).to_numpy(dtype=float))
    assert F.followers_at(series, 0) == 100
    assert F.followers_at(series, 5 * day) == 150
    assert F.followers_at(series, 12 * day) == 200          # 2 days after the last point
    assert F.followers_at(series, 12 * day + 1) is None
    assert F.followers_at(series, -2 * day) == 100
    assert F.followers_at(series, -3 * day) is None
    assert F.followers_at(None, 0) is None


def test_load_followers_and_value_7_days_before_launch(tmp_path):
    launch = date(2024, 6, 20)
    week_before = datetime(2024, 6, 13, 10, tzinfo=PACIFIC)
    fdir = tmp_path / "gp" / "followers"
    fdir.mkdir(parents=True)
    lines = ["appid,followers,observed_at,fetched_at",
             f"1,90,{(week_before - timedelta(days=1)).isoformat()},2026-10-12T00:00:00+00:00",
             f"1,110,{(week_before + timedelta(days=1)).isoformat()},2026-10-12T00:00:00+00:00",
             f"1,500,{(week_before + timedelta(days=1)).isoformat()},2026-10-01T00:00:00+00:00",  # older fetch
             f"1,,{week_before.isoformat()},2026-10-12T00:00:00+00:00",
             f"2,50,{(week_before + timedelta(days=5)).isoformat()},2026-10-12T00:00:00+00:00"]
    with gzip.open(fdir / "2026-10-12.csv.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    series = F.load_followers(tmp_path / "gp")
    assert list(series[1][1]) == [90, 110]
    df = frame(tmp_path, [row(1, day=launch, launch_ts=at(launch)), row(2, day=launch, launch_ts=at(launch)),
                          row(3, day=launch)])
    values = F.prelaunch_followers(df, series)
    assert values.iloc[0] == pytest.approx(math.log1p(100))
    assert values.iloc[1:].isna().all()
    assert F.load_followers(None) == {}


# --- other ------------------------------------------------------------------

def test_publisher_reach_counts_earlier_launches(tmp_path):
    df = frame(tmp_path, [row(1, day=date(2023, 1, 4), publishers="A"),
                          row(2, day=date(2023, 2, 1), publishers="A|B"),
                          row(3, day=date(2023, 3, 1), publishers="B"),
                          row(4, day=date(2023, 3, 1), publishers="B"),        # same time as 3: not earlier
                          row(5, day=date(2023, 4, 5), publishers="A|B"),
                          row(6, day=date(2023, 5, 3), publishers="")])
    assert list(F.publisher_reach(df)) == [0, 1, 1, 1, 3, 0]


def test_placebo_needs_a_complete_week(tmp_path):
    df = frame(tmp_path, [row(1, day=date(2024, 6, 12)), row(2, day=date(2024, 6, 19))])
    # 8 weeks after the week of Jun 10 is Aug 5 to 11; data through Aug 12 covers it
    assert list(F.placebo_ok(df, date(2024, 8, 12), 8)) == [True, False]


def test_pool_is_same_group_full_or_early_access(tmp_path):
    df = frame(tmp_path, [row(1), row(2, free="1"), row(3, launch_type="ea_exit"), row(4, launch_type="early_access")])
    assert list(F.pool_of(df, False)["appid"]) == [1, 4]
    assert list(F.pool_of(df, True)["appid"]) == [2]
