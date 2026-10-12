"""What history says about a week of the year (docs/phase2-plan.md section 2).

Announced dates thin out a few weeks ahead, so for any week the site also shows
how busy that time of year usually was, from past launches only:

- Each past week gets a ratio: its launches in the selection divided by the
  average week in the RELATIVE_WEEKS before it (the panel's normalized busy).
- **Calendar:** the ratios of the same time of year in past years: the week
  that holds the same calendar date as the target week's Thursday (so the week
  of Dec 28 to Jan 3 is matched with past New Year weeks, not Christmas weeks).
- **Events:** recurring events (Next Fests, seasonal sales, holidays) move
  between weeks from year to year. For each one within EVENT_WINDOW weeks of
  the target week, the ratios at the same distance from that event in past
  years (for example 2 weeks after Next Fest February).
- **Expected:** the estimates combined, each weighted by how steady it was
  across years (years / SD squared), so a steady pattern counts more than a
  noisy one. `sd` is the typical year-to-year spread of the parts. Events that
  cover the same past weeks (Winter Sale and Christmas) are weighted as if they
  were separate, so such weeks count more than once; the backtest shows the
  combination still tracks the event estimates.

Only weeks before `before` are used, so a backtest can hide the years it
predicts (see `backtest`).
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta

from .heatmap import PANEL_TYPES, RELATIVE_WEEKS, selected, week_start

EVENT_TYPES = ("next_fest", "seasonal_sale", "regional_holiday")
EVENT_WINDOW = 4   # weeks before and after an event that its pattern covers
MIN_YEARS = 3      # an estimate needs this many past years
MIN_SD = 0.05      # floor, so a near-constant estimate cannot take all the weight
_YEAR = re.compile(r"\s*\b(19|20)\d{2}\b")


def weekly_ratios(history, selection=(), mode: str = "and", languages=(), group: str = "paid") -> dict[date, float]:
    """Each week's launches divided by the average week in the RELATIVE_WEEKS before it,
    for weeks with a full baseline, through the last complete week of the data."""
    chosen = [h for h in selected(history, selection, mode, languages)
              if h["launch_type"] in PANEL_TYPES and h["free"] == (group == "free")]
    span = [week_start(date.fromisoformat(h["launch_date"])) for h in history]
    if not span:
        return {}
    counts = Counter(week_start(date.fromisoformat(h["launch_date"])) for h in chosen)
    newest = max(date.fromisoformat(h["launch_date"]) for h in history)
    last = week_start(newest) - timedelta(weeks=0 if newest.weekday() == 6 else 1)  # the newest week may be partial
    out, week = {}, min(span) + timedelta(weeks=RELATIVE_WEEKS)
    while week <= last:
        usual = sum(counts[week - timedelta(weeks=k)] for k in range(1, RELATIVE_WEEKS + 1)) / RELATIVE_WEEKS
        out[week] = counts[week] / (usual or 1)
        week += timedelta(weeks=1)
    return out


def event_series(events) -> dict[str, list[date]]:
    """Start weeks of each recurring event, by name without the year."""
    series = defaultdict(list)
    for e in events:
        if e["type"] in EVENT_TYPES:
            start = e["start"] if isinstance(e["start"], date) else date.fromisoformat(e["start"])
            series[_YEAR.sub("", e["name"]).strip()].append(week_start(start))
    return {name: sorted(weeks) for name, weeks in series.items()}


def _part(name, values) -> dict | None:
    if len(values) < MIN_YEARS:
        return None
    return {"name": name, "mean": statistics.mean(values), "sd": statistics.stdev(values), "years": len(values)}


def _same_time(week: date, year: int) -> date:
    """The week in `year` that holds the calendar date of `week`'s Thursday."""
    mid = week + timedelta(days=3)
    return week_start(date(year, mid.month, min(mid.day, 28) if mid.month == 2 else mid.day))


