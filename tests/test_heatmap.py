from datetime import date

import pytest

from analysis import heatmap as hm

TODAY = date(2026, 10, 12)  # a Monday
SHOOTER, ROGUELIKE, COZY = 1774, 1716, 97376


def game(precision, start=None, end=None, tags=(SHOOTER,), free=False, followers=None, langs=("english",)):
    return {"precision": precision, "date": start, "date_end": end or start, "tags": list(tags),
            "langs": list(langs), "free": free, "followers": followers}


def test_weeks_start_on_monday():
    assert hm.week_start(date(2026, 10, 18)) == date(2026, 10, 12)  # Sunday
    assert hm.week_start(date(2026, 10, 12)) == date(2026, 10, 12)


def test_matching_any_tag_with_and_or_mode():
    tags = [ROGUELIKE, 492, SHOOTER]  # shooter low in the list still matches
    assert hm.matches(tags, [SHOOTER, ROGUELIKE], "and")
    assert not hm.matches(tags, [SHOOTER, COZY], "and")
    assert hm.matches(tags, [SHOOTER, COZY], "or")
    assert hm.matches(tags, [], "and")


def test_language_filter():
    assert hm.speaks(["english"], [])
    assert hm.speaks(["english", "schinese"], ["schinese"])
    assert not hm.speaks(["english"], ["schinese"])


def test_day_dates_count_once_in_their_week_and_only_inside_the_window():
    games = [game("day", "2026-10-14"), game("day", "2026-10-25"), game("day", "2026-10-05"),
             game("day", "2027-06-01")]
    h = hm.heatmap(games, TODAY)
    assert [c["exact"] for c in h["paid"][:3]] == [1, 1, 0]
    assert sum(c["exact"] for c in h["paid"]) == 2  # last week and 33 weeks out are not shown
    assert h["weeks"][0] == "2026-10-12" and len(h["weeks"]) == 26


def test_month_dates_spread_only_over_days_still_ahead():
    h = hm.heatmap([game("month", "2026-10-01", "2026-10-31")], TODAY)
    spread = [c["spread"] for c in h["paid"][:4]]
    assert spread == pytest.approx([7 / 20, 7 / 20, 6 / 20, 0])  # Oct 12 to 31 is 20 days
    assert sum(spread) == pytest.approx(1)


def test_a_quarter_seen_on_december_1_goes_to_december_only():
    h = hm.heatmap([game("quarter", "2026-10-01", "2026-12-31")], date(2026, 12, 1))
    assert h["weeks"][0] == "2026-11-30"
    assert h["paid"][0]["spread"] == pytest.approx(6 / 31)  # Dec 1 to 6
    assert sum(c["spread"] for c in h["paid"]) == pytest.approx(1)


def test_a_range_that_ran_out_adds_nothing():
    h = hm.heatmap([game("month", "2026-09-01", "2026-09-30")], TODAY)
    assert sum(c["spread"] for c in h["paid"]) == 0


def test_year_dates_are_a_separate_layer_and_a_yearly_total():
    games = [game("year", "2026-01-01", "2026-12-31", followers=100), game("year", "2027-01-01", "2027-12-31")]
    h = hm.heatmap(games, TODAY)
    assert all(c["spread"] == 0 and c["exact"] == 0 for c in h["paid"])
    days_left = (date(2026, 12, 31) - TODAY).days + 1
    assert h["paid"][0]["year"] == pytest.approx(7 / days_left)
    assert h["paid"][0]["year_hype"] == pytest.approx(700 / days_left)
    assert h["paid"][0]["no_hype"] == 0  # year games stay out of the main numbers
    assert h["sometime"]["2026"]["paid"] == {"games": 1, "hype": 100, "no_hype": 0}
    assert h["sometime"]["2027"]["paid"]["games"] == 1


def test_far_off_years_are_summed_as_later():
    games = [game("year", "2028-01-01", "2028-12-31"), game("year", "2099-01-01", "2099-12-31"),
             game("year", "2037-01-01", "2037-12-31")]
    assert list(hm.heatmap(games, TODAY)["sometime"]) == ["2028", "later"]
    assert hm.heatmap(games, TODAY)["sometime"]["later"]["paid"]["games"] == 2


