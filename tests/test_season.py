from datetime import date, timedelta

import pytest

from analysis import season
from analysis.heatmap import week_start

SHOOTER = 1774
START = date(2022, 1, 3)  # a Monday


def launches(per_week: dict[date, int], free=False, tags=(SHOOTER,)):
    rows = []
    for week, n in per_week.items():
        rows += [{"launch_date": week.isoformat(), "launch_type": "full", "tags": list(tags),
                  "langs": ["english"], "free": free, "reviews_30d": 1}] * n
    return rows


def steady(weeks: int, n: int = 10, start: date = START) -> dict[date, int]:
    return {start + timedelta(weeks=i): n for i in range(weeks)}


def test_weekly_ratios_compare_with_the_13_weeks_before():
    counts = steady(30)
    counts[START + timedelta(weeks=20)] = 30
    ratios = season.weekly_ratios(launches(counts))
    assert min(ratios) == START + timedelta(weeks=13)  # first week with a full baseline
    assert ratios[START + timedelta(weeks=20)] == 3.0
    assert ratios[START + timedelta(weeks=21)] == pytest.approx(10 / (150 / 13))


def test_event_series_group_years_and_skip_other_types():
    events = [{"name": "Steam Next Fest February 2025", "type": "next_fest", "start": date(2025, 2, 24)},
              {"name": "Steam Next Fest February 2026", "type": "next_fest", "start": "2026-02-23"},
              {"name": "Some Game", "type": "major_release", "start": date(2026, 3, 1)}]
    assert season.event_series(events) == {"Steam Next Fest February": [date(2025, 2, 24), date(2026, 2, 23)]}


def yearly(pattern, years=range(2022, 2027)):
    """Ratios with `pattern(week)` in every year."""
    return {w: pattern(w) for y in years for w in (week_start(date(y, 1, 4)) + timedelta(weeks=i) for i in range(52))}


def holds(week: date, month: int, day: int) -> bool:
    return week <= date(week.year, month, day) <= week + timedelta(days=6)


def test_calendar_estimate_uses_the_same_time_of_year_in_past_years_only():
    ratios = yearly(lambda w: 0.5 if holds(w, 12, 24) else 1.0)
    target = week_start(date(2026, 12, 24))
    est = season.estimate(target, ratios, {}, before=date(2026, 1, 1))
    assert est["calendar"]["years"] == 4 and est["calendar"]["mean"] == 0.5  # 2022 to 2025
    assert est["expected"] == 0.5 and est["events"] == []
    assert season.estimate(target, ratios, {}, before=date(2024, 1, 1))["expected"] is None  # 2 years: too few


def test_the_week_of_new_year_is_matched_with_past_new_year_weeks():
    # 2026-12-28 to 2027-01-03 is ISO week 53; it must not be compared with Christmas weeks
    # (a week can hold both: in 2023 Dec 25 was a Monday; it counts as the New Year week)
    ratios = yearly(lambda w: 0.7 if holds(w, 12, 31) else 0.4 if holds(w, 12, 25) else 1.0, years=range(2021, 2027))
    est = season.estimate(date(2026, 12, 28), ratios, {}, before=date(2026, 12, 1))
    assert est["calendar"]["mean"] == pytest.approx(0.7)


def test_the_predicted_year_never_leaks_into_its_estimate():
    # 2026 is different on purpose; predicting it from earlier years must not see it
    ratios = yearly(lambda w: 3.0 if w.year == 2026 else 1.0)
    fest = [week_start(date(y, 2, 20)) for y in range(2022, 2027)]
    est = season.estimate(week_start(date(2026, 2, 20)), ratios, {"Fest": fest}, before=date(2026, 1, 1))
    assert est["calendar"]["mean"] == 1.0 and est["events"][0]["mean"] == 1.0 and est["expected"] == 1.0


def test_weekly_ratios_stop_at_the_last_complete_week():
    counts = steady(30)
    last = START + timedelta(weeks=29)
    history = launches(counts) + launches({last + timedelta(days=7): 1})  # a Monday: its week has just begun
    ratios = season.weekly_ratios(history)
    assert max(ratios) == last


def test_event_estimate_follows_the_event_when_it_moves():
    fest = [week_start(date(y, 2, d)) for y, d in ((2022, 21), (2023, 6), (2024, 5), (2025, 24), (2026, 23))]
    ratios = yearly(lambda w: 2.0 if any(w == f + timedelta(weeks=2) for f in fest) else 1.0)
    series = {"Steam Next Fest February": fest}
    est = season.estimate(fest[-1] + timedelta(weeks=2), ratios, series, before=date(2026, 1, 1))
    (part,) = est["events"]
    assert (part["name"], part["offset"], part["mean"], part["years"]) == ("Steam Next Fest February", 2, 2.0, 4)
    assert est["calendar"]["mean"] < 2.0  # the calendar blurs a moving peak
    assert est["calendar"]["mean"] < est["expected"] <= 2.0
    far = season.estimate(fest[-1] + timedelta(weeks=10), ratios, series, before=date(2026, 1, 1))
    assert far["events"] == []  # more than 4 weeks from the event
    # the target's own occurrence is not one of the past years, even when it is in the past
    own = season.estimate(fest[2] + timedelta(weeks=2), ratios, series, before=date(2027, 1, 1))
    assert own["events"][0]["years"] == 4


def test_steadier_estimates_get_more_weight():
    parts_week = week_start(date(2026, 3, 9))
    fest = [week_start(date(y, 3, 2)) for y in range(2022, 2027)]
    noisy = {2022: 0.6, 2023: 1.4, 2024: 0.6, 2025: 1.4}
    ratios = yearly(lambda w: 2.0 if w - timedelta(weeks=1) in fest
                    else noisy.get(w.year, 1.0) if w.isocalendar()[1] == parts_week.isocalendar()[1] else 1.0)
    est = season.estimate(parts_week, ratios, {"Fest": fest}, before=date(2026, 1, 1))
    assert est["events"][0]["sd"] == 0  # the fest pattern is exact
    assert est["expected"] > 1.9


def test_backtest_and_outlook_run_end_to_end():
    counts = steady(52 * 5)
    for y in range(2022, 2027):
        counts[week_start(date(y, 12, 24))] = 3  # quiet Christmas week every year
    history = launches(counts) + launches(steady(52 * 5, 2), free=True)
    events = [{"name": f"Christmas to New Year {y}", "type": "regional_holiday", "start": date(y, 12, 24)}
              for y in range(2022, 2027)]
    result = season.backtest(history, events, {2025, 2026})
    assert result["weeks"] > 50 and result["combined"] < result["flat"]
    same = season.backtest(history, events, {2025, 2026}, pattern=((), "and"))
    assert same == result  # with no tags the pattern is the selection itself
    out = season.outlook(history, events, date(2026, 12, 1), weeks=6)
    christmas = out["weeks"].index(week_start(date(2026, 12, 24)).isoformat())
    assert out["paid"][christmas]["expected"] < 0.5
    assert "Christmas to New Year +0" in out["paid"][christmas]["parts"]
    assert out["free"][0]["expected"] == pytest.approx(1.0)
