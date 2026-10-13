from datetime import date

from analysis import trends as tr

TODAY = date(2026, 10, 13)
SHOOTER, COZY = 1774, 97376


def past(day, tags=(SHOOTER,), langs=("english",), free=False, launch_type="full", reviews=None):
    return {"launch_date": day, "launch_type": launch_type, "tags": list(tags), "langs": list(langs), "free": free,
            "reviews_30d": reviews}


def test_quarters_run_from_2022_q1_to_the_partial_quarter_of_today():
    qs = tr.quarters(TODAY)
    assert len(qs) == 20
    assert qs[0] == {"year": 2022, "q": 1, "start": "2022-01-01", "end": "2022-03-31", "length": 90, "days": 90,
                     "partial": False, "recent": False}
    assert qs[8]["start"] == "2024-01-01" and qs[8]["length"] == 91  # a leap year's Q1
    assert qs[-1] == {"year": 2026, "q": 4, "start": "2026-10-01", "end": "2026-12-31", "length": 92, "days": 12,
                      "partial": True, "recent": True}
    assert [q["partial"] for q in qs].count(True) == 1


def test_the_partial_quarter_and_the_two_full_ones_before_it_are_recent():
    qs = tr.quarters(TODAY)
    assert [f"{q['year']} Q{q['q']}" for q in qs if q["recent"]] == ["2026 Q2", "2026 Q3", "2026 Q4"]
    early = tr.quarters(date(2022, 4, 2))  # fewer quarters than the recent ones: all recent
    assert [q["recent"] for q in early] == [True, True]


def test_on_a_quarters_first_day_the_new_quarter_is_there_with_no_days_yet():
    qs = tr.quarters(date(2026, 10, 1))
    assert qs[-1]["q"] == 4 and qs[-1]["days"] == 0 and qs[-1]["partial"]
    assert not qs[-2]["partial"] and qs[-2]["days"] == 92


def test_counts_share_and_running_totals_per_group():
    history = [past("2022-02-01"), past("2022-03-01", tags=(COZY,)), past("2022-04-01", tags=(COZY, SHOOTER)),
               past("2022-04-02", free=True), past("2022-04-03", tags=(COZY,), free=True)]
    q = tr.quarterly(history, TODAY, [SHOOTER])
    assert [(r["niche"], r["all"]) for r in q["paid"][:3]] == [(1, 2), (1, 1), (0, 0)]
    assert q["paid"][0]["share"] == 0.5 and q["paid"][2]["share"] is None
    assert [r["cumulative"] for r in q["paid"][:3]] == [1, 2, 2]
    assert [r["cumulative_all"] for r in q["paid"][:3]] == [2, 3, 3]
    assert (q["free"][1]["niche"], q["free"][1]["all"]) == (1, 2)


def test_launches_are_the_panels_and_count_without_reviews_yet():
    history = [past("2026-07-01", launch_type="early_access"), past("2026-07-02", launch_type="ea_exit"),
               past("2026-07-03", reviews=None), past("2026-07-04", reviews=5)]
    assert tr.quarterly(history, TODAY)["paid"][-2]["all"] == 3


def test_only_games_still_listed():
    history = [past("2026-07-01"), {**past("2026-07-02"), "listed": False}, {**past("2026-07-03"), "listed": True}]
    assert tr.quarterly(history, TODAY)["paid"][-2]["all"] == 2


def test_only_launches_from_2022_and_before_today():
    history = [past("2021-12-31"), past("2022-01-01"), past("2026-10-12"), past("2026-10-13"), past("2027-01-05")]
    q = tr.quarterly(history, TODAY)
    assert q["paid"][0]["all"] == 1 and q["paid"][-1]["all"] == 1
    assert q["paid"][-1]["cumulative_all"] == 2


def test_and_or_and_languages():
    history = [past("2024-05-01", tags=(SHOOTER, COZY)), past("2024-05-02", tags=(COZY,), langs=("schinese",)),
               past("2024-05-03")]
    at = 9  # 2024 Q2
    assert tr.quarterly(history, TODAY, [SHOOTER, COZY], "and")["paid"][at]["niche"] == 1
    assert tr.quarterly(history, TODAY, [SHOOTER, COZY], "or")["paid"][at]["niche"] == 3
    zh = tr.quarterly(history, TODAY, [COZY], "and", ["schinese"])["paid"][at]
    assert (zh["niche"], zh["all"]) == (1, 1)


def test_no_tags_is_every_launch():
    history = [past("2023-01-05"), past("2023-01-06", tags=(COZY,))]
    row = tr.quarterly(history, TODAY)["paid"][4]
    assert (row["niche"], row["all"], row["share"]) == (2, 2, 1.0)