def estimate(week: date, ratios: dict[date, float], series: dict[str, list[date]], before: date) -> dict:
    """Calendar and event estimates for `week`, and their weighted combination."""
    past = {w: r for w, r in ratios.items() if w < before}
    years = range(min(past).year, before.year + 1) if past else ()
    calendar = _part("calendar", [past[w] for w in {_same_time(week, y) for y in years} if w in past and w != week])
    events = []
    for name, starts in series.items():
        near = min(starts, key=lambda s: abs((week - s).days))
        offset = (week - near).days // 7
        if abs(offset) > EVENT_WINDOW:
            continue
        values = [past[s + timedelta(weeks=offset)] for s in starts
                  if s != near and s + timedelta(weeks=offset) in past]
        part = _part(name, values)
        if part:
            events.append(part | {"offset": offset})
    parts = [p for p in [calendar, *events] if p]
    if not parts:
        return {"calendar": None, "events": [], "expected": None, "sd": None}
    weights = [p["years"] / max(p["sd"], MIN_SD) ** 2 for p in parts]
    total = sum(weights)
    return {"calendar": calendar, "events": events,
            "expected": sum(w * p["mean"] for w, p in zip(weights, parts)) / total,
            "sd": (sum(w * p["sd"] ** 2 for w, p in zip(weights, parts)) / total) ** 0.5}


def backtest(history, events, years, selection=(), mode: str = "and", languages=(), group: str = "paid",
             pattern=None) -> dict:
    """Predict every week of each year in `years` from earlier years only, and give the
    mean absolute error of: no pattern (1.0), calendar only, events only (calendar
    where no event is near), and the combination. The actual ratios come from
    `selection`; the estimates from `pattern` (a (selection, mode) pair), or from
    `selection` itself when None. pattern=((), "and") scores the all-games pattern."""
    actuals = weekly_ratios(history, selection, mode, languages, group)
    ratios = actuals if pattern is None else weekly_ratios(history, pattern[0], pattern[1], languages, group)
    series = event_series(events)
    errors = defaultdict(list)
    for week, actual in actuals.items():
        if week.year not in years:
            continue
        est = estimate(week, ratios, series, before=date(week.year, 1, 1))
        if est["expected"] is None:
            continue
        cal = est["calendar"]["mean"] if est["calendar"] else 1.0
        if est["events"]:
            w = [p["years"] / max(p["sd"], MIN_SD) ** 2 for p in est["events"]]
            ev = sum(x * p["mean"] for x, p in zip(w, est["events"])) / sum(w)
        else:
            ev = cal
        for name, guess in (("flat", 1.0), ("calendar", cal), ("events", ev), ("combined", est["expected"])):
            errors[name].append(abs(guess - actual))
    return {name: round(statistics.mean(v), 3) for name, v in errors.items()} | {"weeks": len(errors["flat"])}


def outlook(history, events, today: date, weeks: int = 26, languages=()) -> dict:
    """The site's "typical for this time of year" numbers: for each of the `weeks`
    weeks from today's, per group, the expected ratio and spread from the pattern
    of all games in the user's languages, not just the selected tags. In a backtest
    on 2025 and 2026 (`backtest(..., pattern=((), "and"))`), the all-games pattern
    predicted niches about as well as their own or better; a niche's own pattern is
    noisy, and worse than none for small niches."""
    series = event_series(events)
    first = week_start(today)
    out = {"weeks": [(first + timedelta(weeks=i)).isoformat() for i in range(weeks)]}
    for group in ("paid", "free"):
        ratios = weekly_ratios(history, (), "and", languages, group)
        out[group] = []
        for i in range(weeks):
            est = estimate(first + timedelta(weeks=i), ratios, series, before=first)
            out[group].append({"expected": est["expected"], "sd": est["sd"],
                               "parts": [p["name"] if "offset" not in p else f"{p['name']} {p['offset']:+d}"
                                         for p in [est["calendar"], *est["events"]] if p]})
    return out
