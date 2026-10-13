"""Section 04 Trends: the selection's past launches per quarter (docs/phase3-plan.md, Page).

The reference for site/src/lib/trends.js, checked with the golden files that
analysis/golden.py writes. Launches are the history panel's (full and Early
Access, not `ea_exit`), with or without a 30-day review count yet, as in the top
bar's past launch count.

- Quarters run from TREND_FROM (2022 Q1, where the data starts) to the quarter
  that holds `today`. That last quarter is `partial`: it counts launches before
  `today` only, so `days` says how many of its days are in.
- The partial quarter and the RECENT_FULL full quarters before it are `recent`:
  they may still change. The history was listed in October 2026, so older
  quarters hold only games still on Steam then (Steam removes many games over
  time) and counts rise toward today; recent games also still carry the tags
  their developers set, before player votes reshape them.
- Per group (paid, free): `niche` the selection's launches, `all` every launch
  of the group in the picked languages (any tags), `share` niche / all (None
  when no launch), and running totals of both from 2022 Q1 on.
- Nothing ahead: announced dates are too incomplete to extend the line.
"""

from __future__ import annotations

from datetime import date, timedelta

from .heatmap import GROUPS, PANEL_TYPES, group_of, matches, speaks

TREND_FROM = date(2022, 1, 1)  # the history data starts here, on a quarter's first day
RECENT_FULL = 2  # full quarters before the partial one that are marked recent


def quarter_start(d: date) -> date:
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def next_quarter(d: date) -> date:
    """The first day of the quarter after the one that starts on `d`."""
    return date(d.year + 1, 1, 1) if d.month == 10 else date(d.year, d.month + 3, 1)


def quarters(today: date) -> list[dict]:
    """2022 Q1 to the quarter that holds `today`: label parts, first and last day,
    its length, how many of its days are counted, whether it is the partial one, and
    whether it is recent (the partial one and the RECENT_FULL before it)."""
    out, start, current = [], TREND_FROM, quarter_start(today)
    while start <= current:
        end = next_quarter(start) - timedelta(days=1)
        partial = start == current
        out.append({"year": start.year, "q": (start.month - 1) // 3 + 1, "start": start.isoformat(),
                    "end": end.isoformat(), "length": (end - start).days + 1,
                    "days": (today - start).days if partial else (end - start).days + 1, "partial": partial})
        start = next_quarter(start)
    for i, q in enumerate(out):
        q["recent"] = i >= len(out) - 1 - RECENT_FULL
    return out


def quarterly(history, today: date, selection=(), mode: str = "and", languages=()) -> dict:
    """Past launches per quarter for the selection and for all games (same group and
    languages), from 2022 Q1 to the quarter of `today` (partial: launches before
    `today`). Returns {"quarters": quarters(today), "paid": [...], "free": [...]},
    one entry per quarter: niche, all, share (None without launches), cumulative
    and cumulative_all (running totals from 2022 Q1)."""
    qs = quarters(today)
    index = {(q["year"], q["q"]): i for i, q in enumerate(qs)}
    niche = {g: [0] * len(qs) for g in GROUPS}
    every = {g: [0] * len(qs) for g in GROUPS}
    since, until = TREND_FROM.isoformat(), today.isoformat()
    for h in history:
        day = h["launch_date"]
        if h["launch_type"] not in PANEL_TYPES or not since <= day < until or not speaks(h["langs"], languages):
            continue
        i = index[int(day[:4]), (int(day[5:7]) - 1) // 3 + 1]
        group = group_of(h)
        every[group][i] += 1
        niche[group][i] += matches(h["tags"], selection, mode)
    out = {"quarters": qs}
    for g in GROUPS:
        rows, run, run_all = [], 0, 0
        for n, a in zip(niche[g], every[g]):
            run, run_all = run + n, run_all + a
            rows.append({"niche": n, "all": a, "share": n / a if a else None, "cumulative": run,
                         "cumulative_all": run_all})
        out[g] = rows
    return out