def test_free_games_and_hype_are_counted_apart():
    games = [game("day", "2026-10-14", followers=500), game("day", "2026-10-14"),
             game("day", "2026-10-14", free=True, followers=50)]
    h = hm.heatmap(games, TODAY)
    assert h["paid"][0] == {"exact": 2, "spread": 0, "year": 0, "hype": 500, "year_hype": 0, "no_hype": 1}
    assert h["free"][0]["exact"] == 1 and h["free"][0]["hype"] == 50


def test_selection_and_match_count():
    games = [game("day", "2026-10-14", tags=(SHOOTER, ROGUELIKE)), game("day", "2026-10-14", tags=(SHOOTER,)),
             game("unknown", tags=(COZY,)), game("day", "2026-10-14", tags=(SHOOTER,), langs=("schinese",))]
    h = hm.heatmap(games, TODAY, [SHOOTER, ROGUELIKE], "and")
    assert (h["matched"], h["total"], h["paid"][0]["exact"]) == (1, 4, 1)
    h = hm.heatmap(games, TODAY, [ROGUELIKE, COZY], "or")
    assert h["matched"] == 2 and h["paid"][0]["exact"] == 1  # the cozy game has no date
    assert hm.heatmap(games, TODAY, [SHOOTER], languages=["english"])["matched"] == 2


def test_percentile_interpolates_like_numpy():
    assert hm.percentile([1, 2, 3, 4], 0.5) == 2.5
    assert hm.percentile([0, 10], 0.9) == 9
    assert hm.percentile([7], 0.75) == 7


def past(day, reviews, tags=(SHOOTER,), free=False, launch_type="full"):
    return {"launch_date": day, "launch_type": launch_type, "tags": list(tags), "langs": ["english"],
            "free": free, "reviews_30d": reviews}


def test_busy_counts_other_matching_launches_of_the_same_group_that_week():
    history = [past("2026-01-05", 10), past("2026-01-07", 20), past("2026-01-11", 30),  # one week, 3 launches
               past("2026-01-12", 40),                                               # next week, alone
               past("2026-01-06", 5, free=True), past("2026-01-06", 5, tags=(COZY,)),
               past("2026-01-06", 5, launch_type="ea_exit")]
    panel = hm.history_panel(history, [SHOOTER], min_group=1)
    parts = panel["paid"]["parts"]
    assert panel["matched"] == 5 and panel["total"] == 6  # ea_exit is not a past launch here
    assert parts["quiet"]["busy_max"] == 0 and parts["quiet"]["games"] == 1
    assert sum(p["games"] for p in parts.values()) == 4
    assert max(p.get("busy_max", 0) for p in parts.values()) == 2


def test_panel_hides_a_group_with_too_few_games():
    history = [past(f"2026-0{1 + i % 6}-0{1 + i % 7}", i) for i in range(60)]
    panel = hm.history_panel(history, [SHOOTER])
    assert panel["paid"]["shown"] is False  # 60 games cannot fill three parts of 30
    assert "median" not in next(p for p in panel["paid"]["parts"].values() if p["games"] < 30)
    assert panel["free"] == {"games": 0, "shown": False, "parts": {n: {"games": 0} for n in ("quiet", "normal", "busy")}}


def test_cut_points_keep_equal_counts_together():
    assert hm.cut_points([0, 2, 2, 2]) == (0, 2)  # not (2, 2), which would put everything in quiet
    assert hm.cut_points([0] * 40 + [1] * 40 + [3] * 40) == (0, 1)
    assert hm.cut_points([5, 5, 5]) == (5, 5)
    assert hm.cut_points([]) is None


def test_panel_reports_review_percentiles_per_part():
    from datetime import timedelta
    history, week = [], date(2024, 1, 1)
    # 40 lone launches (busy 0), 20 weeks of 2 (busy 1), 10 weeks of 4 (busy 3)
    for weeks, size, reviews in ((40, 1, 100), (20, 2, 50), (10, 4, 20)):
        for _ in range(weeks):
            history += [past(week.isoformat(), reviews)] * size
            week += timedelta(weeks=1)
    panel = hm.history_panel(history, [SHOOTER])
    parts = panel["paid"]["parts"]
    assert panel["paid"]["shown"] is True
    assert [parts[n]["games"] for n in ("quiet", "normal", "busy")] == [40, 40, 40]
    assert [parts[n]["median"] for n in ("quiet", "normal", "busy")] == [100, 50, 20]
    assert (parts["busy"]["busy_min"], parts["busy"]["busy_max"]) == (3, 3)
