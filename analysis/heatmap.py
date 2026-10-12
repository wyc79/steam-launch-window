"""The site's numbers, defined once (docs/phase2-plan.md sections 1, 2 and 4).

The website computes these in the browser from upcoming.json and history.json.
This module is the reference: its tests are the spec the browser code is
checked against. Games are dicts with the column names of those files.

- A game matches a tag selection if the tags are anywhere in its tags: all of
  them (mode "and") or any of them (mode "or"). An empty selection matches all.
- Weeks run Monday to Sunday (dates are Pacific, like the store), starting with
  the week of `today` (the newest snapshot's date).
- Day dates count 1 in their week ("exact"). Month and quarter dates are spread
  evenly over the days of their range from `today` on ("spread"). Year-only
  dates are spread the same way into a separate layer ("year") and also summed
  per year ("sometime"); they never add into exact or spread.
- Free games (Steam's flag or "Free to Play" in the top 10 tags) are counted
  apart from paid ones.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

WEEKS = 26
SPREAD = ("month", "quarter")
GROUPS = ("paid", "free")
CELL = ("exact", "spread", "year", "hype", "year_hype", "no_hype")
PANEL_TYPES = ("full", "early_access")
MIN_GROUP = 30
LATER_AFTER = 2  # year-only dates more than this many years ahead ("2099") are summed as "later"


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def matches(tags, selection, mode: str = "and") -> bool:
    if not selection:
        return True
    have = set(tags)
    return all(t in have for t in selection) if mode == "and" else any(t in have for t in selection)


def speaks(langs, languages) -> bool:
    """True if the game supports at least one of the user's languages (none chosen: all games)."""
    return not languages or bool(set(langs) & set(languages))


def selected(games, selection=(), mode: str = "and", languages=()) -> list[dict]:
    return [g for g in games if matches(g["tags"], selection, mode) and speaks(g["langs"], languages)]


def days_ahead(game: dict, today: date) -> tuple[date, date] | None:
    """The part of a vague date's range from `today` on, or None if it has run out."""
    start, end = max(date.fromisoformat(game["date"]), today), date.fromisoformat(game["date_end"])
    return (start, end) if start <= end else None


def _overlap(start: date, end: date, week: date) -> int:
    return max(0, (min(end, week + timedelta(days=6)) - max(start, week)).days + 1)


def heatmap(games, today: date, selection=(), mode: str = "and", languages=()) -> dict:
    """Per week and group: exact, spread, year (games), hype and year_hype
    (followers), no_hype (games with no follower number, exact and spread only).
    `sometime` sums the year-only games per year (years more than LATER_AFTER
    ahead together, as "later"). `matched` and `total` are the
    match count for upcoming games."""
    weeks = [week_start(today) + timedelta(weeks=i) for i in range(WEEKS)]
    grid = {g: [dict.fromkeys(CELL, 0.0) for _ in weeks] for g in GROUPS}
    sometime: dict[str, dict] = {}
    chosen = selected(games, selection, mode, languages)
    for game in chosen:
        group = "free" if game["free"] else "paid"
        followers = game.get("followers")
        precision = game["precision"]
        if precision == "day":
            i = (week_start(date.fromisoformat(game["date"])) - weeks[0]).days // 7
            if 0 <= i < WEEKS:
                cell = grid[group][i]
                cell["exact"] += 1
                cell["hype"] += followers or 0
                cell["no_hype"] += followers is None
            continue
        if precision not in (*SPREAD, "year"):
            continue  # no date (ranked only): not on the heatmap
        span = days_ahead(game, today)
        if span is None:
            continue
        per_day = 1 / ((span[1] - span[0]).days + 1)
        layer, hype = ("year", "year_hype") if precision == "year" else ("spread", "hype")
        for i, week in enumerate(weeks):
            share = per_day * _overlap(*span, week)
            if share:
                cell = grid[group][i]
                cell[layer] += share
                cell[hype] += share * (followers or 0)
                if precision != "year":
                    cell["no_hype"] += share * (followers is None)
        if precision == "year":
            key = game["date"][:4] if int(game["date"][:4]) <= today.year + LATER_AFTER else "later"
            year = sometime.setdefault(key, {g: {"games": 0, "hype": 0, "no_hype": 0} for g in GROUPS})
            year[group]["games"] += 1
            year[group]["hype"] += followers or 0
            year[group]["no_hype"] += followers is None
    return {"weeks": [w.isoformat() for w in weeks], **grid, "sometime": dict(sorted(sometime.items())),
            "matched": len(chosen), "total": len(games)}


def percentile(values: list[float], q: float) -> float:
    """Linear interpolation between the closest ranks (numpy's default), q in 0..1."""
    v = sorted(values)
    pos = (len(v) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def history_panel(history, selection=(), mode: str = "and", languages=(), min_group: int = MIN_GROUP) -> dict:
    """Past launches in the selection, per group (paid, free), split into quiet,
    normal and busy launch weeks by tercile of "busy": how many other launches of
    the same group in the selection launched that week (Monday to Sunday). Each
    part gives games, its busy range, and median, 75th and 90th percentile of
    30-day reviews. A part with fewer than `min_group` games is hidden, and then
    the whole group is (`shown` false)."""
    chosen = [h for h in selected(history, selection, mode, languages) if h["launch_type"] in PANEL_TYPES]
    per_week = Counter(("free" if h["free"] else "paid", week_start(date.fromisoformat(h["launch_date"])))
                       for h in chosen)
    out = {}
    for group in GROUPS:
        sample = [(per_week[group, week_start(date.fromisoformat(h["launch_date"]))] - 1, h["reviews_30d"])
                  for h in chosen if ("free" if h["free"] else "paid") == group and h["reviews_30d"] is not None]
        out[group] = _terciles(sample, min_group)
    out["matched"] = len(chosen)
    out["total"] = sum(h["launch_type"] in PANEL_TYPES for h in history)
    return out


def cut_points(busy: list[int]) -> tuple[int, int] | None:
    """Where quiet ends and normal ends: games with the same busy count stay in one
    part, and each cut is the value whose running total is closest to a third
    (then two thirds) of the games; ties go to the lower value. With many equal
    counts a part can end up empty, which hides the panel."""
    if not busy:
        return None
    counts = sorted(Counter(busy).items())
    running, total = [], 0
    for value, n in counts:
        total += n
        running.append((value, total))
    c1 = min(running, key=lambda vt: (abs(vt[1] - total / 3), vt[0]))[0]
    later = [vt for vt in running if vt[0] > c1]
    c2 = min(later, key=lambda vt: (abs(vt[1] - 2 * total / 3), vt[0]))[0] if later else c1
    return c1, c2


def _terciles(sample: list[tuple[int, int]], min_group: int) -> dict:
    parts = defaultdict(list)
    cuts = cut_points([b for b, _ in sample])
    if cuts:
        for b, reviews in sample:
            parts["quiet" if b <= cuts[0] else "normal" if b <= cuts[1] else "busy"].append((b, reviews))
    result = {"games": len(sample), "shown": True, "parts": {}}
    for name in ("quiet", "normal", "busy"):
        rows = parts[name]
        if len(rows) < min_group:
            result["shown"] = False
            result["parts"][name] = {"games": len(rows)}
            continue
        reviews = [r for _, r in rows]
        result["parts"][name] = {
            "games": len(rows), "busy_min": min(b for b, _ in rows), "busy_max": max(b for b, _ in rows),
            "median": percentile(reviews, 0.5), "p75": percentile(reviews, 0.75), "p90": percentile(reviews, 0.9),
        }
    return result
