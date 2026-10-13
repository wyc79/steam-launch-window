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
- Week 0 counts exact dates for the whole week but spreads vague ones only from
  `today` on; games that launched earlier that week have left the list.
- Free games (Steam's flag or "Free to Play" in the top 10 tags) are counted
  apart from paid ones.

The browser's copies are in site/src/lib/ (heatmap.js, season.js), checked
against this module with the golden files that analysis/golden.py writes.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

WEEKS = 13  # Competition ahead: a quarter; announced dates say little beyond it
SPREAD = ("month", "quarter")
GROUPS = ("paid", "free")
CELL = ("exact", "spread", "year", "hype", "year_hype", "no_hype")
PANEL_TYPES = ("full", "early_access")
MIN_GROUP = 30
RELATIVE_WEEKS = 13  # the relative busy measure compares a week with this many weeks before it
TYPICAL_WEEKS = 52  # the heatmap's normalized view compares with launches over this many weeks
LATER_AFTER = 2  # year-only dates more than this many years ahead ("2099") are summed as "later"
TREND_MIN_EXACT = 10  # the niche trend needs this many niche games with exact dates
TREND_RATIO = 1.25  # and a share at least this many times the past one (or at most its inverse)
TREND_Z = 1.959964  # and a two-proportion z-test at p < 0.05, two-sided


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


MODES = ("and", "or")
MEASURES = ("relative", "raw")


def matches(tags, selection, mode: str = "and") -> bool:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, not {mode!r}")
    if not selection:
        return True
    have = set(tags)
    return all(t in have for t in selection) if mode == "and" else any(t in have for t in selection)


def speaks(langs, languages) -> bool:
    """True if the game supports at least one of the user's languages (none chosen: all games)."""
    return not languages or bool(set(langs) & set(languages))


def selected(games, selection=(), mode: str = "and", languages=()) -> list[dict]:
    return [g for g in games if matches(g["tags"], selection, mode) and speaks(g["langs"], languages)]


def group_of(game: dict) -> str:
    return "free" if game["free"] else "paid"


def _per_group(games) -> dict[str, int]:
    return {g: sum(group_of(x) == g for x in games) for g in GROUPS}


def match_count(games, history, selection=(), mode: str = "and", languages=()) -> dict:
    """The top bar's numbers per group (paid, free), so they agree with the heatmap
    for the group the user picked: [matched, total] for upcoming games and for past
    launches (full and Early Access, as in the panel)."""
    past = [h for h in history if h["launch_type"] in PANEL_TYPES]
    up, up_all = _per_group(selected(games, selection, mode, languages)), _per_group(games)
    hist, hist_all = _per_group(selected(past, selection, mode, languages)), _per_group(past)
    return {g: {"upcoming": [up[g], up_all[g]], "past": [hist[g], hist_all[g]]} for g in GROUPS}


def days_ahead(game: dict, today: date) -> tuple[date, date] | None:
    """The part of a vague date's range from `today` on, or None if it has run out."""
    start, end = max(date.fromisoformat(game["date"]), today), date.fromisoformat(game["date_end"])
    return (start, end) if start <= end else None


def _overlap(start: date, end: date, week: date) -> int:
    return max(0, (min(end, week + timedelta(days=6)) - max(start, week)).days + 1)


def heatmap(games, today: date, selection=(), mode: str = "and", languages=(), history=None) -> dict:
    """Per week and group: exact, spread, year (games), hype and year_hype
    (followers), no_hype (games with no follower number, exact and spread only).
    `sometime` sums the year-only games per year (years more than LATER_AFTER
    ahead together, as "later"). `typical` (with `history`) is each group's
    average week of real launches in the selection over the TYPICAL_WEEKS before
    `today`: the normalized view shows (exact + spread) / typical, "compared with
    a usual week of launches" (none when it is 0). Announced dates are not
    launches: near weeks run high (some will slip) and far weeks low (dates not
    set yet), and the page says so. `matched` and `total` are the
    match count for upcoming games, per group."""
    weeks = [week_start(today) + timedelta(weeks=i) for i in range(WEEKS)]
    grid = {g: [dict.fromkeys(CELL, 0.0) for _ in weeks] for g in GROUPS}
    sometime: dict[str, dict] = {}
    chosen = selected(games, selection, mode, languages)
    for game in chosen:
        group = group_of(game)
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
    typical = None
    if history is not None:
        since = (today - timedelta(weeks=TYPICAL_WEEKS)).isoformat()
        recent = [h for h in selected(history, selection, mode, languages)
                  if h["launch_type"] in PANEL_TYPES and since <= h["launch_date"] < today.isoformat()]
        typical = {g: sum((h["free"]) == (g == "free") for h in recent) / TYPICAL_WEEKS for g in GROUPS}
    return {"weeks": [w.isoformat() for w in weeks], **grid, "typical": typical,
            "sometime": dict(sorted(sometime.items())), "matched": _per_group(chosen), "total": _per_group(games)}


def heatmap_rows(games, today: date, selection=(), mode: str = "and", languages=(), history=None) -> list[dict]:
    """The heatmap's rows: each picked tag alone, then the combination in `mode`
    (no tags: one row of all games; one tag: just its row)."""
    out = [{"tags": [t], **heatmap(games, today, [t], mode, languages, history)} for t in selection]
    if len(selection) != 1:
        out.append({"tags": list(selection), **heatmap(games, today, selection, mode, languages, history)})
    return out


def trend_from(niche: dict, everyone: dict) -> dict:
    """The niche trend from two heatmaps (with `history`) for the same languages and
    today: the niche's and all games'. See `niche_trend`."""
    out = {}
    for g in GROUPS:
        up = sum(c["exact"] + c["spread"] for c in niche[g])
        up_all = sum(c["exact"] + c["spread"] for c in everyone[g])
        exact = sum(c["exact"] for c in niche[g])
        exact_all = sum(c["exact"] for c in everyone[g])
        past = round(niche["typical"][g] * TYPICAL_WEEKS)
        past_all = round(everyone["typical"][g] * TYPICAL_WEEKS)
        share_up = up / up_all if up_all else None
        share_past = past / past_all if past_all else None
        ratio = share_up / share_past if share_up is not None and share_past else None
        z = None
        if exact_all and past_all:
            pooled = (exact + past) / (exact_all + past_all)
            se = (pooled * (1 - pooled) * (1 / exact_all + 1 / past_all)) ** 0.5
            z = (exact / exact_all - past / past_all) / se if se else 0.0
        clear = (ratio is not None and z is not None and exact >= TREND_MIN_EXACT and past >= TYPICAL_WEEKS
                 and (ratio >= TREND_RATIO or ratio <= 1 / TREND_RATIO)
                 and abs(z) >= TREND_Z and (z > 0) == (ratio > 1))
        out[g] = {"ratio": ratio, "upcoming": up, "upcoming_all": up_all, "exact": exact, "exact_all": exact_all,
                  "past": past, "past_all": past_all, "z": z, "clear": clear}
    return out


def niche_trend(games, history, today: date, selection=(), mode: str = "and", languages=()) -> dict | None:
    """Per group, how the niche's share of upcoming games compares with its share of
    past launches: (niche / all games among the upcoming games with exact or spread
    dates in the heatmap's WEEKS, counted as `heatmap` counts them) divided by (niche
    / all games among the launches of the last TYPICAL_WEEKS, as in `typical`). All
    games means the same languages and group, any tags. 2.0 means the niche is twice
    as large a part of what is coming as of what launched.

    `clear` (the site shows the line only then): at least TREND_MIN_EXACT niche games
    with exact dates, at least one niche launch a week in the past year (the heatmap's
    own rule for comparing at all), a ratio of at least TREND_RATIO either way, and a
    two-proportion z-test on exact-date counts (exact niche / exact all against past
    niche / past all, pooled) at p < 0.05 two-sided (|z| >= TREND_Z) that points the
    same way. Exact dates only, since spread dates are fractions of games. Also
    returned: `upcoming`, `exact`, `past` and their `_all`, and `z`. No tags: None
    (the niche would be all games)."""
    if not selection:
        return None
    return trend_from(heatmap(games, today, selection, mode, languages, history),
                      heatmap(games, today, (), "and", languages, history))


def normalized(h: dict) -> dict | None:
    """The heatmap's default view, "1.0 = a usual week": exact, spread and year per
    week divided by the group's typical week. None without `typical`, and a group
    whose typical week is 0 gets None."""
    if h["typical"] is None:
        return None
    return {g: [{k: c[k] / h["typical"][g] for k in ("exact", "spread", "year")} for c in h[g]]
            if h["typical"][g] else None for g in GROUPS}


def week_games(games, today: date, week: date, selection=(), mode: str = "and", languages=(),
               year: bool = False) -> list[dict]:
    """The games behind one heatmap week (`week` is its Monday), as the heatmap counts
    them: day dates in the week (layer "exact", share 1), month and quarter dates by the
    share they add ("spread"), and year-only dates the same way when `year` is set.
    Games whose top 10 tags match the selection come first, then the most followers
    (none last), then by name, then appid. `hype_src` says where `followers` comes from
    ("f" a count, "r" an estimate from wishlist rank). `moved` is [kind, old date
    text, days since the change]."""
    out = []
    for game in selected(games, selection, mode, languages):
        precision = game["precision"]
        if precision == "day":
            if week_start(date.fromisoformat(game["date"])) != week:
                continue
            layer, share = "exact", 1.0
        elif precision in SPREAD or (year and precision == "year"):
            span = days_ahead(game, today)
            days = _overlap(*span, week) if span else 0
            if not days:
                continue
            layer = "year" if precision == "year" else "spread"
            share = 1 / ((span[1] - span[0]).days + 1) * days  # as in heatmap, to the last digit
        else:
            continue
        moved = game.get("moved")
        out.append({"appid": game["appid"], "name": game["name"], "free": game["free"], "layer": layer,
                    "share": share, "followers": game.get("followers"), "hype_src": game.get("hype_src"),
                    "top10": matches(game["tags"][:10], selection, mode),
                    "moved": [moved[0], moved[1], (today - date.fromisoformat(moved[2])).days] if moved else None})
    return sorted(out, key=lambda g: (not g["top10"], g["followers"] is None, -(g["followers"] or 0),
                                      g["name"], g["appid"]))


def percentile(values: list[float], q: float) -> float:
    """Linear interpolation between the closest ranks (numpy's default), q in 0..1."""
    if not values:
        raise ValueError("percentile of no values")
    v = sorted(values)
    pos = (len(v) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def history_panel(history, selection=(), mode: str = "and", languages=(), min_group: int = MIN_GROUP,
                  measure: str = "relative") -> dict:
    """Past launches in the selection, per group (paid, free), split into quiet,
    normal and busy launch weeks by tercile of "busy". Each part gives games, its
    busy range, and median, 75th and 90th percentile of 30-day reviews. A part
    with fewer than `min_group` games is hidden, and then the whole group is
    (`shown` false).

    Busy, for launches of the same group in the selection (weeks Monday to Sunday):
    - measure "raw" (the site's "raw counts" toggle, off by default): how many
      other launches that week;
    - measure "relative" (the default): the other launches that week divided by
      the average week in the RELATIVE_WEEKS before it, rounded to 2 decimals. An
      average under 1 counts as 1, so a niche with less than one launch a week is
      compared with one launch, not with a fraction (a lone launch after a quiet
      quarter would otherwise read as very busy). Steam grows every year, so raw counts make "busy" partly mean
      "recent"; this compares a week with what was usual just before it, which is
      what a developer could know when picking the date. Launches in the data's
      first RELATIVE_WEEKS weeks have no such baseline and are left out. In a
      fast-growing niche the past lags, so its weeks read a little high."""
    if measure not in MEASURES:
        raise ValueError(f"measure must be one of {MEASURES}, not {measure!r}")
    chosen = [h for h in selected(history, selection, mode, languages) if h["launch_type"] in PANEL_TYPES]
    week_of = {id(h): week_start(date.fromisoformat(h["launch_date"])) for h in chosen}
    per_week = Counter((group_of(h), week_of[id(h)]) for h in chosen)
    span = [week_start(date.fromisoformat(h["launch_date"])) for h in history]
    baseline_from = min(span) + timedelta(weeks=RELATIVE_WEEKS) if span else None

    def busy(group, week):
        if measure == "raw":
            return per_week[group, week] - 1
        usual = sum(per_week[group, week - timedelta(weeks=k)] for k in range(1, RELATIVE_WEEKS + 1)) / RELATIVE_WEEKS
        return round((per_week[group, week] - 1) / max(usual, 1), 2)

    out = {"measure": measure}
    for group in GROUPS:
        sample = [(busy(group, week_of[id(h)]), h["reviews_30d"])
                  for h in chosen if group_of(h) == group and h["reviews_30d"] is not None
                  and (measure == "raw" or week_of[id(h)] >= baseline_from)]
        out[group] = _terciles(sample, min_group)
    out["matched"] = _per_group(chosen)
    out["total"] = _per_group([h for h in history if h["launch_type"] in PANEL_TYPES])
    return out


def cut_points(busy: list[float]) -> tuple[float, float] | None:
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


def _terciles(sample: list[tuple[float, int]], min_group: int) -> dict:
    parts = defaultdict(list)
    cuts = cut_points([b for b, _ in sample])
    if cuts:
        for b, reviews in sample:
            parts["quiet" if b <= cuts[0] else "normal" if b <= cuts[1] else "busy"].append((b, reviews))
    result = {"games": len(sample), "shown": True, "parts": {}}
    for name in ("quiet", "normal", "busy"):
        rows = parts[name]
        if len(rows) < max(min_group, 1):
            result["shown"] = False
            result["parts"][name] = {"games": len(rows)}
            continue
        reviews = [r for _, r in rows]
        result["parts"][name] = {
            "games": len(rows), "busy_min": min(b for b, _ in rows), "busy_max": max(b for b, _ in rows),
            "median": percentile(reviews, 0.5), "p75": percentile(reviews, 0.75), "p90": percentile(reviews, 0.9),
        }
    return result
