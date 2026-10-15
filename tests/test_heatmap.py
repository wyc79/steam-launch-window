from datetime import date, timedelta

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
             game("day", "2027-01-10"), game("day", "2027-01-11"), game("day", "2027-06-01")]
    h = hm.heatmap(games, TODAY)
    assert [c["exact"] for c in h["paid"][:3]] == [1, 1, 0]
    assert h["paid"][-1]["exact"] == 1  # Sunday Jan 10 is in the 13th week; Jan 11 starts the 14th
    assert sum(c["exact"] for c in h["paid"]) == 3  # last week and weeks after the 13th are not shown
    assert h["weeks"][0] == "2026-10-12" and len(h["weeks"]) == hm.WEEKS == 13


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
    assert (h["matched"], h["total"], h["paid"][0]["exact"]) == ({"paid": 1, "free": 0}, {"paid": 4, "free": 0}, 1)
    h = hm.heatmap(games, TODAY, [ROGUELIKE, COZY], "or")
    assert h["matched"]["paid"] == 2 and h["paid"][0]["exact"] == 1  # the cozy game has no date
    assert hm.heatmap(games, TODAY, [SHOOTER], languages=["english"])["matched"]["paid"] == 2


def test_match_count_follows_the_group():
    games = [game("day", "2026-10-14"), game("day", "2026-10-14", free=True), game("day", "2026-10-14", tags=(COZY,))]
    history = [past("2026-01-05", 1), past("2026-01-05", 1, free=True), past("2026-01-05", 1, tags=(COZY,)),
               past("2026-01-05", 1, launch_type="ea_exit")]
    assert hm.match_count(games, history, [SHOOTER]) == {"paid": {"upcoming": [1, 2], "past": [1, 2]},
                                                         "free": {"upcoming": [1, 1], "past": [1, 1]}}


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
    panel = hm.history_panel(history, [SHOOTER], min_group=1, measure="raw")
    parts = panel["paid"]["parts"]
    assert panel["matched"] == {"paid": 4, "free": 1}  # the cozy launch is not a shooter
    assert panel["total"] == {"paid": 5, "free": 1}    # ea_exit is not a past launch here
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
    panel = hm.history_panel(history, [SHOOTER], measure="raw")
    parts = panel["paid"]["parts"]
    assert panel["paid"]["shown"] is True
    assert [parts[n]["games"] for n in ("quiet", "normal", "busy")] == [40, 40, 40]
    assert [parts[n]["median"] for n in ("quiet", "normal", "busy")] == [100, 50, 20]
    assert (parts["busy"]["busy_min"], parts["busy"]["busy_max"]) == (3, 3)


def test_typical_week_is_the_average_week_of_real_launches_last_year():
    history = ([past("2026-01-05", 10)] * 104 + [past("2026-03-02", 10, free=True)] * 26
               + [past("2025-10-01", 10)] * 50          # more than 52 weeks before TODAY: not counted
               + [past("2026-10-12", 10)]                 # TODAY itself: not counted
               + [past("2026-02-02", 10, launch_type="ea_exit")] + [past("2026-02-02", 10, tags=(COZY,))])
    h = hm.heatmap([game("day", "2026-10-14")], TODAY, [SHOOTER], history=history)
    assert h["typical"] == {"paid": 2.0, "free": 0.5}
    assert hm.heatmap([game("day", "2026-10-14")], TODAY)["typical"] is None


def weekly(counts, start=date(2024, 1, 1)):
    from datetime import timedelta
    rows = []
    for i, n in enumerate(counts):
        rows += [past((start + timedelta(weeks=i)).isoformat(), 10)] * n
    return rows


def test_relative_busy_compares_a_week_with_the_weeks_before_it():
    counts = [2] * 27
    counts[13] = 6
    panel = hm.history_panel(weekly(counts), [SHOOTER], min_group=1)  # relative is the default
    assert panel["measure"] == "relative"
    parts = panel["paid"]["parts"].values()
    assert max(p.get("busy_max", 0) for p in parts) == 2.5   # 5 others against 2 a week before
    assert min(p.get("busy_min", 9) for p in parts) == 0.43  # 1 other against 30/13 with the spike in the past
    assert sum(p["games"] for p in parts) == 2 * 13 + 6      # the first 13 weeks have no baseline
    raw = hm.history_panel(weekly(counts), [SHOOTER], min_group=1, measure="raw")
    assert raw["measure"] == "raw" and max(p.get("busy_max", 0) for p in raw["paid"]["parts"].values()) == 5
    assert sum(p["games"] for p in raw["paid"]["parts"].values()) == sum(counts)


def test_relative_busy_removes_slow_growth():
    counts = [5 + i // 4 for i in range(104)]  # launches grow from 5 to 30 a week over two years
    raw = hm.history_panel(weekly(counts), [SHOOTER], min_group=1, measure="raw")
    assert max(p["busy_max"] for p in raw["paid"]["parts"].values()) == 29
    panel = hm.history_panel(weekly(counts), [SHOOTER], min_group=1)
    interior = [p for p in panel["paid"]["parts"].values() if p["games"]]
    # every week is about usual; the past lags behind growth, so weeks read a little high (up to 1.3 here)
    assert all(0.9 <= p["busy_min"] and p["busy_max"] <= 1.35 for p in interior)


def test_relative_busy_puts_a_lone_launch_in_a_small_niche_in_quiet():
    counts = [0] * 40
    for i in range(14, 40, 2):
        counts[i] = 1          # one launch every other week: usual is about half a launch
    counts[39] = 3
    panel = hm.history_panel(weekly(counts), [SHOOTER], min_group=1)
    parts = panel["paid"]["parts"]
    assert parts["quiet"]["busy_max"] == 0.0     # alone in its week: no competition
    assert max(p.get("busy_max", 0) for p in parts.values()) == 2.0  # 2 others against a floor of 1


def test_rows_are_each_tag_then_the_combination():
    games = [game("day", "2026-10-14", tags=(SHOOTER, ROGUELIKE)), game("day", "2026-10-14", tags=(ROGUELIKE,))]
    rows = hm.heatmap_rows(games, TODAY, [SHOOTER, ROGUELIKE], "or")
    assert [(r["tags"], r["matched"]["paid"]) for r in rows] == [([SHOOTER], 1), ([ROGUELIKE], 2),
                                                                ([SHOOTER, ROGUELIKE], 2)]
    assert [r["tags"] for r in hm.heatmap_rows(games, TODAY, [SHOOTER])] == [[SHOOTER]]
    assert [r["matched"]["paid"] for r in hm.heatmap_rows(games, TODAY)] == [2]  # no tags: all games


def test_normalized_divides_by_the_typical_week():
    history = [past("2026-03-02", 10)] * 104  # 2 a week for paid, none for free
    h = hm.heatmap([game("day", "2026-10-14"), game("month", "2026-10-01", "2026-10-31")], TODAY, history=history)
    norm = hm.normalized(h)
    assert norm["paid"][0] == pytest.approx({"exact": 0.5, "spread": 7 / 20 / 2, "year": 0})
    assert norm["free"] is None  # no usual week to compare with
    assert hm.normalized(hm.heatmap([], TODAY)) is None


def test_week_games_list_top_10_matches_first_then_big_names():
    low = [492, 19, 21, 4182, 597, 1742, 3871, 1625, 4166, 1664, SHOOTER]  # shooter is 11th
    games = [dict(game("day", "2026-10-14", tags=low, followers=9000), appid=1, name="Low", moved=None),
             dict(game("day", "2026-10-15", followers=10), appid=2, name="Small", moved=None),
             dict(game("day", "2026-10-16"), appid=3, name="Unknown", moved=["moved", "October 2026", "2026-10-09"]),
             dict(game("month", "2026-10-01", "2026-10-31", followers=500), appid=4, name="Vague", moved=None),
             dict(game("day", "2026-10-20"), appid=5, name="Next week", moved=None)]
    listed = hm.week_games(games, TODAY, date(2026, 10, 12), [SHOOTER])
    assert [g["appid"] for g in listed] == [4, 2, 3, 1]
    assert listed[0]["layer"] == "spread" and listed[0]["share"] == pytest.approx(7 / 20)
    assert listed[2]["moved"] == ["moved", "October 2026", 3]  # changed 3 days ago
    assert listed[3]["top10"] is False


def test_week_games_with_year_dates_over_the_year_end():
    games = [dict(game("year", "2026-01-01", "2026-12-31", followers=50), appid=1, name="This year", moved=None),
             dict(game("year", "2027-01-01", "2027-12-31"), appid=2, name="Next year", moved=None),
             dict(game("day", "2027-01-01", followers=40), appid=3, name="New Year Day", moved=None)]
    today, week = date(2026, 12, 23), date(2026, 12, 28)  # Dec 28 to Jan 3, ISO week 53
    assert [g["appid"] for g in hm.week_games(games, today, week)] == [3]  # year dates only on request
    listed = hm.week_games(games, today, week, year=True)
    assert [(g["appid"], g["layer"]) for g in listed] == [(1, "year"), (3, "exact"), (2, "year")]
    assert listed[0]["share"] == pytest.approx(4 / 9)    # Dec 28 to 31 of the 9 days left in 2026
    assert listed[2]["share"] == pytest.approx(3 / 365)  # Jan 1 to 3 of 2027


def test_week_games_in_or_mode_carry_group_and_hype_source():
    low = [492, 19, 21, 4182, 597, 1742, 3871, 1625, 4166, 1664, ROGUELIKE]  # roguelike is 11th
    games = [dict(game("day", "2026-10-14", tags=(COZY,), free=True, followers=70), appid=1, name="Cozy",
                  moved=None, hype_src="r"),
             dict(game("day", "2026-10-14", tags=low, followers=900), appid=2, name="Low", moved=None, hype_src="f"),
             dict(game("day", "2026-10-14", tags=(SHOOTER,)), appid=3, name="Shooter", moved=None),
             dict(game("day", "2026-10-15", tags=(ROGUELIKE, *low)), appid=4, name="Rogue", moved=None)]
    listed = hm.week_games(games, TODAY, date(2026, 10, 12), [ROGUELIKE, COZY], "or")
    assert [(g["appid"], g["top10"]) for g in listed] == [(1, True), (4, True), (2, False)]
    assert (listed[0]["free"], listed[0]["hype_src"]) == (True, "r")  # an estimate from wishlist rank
    assert (listed[2]["free"], listed[2]["hype_src"]) == (False, "f")
    assert listed[1]["hype_src"] is None


def test_most_anticipated_orders_by_rank_at_any_date_and_ignores_followers():
    games = [dict(game("unknown", followers=90000), appid=1, name="Undated", wishlist_rank=40, hype_src="r",
                  date_text="Coming soon"),
             dict(game("day", "2027-06-01"), appid=2, name="Far", wishlist_rank=3),
             dict(game("year", "2028-01-01", "2028-12-31", tags=(COZY,)), appid=3, name="Cozy", wishlist_rank=1),
             dict(game("day", "2026-10-14", followers=500000), appid=4, name="Unranked", wishlist_rank=None),
             dict(game("quarter", "2027-01-01", "2027-03-31", free=True), appid=5, name="Free", wishlist_rank=2)]
    top = hm.most_anticipated(games, [SHOOTER])
    assert [g["appid"] for g in top["paid"]["games"]] == [2, 1]  # rank 3 before rank 40, whatever the followers
    assert top["paid"]["total"] == 3
    assert top["paid"]["games"][1] == {"appid": 1, "name": "Undated", "precision": "unknown", "date": None,
                                       "date_text": "Coming soon", "wishlist_rank": 40,
                                       "tag_pos": [[SHOOTER, 1]], "tag_count": 1}  # no followers in it
    assert top["paid"]["games"][0]["date_text"] is None
    assert [g["appid"] for g in top["free"]["games"]] == [5]
    assert [g["appid"] for g in hm.most_anticipated(games, limit=1)["paid"]["games"]] == [3]
    assert hm.most_anticipated(games, [COZY, SHOOTER])["paid"] == {"games": [], "total": 3}


def test_tag_pos_gives_each_picked_tags_place():
    tags = [492, 19, 21, 4182, 597, ROGUELIKE, 1742, 3871, 1625, 4166, 1664, SHOOTER]
    assert hm.tag_pos(tags, [SHOOTER, ROGUELIKE]) == [[SHOOTER, 12], [ROGUELIKE, 6]]  # in the selection's order
    assert hm.tag_pos(tags, [COZY, SHOOTER]) == [[SHOOTER, 12]]  # only the tags the game has (or mode)
    assert hm.tag_pos(tags, []) == []


def test_week_games_and_most_anticipated_carry_tag_places():
    low = [492, 19, 21, 4182, 597, 1742, 3871, 1625, 4166, 1664, SHOOTER, COZY]
    games = [dict(game("day", "2026-10-14", tags=low), appid=1, name="Low", moved=None, wishlist_rank=5),
             dict(game("day", "2026-10-15", tags=(COZY,)), appid=2, name="Cozy", moved=None, wishlist_rank=9)]
    listed = hm.week_games(games, TODAY, date(2026, 10, 12), [SHOOTER, COZY], "or")
    assert [(g["appid"], g["tag_pos"], g["tag_count"]) for g in listed] == [
        (2, [[COZY, 1]], 1), (1, [[SHOOTER, 11], [COZY, 12]], 12)]
    assert [g["tag_pos"] for g in hm.week_games(games, TODAY, date(2026, 10, 12))] == [[], []]  # no tags picked
    top = hm.most_anticipated(games, [COZY])["paid"]["games"]
    assert [(g["appid"], g["tag_pos"], g["tag_count"]) for g in top] == [(1, [[COZY, 12]], 12), (2, [[COZY, 1]], 1)]


def test_unknown_mode_or_measure_is_an_error():
    with pytest.raises(ValueError):
        hm.matches([1], [1], "xor")
    with pytest.raises(ValueError):
        hm.history_panel([], measure="ratio")


def _trend_data(niche_exact, other_exact, niche_past, other_past):
    """Upcoming games with exact dates this week (shooters and cozy games) and past
    launches in the last 52 weeks."""
    games = [game("day", "2026-10-14")] * niche_exact + [game("day", "2026-10-14", tags=(COZY,))] * other_exact
    history = [past("2026-03-02", 10)] * niche_past + [past("2026-03-02", 10, tags=(COZY,))] * other_past
    return games, history


def test_niche_trend_compares_shares_of_upcoming_and_past():
    games, history = _trend_data(30, 20, 52, 156)  # 60% of upcoming, 25% of past
    t = hm.niche_trend(games, history, TODAY, [SHOOTER])["paid"]
    assert t["ratio"] == pytest.approx(0.6 / 0.25)
    assert (t["exact"], t["exact_all"], t["past"], t["past_all"]) == (30, 50, 52, 208)
    assert t["z"] > hm.TREND_Z and t["clear"] is True


def test_niche_trend_uses_exact_dates_only():
    games, history = _trend_data(30, 20, 52, 156)
    games += [game("month", "2026-10-01", "2026-10-31", tags=(COZY,))] * 40  # month dates: left out
    t = hm.niche_trend(games, history, TODAY, [SHOOTER])["paid"]
    assert t["ratio"] == pytest.approx(0.6 / 0.25) and t["exact_all"] == 50 and t["clear"] is True


def test_niche_trend_needs_size_a_clear_test_and_a_big_enough_ratio():
    # 9 exact dates: too few, however large the ratio
    assert hm.niche_trend(*_trend_data(9, 1, 52, 156), TODAY, [SHOOTER])["paid"]["clear"] is False
    # under one launch a week in the past year
    assert hm.niche_trend(*_trend_data(30, 20, 51, 153), TODAY, [SHOOTER])["paid"]["clear"] is False
    # a ratio of 1.15: under TREND_RATIO although the test is clear
    t = hm.niche_trend(*_trend_data(300, 700, 1300, 3700), TODAY, [SHOOTER])["paid"]
    assert t["ratio"] == pytest.approx(0.3 / 0.26) and t["z"] > hm.TREND_Z and t["clear"] is False
    # a ratio of 1.65 on few games: the test is not clear
    t = hm.niche_trend(*_trend_data(11, 29, 52, 260), TODAY, [SHOOTER])["paid"]
    assert t["ratio"] == pytest.approx(1.65) and abs(t["z"]) < hm.TREND_Z and t["clear"] is False


def test_niche_trend_flags_a_smaller_share_too():
    t = hm.niche_trend(*_trend_data(10, 190, 104, 104), TODAY, [SHOOTER])["paid"]
    assert t["ratio"] == pytest.approx(0.1) and t["z"] < -hm.TREND_Z and t["clear"] is True


def test_niche_trend_without_tags_or_history():
    games, history = _trend_data(30, 20, 52, 156)
    assert hm.niche_trend(games, history, TODAY) is None
    t = hm.niche_trend(games, [], TODAY, [SHOOTER])
    assert t["paid"]["ratio"] is None and t["paid"]["z"] is None and t["paid"]["clear"] is False
    assert t["free"] == {"ratio": None, "exact": 0, "exact_all": 0, "past": 0, "past_all": 0, "z": None,
                         "clear": False}


def test_trend_calibration_counts_real_launches_as_upcoming():
    from analysis import trend_calibration as tc
    week = lambda i, tags: past((date(2023, 1, 2) + timedelta(weeks=i)).isoformat(), 1, tags=tags)
    history = ([week(i - 52, (SHOOTER,)) for i in range(52)] + [week(i - 52, (COZY,)) for i in range(52)] * 3
               + [week(i, (SHOOTER,)) for i in range(13)] * 2 + [week(i, (COZY,)) for i in range(13)] * 2
               + [week(14, (COZY,))])
    assert tc.windows(history) == [date(2023, 1, 2)]  # one full window before the last, partial week
    cases = dict((c["exact"], c) for g, c in tc.tag_quarters(history) if g == "paid")
    assert cases[26] == {"exact": 26, "exact_all": 52, "past": 52, "past_all": 208}
    rates = tc.flag_rates(tc.tag_quarters(history), cuts=[1.4, 3])
    assert rates["eligible"]["paid"] == 2 and rates["cuts"][1.4]["paid"] == 1.0  # shooter 2.0, cozy 0.67
    assert rates["cuts"][3]["paid"] == 0 and tc.choose(rates, 0.05) == 3
