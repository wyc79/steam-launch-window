"""Golden test cases for the browser's copies of the reference numbers (docs/phase3-plan.md, Data).

    python -m analysis.golden

Runs analysis.heatmap, analysis.season, analysis.trends and site_data.table_rows on small
hand-built inputs and writes the inputs with the expected outputs to
site/test/golden/*.json. site/test/golden.test.js requires the JavaScript in
site/src/lib/ to give the same results, and tests/test_golden.py fails when the
committed files are out of date, so the two sides cannot drift.

Each file is {"inputs": {...}, "cases": [{"name", "fn", "args", "expected"}]};
an argument written "$name" stands for inputs[name]. Dates are "YYYY-MM-DD".
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import heatmap as hm
from . import season
from . import trends
from .site_data import table_rows

OUT = Path(__file__).resolve().parent.parent / "site" / "test" / "golden"
SHOOTER, ROGUELIKE, COZY, PIXEL, F2P = 1774, 1716, 97376, 3964, 113
FILLER = [492, 19, 21, 4182, 597, 1742, 3871, 1625, 4166, 1664, 7208]  # pushes a tag below the top 10


def _d(iso: str | None) -> date | None:
    return date.fromisoformat(iso) if iso else None


# fn name: how to call the Python reference with the case's (resolved) arguments
CALLS = {
    "matches": lambda a: hm.matches(a["tags"], a["selection"], a.get("mode", "and")),
    "tag_pos": lambda a: hm.tag_pos(a["tags"], a["selection"]),
    "speaks": lambda a: hm.speaks(a["langs"], a["languages"]),
    "heatmap": lambda a: hm.heatmap(a["games"], _d(a["today"]), a.get("selection", ()), a.get("mode", "and"),
                                    a.get("languages", ()), a.get("history")),
    "heatmap_rows": lambda a: hm.heatmap_rows(a["games"], _d(a["today"]), a.get("selection", ()),
                                              a.get("mode", "and"), a.get("languages", ()), a.get("history")),
    "match_count": lambda a: hm.match_count(a["games"], a["history"], a.get("selection", ()), a.get("mode", "and"),
                                            a.get("languages", ())),
    "normalized": lambda a: hm.normalized(CALLS["heatmap"](a)),
    "niche_trend": lambda a: hm.niche_trend(a["games"], a["history"], _d(a["today"]), a.get("selection", ()),
                                            a.get("mode", "and"), a.get("languages", ())),
    "most_anticipated": lambda a: hm.most_anticipated(a["games"], a.get("selection", ()), a.get("mode", "and"),
                                                      a.get("languages", ()), a.get("limit", hm.TOP_RANKED)),
    "week_games": lambda a: hm.week_games(a["games"], _d(a["today"]), _d(a["week"]), a.get("selection", ()),
                                          a.get("mode", "and"), a.get("languages", ()), a.get("year", False)),
    "percentile": lambda a: hm.percentile(a["values"], a["q"]),
    "round2": lambda a: round(a["x"], 2),  # the relative busy measure's rounding
    "cut_points": lambda a: hm.cut_points(a["busy"]),
    "history_panel": lambda a: hm.history_panel(a["history"], a.get("selection", ()), a.get("mode", "and"),
                                                a.get("languages", ()), a.get("min_group", hm.MIN_GROUP),
                                                a.get("measure", "relative")),
    "weekly_ratios": lambda a: season.weekly_ratios(a["history"], a.get("selection", ()), a.get("mode", "and"),
                                                    a.get("languages", ()), a.get("group", "paid")),
    "event_series": lambda a: season.event_series(a["events"]),
    "estimate": lambda a: season.estimate(_d(a["week"]), {_d(w): r for w, r in a["ratios"].items()},
                                          {n: [_d(w) for w in ws] for n, ws in a["series"].items()},
                                          _d(a["before"])),
    "outlook": lambda a: season.outlook(a["history"], a["events"], _d(a["today"]), a.get("weeks", 26),
                                        a.get("languages", ())),
    "table_rows": lambda a: table_rows(a["table"], a.get("meta")),
    "quarters": lambda a: trends.quarters(_d(a["today"])),
    "quarterly": lambda a: trends.quarterly(a["history"], _d(a["today"]), a.get("selection", ()), a.get("mode", "and"),
                                            a.get("languages", ())),
}


def _plain(x):
    """Dates to strings and tuples to lists, as JSON and the JavaScript side have them."""
    if isinstance(x, date):
        return x.isoformat()
    if isinstance(x, dict):
        return {_plain(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    return x


class Cases:
    def __init__(self, **inputs):
        self.inputs = inputs
        self.cases = []

    def add(self, name: str, fn: str, **args):
        resolved = {k: self.inputs[v[1:]] if isinstance(v, str) and v.startswith("$") else v for k, v in args.items()}
        self.cases.append({"name": name, "fn": fn, "args": args, "expected": _plain(CALLS[fn](resolved))})

    def obj(self) -> dict:
        return {"inputs": self.inputs, "cases": self.cases}


def game(appid, name, precision, start=None, end=None, tags=(SHOOTER,), langs=("english",), free=False,
         followers=None, moved=None, hype_src=None):
    return {"appid": appid, "name": name, "precision": precision, "date": start,
            "date_end": end or start, "tags": list(tags), "langs": list(langs), "free": free,
            "followers": followers, "hype_src": hype_src or ("f" if followers is not None else None), "moved": moved}


def past(day, reviews=10, tags=(SHOOTER,), langs=("english",), free=False, launch_type="full"):
    return {"launch_date": day, "launch_type": launch_type, "tags": list(tags), "langs": list(langs),
            "free": free, "reviews_30d": reviews}


UPCOMING = [
    # same name and followers as appid 2: by appid, and listed first so a stable sort alone gets it wrong
    game(22, "Alpha Run", "day", "2026-10-13", followers=5000),
    game(1, "Zeta Strike", "day", "2026-10-12", tags=(SHOOTER, ROGUELIKE), followers=5000),  # earlier this week
    game(2, "Alpha Run", "day", "2026-10-15", followers=5000),            # same followers: by name
    game(3, "Twin Tongue", "day", "2026-10-16", langs=("english", "schinese")),  # no follower number
    game(4, "Dragon Hall", "day", "2026-10-20", tags=(ROGUELIKE,), langs=("schinese",), followers=300),
    game(5, "Low Tag", "day", "2026-10-21", tags=(*FILLER, SHOOTER), free=True, followers=120000),
    game(6, "Mover", "month", "2026-10-01", "2026-10-31", followers=800,
         moved=["moved", "Q3 2026", "2026-10-11"]),
    game(7, "Cozy Quarter", "quarter", "2026-10-01", "2026-12-31", tags=(COZY, SHOOTER), free=True,
         moved=["date_set", "Coming soon", "2026-10-14"]),
    game(8, "Ran Out", "month", "2026-09-01", "2026-09-30"),
    game(9, "This Year", "year", "2026-01-01", "2026-12-31", followers=50),
    game(10, "Next Year", "year", "2027-01-01", "2027-12-31", tags=(ROGUELIKE,)),
    game(11, "Two Years", "year", "2028-01-01", "2028-12-31", free=True),
    game(12, "Far Off", "year", "2031-01-01", "2031-12-31", followers=7),
    game(13, "Ranked Only", "unknown", followers=900, hype_src="r"),
    game(14, "Summer", "day", "2027-06-01"),                               # past the 26 weeks
    game(15, "Last Week", "day", "2026-10-05"),                            # before this week
    game(16, "New Year Day", "day", "2027-01-01", followers=40),           # ISO week 53 of 2026
    game(17, "December", "month", "2026-12-01", "2026-12-31", tags=(ROGUELIKE, SHOOTER), followers=0),
    game(18, "Cozy Today", "day", "2026-10-14", tags=(COZY,), followers=10),
    game(19, "Spring Free", "quarter", "2027-01-01", "2027-03-31", tags=(ROGUELIKE,), free=True, followers=999),
    game(20, "Pixel Later", "day", "2026-11-03", tags=(PIXEL, *FILLER, ROGUELIKE), followers=60, hype_src="r",
         moved=["moved", "Oct 28, 2026", "2026-09-20"]),                # followers estimated from wishlist rank
    game(21, "Three Years", "year", "2029-01-01", "2029-12-31"),          # one year past LATER_AFTER: "later"
    # by code point the fullwidth F (U+FF26) comes first; by UTF-16 units the emoji (U+1F600) would
    game(23, "\U0001F600 Smile", "day", "2026-11-10"),
    game(24, "Ｆull", "day", "2026-11-11"),
]

# past launches around TODAY's 52-week window (2025-10-15 to 2026-10-13) for the typical week
TYPICAL = (
    [past("2025-10-14"), past("2025-10-15"), past("2026-10-13"), past("2026-10-14")]
    + [past("2026-03-0" + str(1 + i % 7)) for i in range(50)]
    + [past("2026-05-04", launch_type="early_access"), past("2026-05-04", launch_type="ea_exit"),
       past("2026-05-05", tags=(ROGUELIKE,)), past("2026-05-05", tags=(ROGUELIKE,), free=True),
       past("2026-06-01", langs=("schinese",))]
)


def _ranked(appid, name, rank, precision, start=None, end=None, date_text=None, **kw):
    return {**game(appid, name, precision, start, end, **kw), "date_text": date_text, "wishlist_rank": rank}


# for the most anticipated list: Top Wishlisted ranks at every kind of date, and games without one
RANKED = [
    _ranked(1, "Undated Giant", 1, "unknown", date_text="Coming soon", followers=250000, hype_src="r"),
    _ranked(2, "Far Shooter", 7, "day", "2027-08-20", tags=(SHOOTER, ROGUELIKE)),
    _ranked(3, "Cozy Year", 3, "year", "2028-01-01", "2028-12-31", tags=(COZY,), followers=900),
    _ranked(4, "Month Rogue", 12, "month", "2026-12-01", "2026-12-31", tags=(ROGUELIKE,)),
    _ranked(5, "Free Quarter", 2, "quarter", "2027-01-01", "2027-03-31", free=True),
    _ranked(6, "Chinese Only", 4, "day", "2026-11-03", langs=("schinese",)),
    _ranked(7, "Not Ranked", None, "day", "2026-10-20", followers=999999, hype_src="f"),
    _ranked(8, "Low Tag Cozy", 30, "day", "2026-10-28", tags=(*FILLER, COZY), followers=10),
    _ranked(9, "Past Day", 9, "day", "2026-09-30"),  # its date passed, still coming soon
    _ranked(11, "Same Rank B", 20, "day", "2027-02-01"),  # ranks are unique in the data; ties go by appid
    _ranked(10, "Same Rank A", 20, "day", "2027-02-02"),
    _ranked(12, "No Text", 25, "unknown"),  # undated, and the store gave no text
    # site_data sets `free` from the Free to Play tag when Steam's flag is not set; the list reads only `free`
    _ranked(13, "Tagged Free", 6, "unknown", date_text="To be announced", tags=(F2P, SHOOTER), free=True,
            langs=("english", "schinese")),
]


def _trend_games():
    """For the niche trend: exact dates over the next weeks (shooters, cozy games and
    a few free ones), month dates and a quarter that spread, and a far exact date."""
    out = [game(100 + i, f"Trend {i}", "day", (date(2026, 10, 14) + timedelta(days=i * 3)).isoformat())
           for i in range(30)]
    out += [game(200 + i, f"Other {i}", "day", (date(2026, 10, 15) + timedelta(days=i * 4)).isoformat(),
                 tags=(COZY,), langs=("english", "schinese")) for i in range(20)]
    out += [game(300 + i, f"Month {i}", "month", "2026-11-01", "2026-11-30", tags=(COZY, PIXEL)) for i in range(15)]
    out += [game(400, "Quarter", "quarter", "2026-10-01", "2026-12-31", tags=(SHOOTER, PIXEL)),
            game(401, "Far", "day", "2027-06-01"),
            *[game(500 + i, f"Free {i}", "day", "2026-10-20", tags=(PIXEL,), free=True) for i in range(12)]]
    return out


def _trend_history():
    """52 shooters and 156 cozy launches in the 52 weeks before 2026-10-14, a few
    Simplified Chinese ones, free pixel games, and launches outside the window."""
    start = date(2025, 10, 16)
    rows = [past((start + timedelta(days=i)).isoformat()) for i in range(0, 364, 7)]
    rows += [past((start + timedelta(days=i % 364)).isoformat(), tags=(COZY,)) for i in range(0, 156 * 2, 2)]
    rows += [past("2026-05-05", tags=(COZY,), langs=("schinese",))] * 5
    rows += [past("2026-05-05", tags=(PIXEL,), free=True)] * 30 + [past("2026-05-05", free=True)] * 30
    rows += [past("2025-10-14"), past("2026-10-14"), past("2026-05-05", launch_type="ea_exit")]
    return rows


def weekly(counts, start=date(2024, 1, 1), reviews=lambda i, j: (i * 37 + j * 11) % 101, **kw):
    """`counts[i]` launches in week i from `start`, spread over the week's days."""
    rows = []
    for i, n in enumerate(counts):
        for j in range(n):
            rows.append(past((start + timedelta(weeks=i, days=j % 7)).isoformat(), reviews(i, j), **kw))
    return rows


# 60 weeks with a repeating 1-2-3-2-4 pattern: equal busy counts, cut ties, and parts of 30 or more
PANEL = (weekly([(1, 2, 3, 2, 4)[i % 5] for i in range(60)])
         + weekly([(1, 2, 3, 2, 4)[i % 5] for i in range(60)], tags=(COZY,), langs=("schinese",))
         + weekly([1 + i % 2 for i in range(60)], free=True)
         + weekly([1] * 10, reviews=lambda i, j: None)                     # no review count yet
         + weekly([0] * 20 + [2, 1, 3] * 10, tags=(PIXEL,))                 # first appears in week 20
         + [past("2024-02-05", 3, launch_type="early_access"), past("2024-02-05", 3, launch_type="ea_exit")])

# exact halves at 2 decimals: 13 weeks of 8, then 1, 3 and 5 others against 8 (0.125, 0.375, 0.625)
HALVES = [r for tag, n in ((SHOOTER, 2), (COZY, 4), (ROGUELIKE, 6)) for r in weekly([8] * 13 + [n], tags=(tag,))]

# under one launch a week: the usual week counts as 1, so a lone launch is quiet
SPARSE = weekly([0] * 14 + [1, 0] * 12 + [3])

# a niche with a long gap (weeks with no usual launches), its last week complete
# (7 launches, Monday to Sunday); without the Sunday launch that week is partial
GAP = weekly([3] * 14 + [0] * 16 + [2, 5, 7])
GAP_PARTIAL = GAP[:-1]


def season_history():
    """Weekly launches 2022 to 2026-10-11 (a Sunday): a quiet Christmas week, a busy
    week after each Next Fest, a Chinese-only market and free games."""
    fests = {date(y, m, d) for y, m, d in NEXT_FESTS}
    rows, week = [], date(2022, 1, 3)
    while week <= date(2026, 10, 5):
        days = _days(week)
        n = 2 if (1, 1) in days else 1 if (12, 25) in days else 5 if week - timedelta(weeks=1) in fests else 3
        n += week.month in (6, 7)
        days = [(week + timedelta(days=j % 7)).isoformat() for j in range(n)]
        rows += [past(d, tags=(SHOOTER,) if j % 2 else (ROGUELIKE,)) for j, d in enumerate(days)]
        rows.append(past((week + timedelta(days=2)).isoformat(), langs=("schinese",)))
        if week.toordinal() % 3:
            rows.append(past((week + timedelta(days=4)).isoformat(), free=True))
        week += timedelta(weeks=1)
    rows.append(past("2026-10-11"))
    return rows


NEXT_FESTS = [(2022, 2, 21), (2022, 6, 13), (2022, 10, 3), (2023, 2, 6), (2023, 6, 19), (2023, 10, 9),
              (2024, 2, 5), (2024, 6, 10), (2024, 10, 14), (2025, 2, 24), (2025, 6, 9), (2025, 10, 13),
              (2026, 2, 23), (2026, 6, 15), (2026, 10, 19), (2027, 2, 22)]


def season_events():
    events = []
    for y, m, d in NEXT_FESTS:
        month = date(y, m, d).strftime("%B")
        name = f"Steam Next Fest: {month} {y} Edition" if m == 6 else f"Steam Next Fest {month} {y}"
        events.append({"name": name, "type": "next_fest", "start": date(y, m, d).isoformat()})
    for y in range(2022, 2027):
        events.append({"name": f"Steam Winter Sale {y}", "type": "seasonal_sale", "start": f"{y}-12-{18 + y % 4}"})
        events.append({"name": f"Christmas to New Year {y}", "type": "regional_holiday", "start": f"{y}-12-24"})
        events.append({"name": f"Big Game {y}", "type": "major_release", "start": f"{y}-11-0{1 + y % 5}"})
    return events


def yearly_ratios(start=date(2019, 1, 7), end=date(2026, 12, 28)):
    """Synthetic weekly ratios: 0.7 in a week that holds Jan 1, 0.4 in one that holds
    Dec 25 (2023's Dec 25 is a Monday: that week counts as New Year), 2.0 in one that
    holds Feb 29, and a small wobble from year to year and week to week."""
    out, week = {}, start
    while week <= end:
        days = _days(week)
        r = 0.7 if (1, 1) in days else 0.4 if (12, 25) in days else 2.0 if (2, 29) in days else 1.0
        out[week.isoformat()] = round(r + 0.05 * (week.year % 3) - 0.01 * (week.isocalendar()[1] % 4), 4)
        week += timedelta(weeks=1)
    return out


def _days(week: date) -> set[tuple[int, int]]:
    """(month, day) of each day of the week."""
    return {((week + timedelta(days=k)).month, (week + timedelta(days=k)).day) for k in range(7)}


def heatmap_cases() -> Cases:
    c = Cases(games=UPCOMING, typical=TYPICAL, trend_games=_trend_games(), trend_history=_trend_history(),
              ranked=RANKED)
    today = "2026-10-14"  # a Wednesday: week 0 is partial for vague dates
    c.add("all games, no history", "heatmap", games="$games", today=today)
    c.add("shooter with the typical week", "heatmap", games="$games", today=today, selection=[SHOOTER],
          history="$typical")
    c.add("shooter and roguelike", "heatmap", games="$games", today=today, selection=[SHOOTER, ROGUELIKE],
          mode="and", history="$typical")
    c.add("shooter or roguelike", "heatmap", games="$games", today=today, selection=[SHOOTER, ROGUELIKE],
          mode="or", history="$typical")
    c.add("no match", "heatmap", games="$games", today=today, selection=[COZY, PIXEL], mode="and",
          history="$typical")
    c.add("simplified chinese only", "heatmap", games="$games", today=today, languages=["schinese"],
          history="$typical")
    c.add("english or schinese", "heatmap", games="$games", today=today, languages=["english", "schinese"])
    c.add("year end: week 53 and partial weeks", "heatmap", games="$games", today="2026-12-23")
    c.add("on a Monday", "heatmap", games="$games", today="2026-10-12", selection=[ROGUELIKE])
    c.add("rows: no tags", "heatmap_rows", games="$games", today=today, history="$typical")
    c.add("rows: one tag", "heatmap_rows", games="$games", today=today, selection=[ROGUELIKE])
    c.add("rows: two tags, or", "heatmap_rows", games="$games", today=today, selection=[SHOOTER, ROGUELIKE],
          mode="or", history="$typical")
    c.add("rows: three tags, and", "heatmap_rows", games="$games", today=today,
          selection=[SHOOTER, ROGUELIKE, COZY], mode="and", history="$typical")
    c.add("normalized: free has no usual week", "normalized", games="$games", today=today,
          selection=[SHOOTER], history="$typical")
    c.add("normalized: roguelike, both groups", "normalized", games="$games", today=today,
          selection=[ROGUELIKE], history="$typical")
    c.add("normalized: no history", "normalized", games="$games", today=today)
    c.add("niche trend: no tags", "niche_trend", games="$trend_games", history="$trend_history", today=today)
    c.add("niche trend: shooter, clear", "niche_trend", games="$trend_games", history="$trend_history",
          today=today, selection=[SHOOTER])
    c.add("niche trend: cozy, a smaller share, month dates left out", "niche_trend", games="$trend_games",
          history="$trend_history", today=today, selection=[COZY])
    c.add("niche trend: pixel, tiny niche, free group", "niche_trend", games="$trend_games",
          history="$trend_history", today=today, selection=[PIXEL])
    c.add("niche trend: shooter or pixel", "niche_trend", games="$trend_games", history="$trend_history",
          today=today, selection=[SHOOTER, PIXEL], mode="or")
    c.add("niche trend: schinese", "niche_trend", games="$trend_games", history="$trend_history",
          today=today, selection=[COZY], languages=["schinese"])
    c.add("niche trend: no history", "niche_trend", games="$trend_games", history=[], today=today,
          selection=[SHOOTER])
    c.add("niche trend: few games, the typical week", "niche_trend", games="$games", history="$typical",
          today=today, selection=[SHOOTER])
    c.add("week games: this week, shooter", "week_games", games="$games", today=today, week="2026-10-12",
          selection=[SHOOTER])
    c.add("week games: next week, all", "week_games", games="$games", today=today, week="2026-10-19")
    c.add("week games: next week, roguelike or shooter", "week_games", games="$games", today=today,
          week="2026-10-19", selection=[ROGUELIKE, SHOOTER], mode="or")
    c.add("week games: moved from a month to a day", "week_games", games="$games", today=today,
          week="2026-11-02", selection=[ROGUELIKE])
    c.add("week games: week 53 without year dates", "week_games", games="$games", today="2026-12-23",
          week="2026-12-28")
    c.add("week games: week 53 with year dates", "week_games", games="$games", today="2026-12-23",
          week="2026-12-28", year=True)
    c.add("week games: schinese", "week_games", games="$games", today=today, week="2026-10-19",
          languages=["schinese"])
    c.add("week games: names compared by code point", "week_games", games="$games", today=today,
          week="2026-11-09")
    c.add("week games: tag places, pixel or roguelike", "week_games", games="$games", today=today,
          week="2026-11-02", selection=[PIXEL, ROGUELIKE], mode="or")
    c.add("week games: tag places, roguelike and pixel", "week_games", games="$games", today=today,
          week="2026-11-02", selection=[ROGUELIKE, PIXEL], mode="and")
    c.add("most anticipated: no tags", "most_anticipated", games="$ranked")
    c.add("most anticipated: no tags, top 3", "most_anticipated", games="$ranked", limit=3)
    c.add("most anticipated: shooter", "most_anticipated", games="$ranked", selection=[SHOOTER])
    c.add("most anticipated: cozy or roguelike", "most_anticipated", games="$ranked", selection=[COZY, ROGUELIKE],
          mode="or")
    c.add("most anticipated: shooter and roguelike", "most_anticipated", games="$ranked",
          selection=[SHOOTER, ROGUELIKE])
    c.add("most anticipated: schinese", "most_anticipated", games="$ranked", languages=["schinese"])
    c.add("most anticipated: no tags, english or schinese", "most_anticipated", games="$ranked",
          languages=["english", "schinese"])
    c.add("most anticipated: free to play tag", "most_anticipated", games="$ranked", selection=[F2P])
    c.add("most anticipated: no match", "most_anticipated", games="$ranked", selection=[PIXEL])
    c.add("most anticipated: cozy, a tag below the top 10", "most_anticipated", games="$ranked", selection=[COZY])
    c.add("most anticipated: no ranks", "most_anticipated", games="$games", selection=[SHOOTER])
    c.add("match count: all games", "match_count", games="$games", history="$typical")
    c.add("match count: shooter, by group", "match_count", games="$games", history="$typical", selection=[SHOOTER])
    c.add("match count: roguelike or cozy, schinese", "match_count", games="$games", history="$typical",
          selection=[ROGUELIKE, COZY], mode="or", languages=["schinese"])
    c.add("match count: no match", "match_count", games="$games", history="$typical", selection=[COZY, PIXEL])
    for tags, sel, mode in (([ROGUELIKE, 492, SHOOTER], [SHOOTER, ROGUELIKE], "and"),
                            ([ROGUELIKE, 492, SHOOTER], [SHOOTER, COZY], "and"),
                            ([ROGUELIKE, 492, SHOOTER], [SHOOTER, COZY], "or"),
                            ([ROGUELIKE], [], "and"), ([], [SHOOTER], "or")):
        c.add(f"matches {sel} {mode} in {tags}", "matches", tags=tags, selection=sel, mode=mode)
    for tags, sel in (([ROGUELIKE, 492, SHOOTER], [SHOOTER, ROGUELIKE]), ([ROGUELIKE, 492, SHOOTER], [COZY, 492]),
                      ([ROGUELIKE], []), ([], [SHOOTER]), ([*FILLER, SHOOTER, COZY], [COZY, SHOOTER])):
        c.add(f"tag pos {sel} in {tags}", "tag_pos", tags=tags, selection=sel)
    for langs, languages in ((["english"], []), (["english", "schinese"], ["schinese"]), (["english"], ["schinese"])):
        c.add(f"speaks {languages} with {langs}", "speaks", langs=langs, languages=languages)
    return c


def panel_cases() -> Cases:
    c = Cases(panel=PANEL, halves=HALVES, sparse=SPARSE)
    c.add("relative, under one launch a week", "history_panel", history="$sparse", min_group=1)
    c.add("relative, a tag that starts after the data: baseline from all launches", "history_panel",
          history="$panel", selection=[PIXEL], min_group=1)
    c.add("raw, shooter", "history_panel", history="$panel", selection=[SHOOTER], measure="raw")
    c.add("relative, shooter", "history_panel", history="$panel", selection=[SHOOTER])
    c.add("relative, all games, small parts", "history_panel", history="$panel", min_group=1)
    c.add("relative, shooter or cozy", "history_panel", history="$panel", selection=[SHOOTER, COZY], mode="or",
          min_group=5)
    c.add("relative, shooter and cozy: no match", "history_panel", history="$panel", selection=[SHOOTER, COZY])
    c.add("relative, schinese", "history_panel", history="$panel", languages=["schinese"], min_group=10)
    c.add("raw, min group 0", "history_panel", history="$panel", measure="raw", min_group=0)
    c.add("no history", "history_panel", history=[])
    for tag in (SHOOTER, COZY, ROGUELIKE):
        c.add(f"exact half rounds to even, tag {tag}", "history_panel", history="$halves", selection=[tag],
              min_group=1)
    for busy in ([0, 2, 2, 2], [0] * 40 + [1] * 40 + [3] * 40, [5, 5, 5], [], [0, 1, 1, 2, 2, 2],
                 [1, 1, 2, 2, 3, 3], [0.12, 0.38, 0.12, 0.62, 1.5, 0.38], [3, 1, 2]):
        c.add(f"cut points {busy[:8]} ({len(busy)})", "cut_points", busy=busy)
    for values, q in (([1, 2, 3, 4], 0.5), ([0, 10], 0.9), ([7], 0.75), ([5, 1, 9, 3, 3], 0.9), ([2, 4], 0.75)):
        c.add(f"percentile {values} {q}", "percentile", values=values, q=q)
    # exact halves of a cent (odd eighths) go to the even cent; 2.675 and 1.005 sit just below a half
    for x in (0.125, 0.375, 0.625, 0.875, 2.675, 1.005, 0.145, 1 / 3, 13 / 7, 12.5, 0, 9.995, 30 / 13):
        c.add(f"round {x}", "round2", x=x)
    return c


def season_cases() -> Cases:
    c = Cases(history=season_history(), events=season_events(), ratios=yearly_ratios(), gap=GAP,
              gap_partial=GAP_PARTIAL)
    c.inputs["series"] = _plain(season.event_series(c.inputs["events"]))
    c.inputs["history_ratios"] = _plain(season.weekly_ratios(c.inputs["history"]))
    c.add("ratios, paid", "weekly_ratios", history="$history")
    c.add("ratios, free", "weekly_ratios", history="$history", group="free")
    c.add("ratios, schinese", "weekly_ratios", history="$history", languages=["schinese"])
    c.add("ratios, shooter", "weekly_ratios", history="$history", selection=[SHOOTER])
    c.add("ratios: weeks with no usual launches", "weekly_ratios", history="$gap")
    c.add("ratios: partial last week left out", "weekly_ratios", history="$gap_partial")
    c.add("ratios: no history", "weekly_ratios", history=[])
    c.add("event series", "event_series", events="$events")
    c.add("estimate: Christmas week", "estimate", week="2026-12-21", ratios="$ratios", series={},
          before="2026-01-01")
    c.add("estimate: week 53 matched with New Year", "estimate", week="2026-12-28", ratios="$ratios", series={},
          before="2026-12-01")
    c.add("estimate: Thursday on Feb 29", "estimate", week="2024-02-26", ratios="$ratios", series={},
          before="2024-02-01")
    c.add("estimate: two years only", "estimate", week="2021-12-20", ratios="$ratios", series={},
          before="2021-06-01")
    c.add("estimate: nothing before", "estimate", week="2020-06-01", ratios="$ratios", series="$series",
          before="2018-01-01")
    c.add("estimate: after a Next Fest", "estimate", week="2026-10-26", ratios="$ratios", series="$series",
          before="2026-10-12")
    c.add("estimate: own occurrence is not a past year", "estimate", week="2024-02-19", ratios="$ratios",
          series="$series", before="2027-01-01")
    twin = [f"{y}-{md}" for y, mds in ((2023, ("03-06", "04-17")), (2024, ("03-04", "04-15")),
                                       (2025, ("03-03", "04-14")), (2026, ("03-02", "04-13"))) for md in mds]
    c.add("estimate: halfway between two occurrences goes with the earlier", "estimate", week="2026-03-23",
          ratios="$ratios", series={"Twin Fest": twin}, before="2026-01-01")
    c.add("estimate: events from the history", "estimate", week="2026-03-02", ratios="$history_ratios",
          series="$series", before="2026-01-01")
    c.add("outlook", "outlook", history="$history", events="$events", today="2026-10-14")
    c.add("outlook, schinese", "outlook", history="$history", events="$events", today="2026-10-14",
          languages=["schinese"], weeks=8)
    c.add("outlook over the year end", "outlook", history="$history", events="$events", today="2026-12-23",
          weeks=6)
    return c


def trend_history():
    """Launches 2022 to 2026: shooters all along (more each year), cozy games from
    2024 Q2 on, some with both tags, Simplified Chinese and free ones, Early Access
    and ea_exit rows, launches without a review count yet, launches outside the
    window (2021, today and later), and games Steam has removed (not `listed`)."""
    rows, day = [], date(2022, 1, 1)
    i = 0
    while day < date(2026, 10, 20):
        cozy = day >= date(2024, 4, 1)
        tags = (COZY, SHOOTER) if cozy and i % 5 == 0 else (COZY,) if cozy and i % 3 == 0 else (SHOOTER,)
        rows.append(past(day.isoformat(), tags=tags, langs=("english", "schinese") if i % 4 == 0 else ("english",),
                         free=i % 7 == 0, launch_type="early_access" if i % 6 == 0 else "full",
                         reviews=None if day >= date(2026, 9, 12) else i % 50))
        i += 1
        day += timedelta(days=max(1, 9 - (day.year - 2022) * 2))  # more launches each year
    rows += [past("2021-12-31"), past("2024-05-05", launch_type="ea_exit"), past("2025-02-02", tags=(PIXEL,),
                                                                                  langs=("schinese",))]
    # Steam has removed these since: left out, in a recent quarter and an older one
    rows += [{**past("2026-08-03", tags=(COZY,)), "listed": False}, {**past("2026-08-04"), "listed": False},
             {**past("2023-03-03", tags=(COZY,), free=True), "listed": False}]
    for r in rows:
        r.setdefault("listed", True)
    return rows


def trend_cases() -> Cases:
    c = Cases(history=trend_history())
    today = "2026-10-14"
    c.add("quarters: mid-quarter", "quarters", today=today)
    c.add("quarters: a quarter's first day", "quarters", today="2026-10-01")
    c.add("quarters: the data's first day", "quarters", today="2022-01-01")
    c.add("quarters: fewer than the recent ones", "quarters", today="2022-04-02")
    c.add("no tags", "quarterly", history="$history", today=today)
    c.add("shooter", "quarterly", history="$history", today=today, selection=[SHOOTER])
    c.add("cozy: starts in 2024 Q2", "quarterly", history="$history", today=today, selection=[COZY])
    c.add("cozy and shooter", "quarterly", history="$history", today=today, selection=[COZY, SHOOTER], mode="and")
    c.add("cozy or pixel", "quarterly", history="$history", today=today, selection=[COZY, PIXEL], mode="or")
    c.add("schinese", "quarterly", history="$history", today=today, selection=[SHOOTER], languages=["schinese"])
    c.add("english or schinese, no tags", "quarterly", history="$history", today=today,
          languages=["english", "schinese"])
    c.add("partial quarter on its first day", "quarterly", history="$history", today="2026-10-01",
          selection=[COZY])
    c.add("no match", "quarterly", history="$history", today=today, selection=[PIXEL, SHOOTER])
    c.add("no history", "quarterly", history=[], today=today, selection=[SHOOTER])
    return c


def data_cases() -> Cases:
    meta = {"snapshot_date": "2026-10-12", "tags": [[113, "Free to Play", 1, 0], [1774, "Shooter", 2, 1],
                                                     [99999, None, 1, 0]],
            "languages": ["english", "schinese"], "rank_curve": None}
    table = {"columns": ["appid", "name", "tags", "langs", "free", "moved"],
             "rows": [[1, "A", [1, 0], [0, 1], True, None], [2, "B", [2], [], False, ["moved", "2026", "2026-10-12"]]]}
    history = {"columns": ["appid", "launch_date", "launch_type", "tags", "langs", "free", "price_cents",
                           "reviews_30d"],
               "rows": [[10, "2026-01-05", "full", [1], [0], False, 999, 12],
                        [11, "2026-01-06", "early_access", [0, 1], [1], True, None, None]]}
    c = Cases(meta=meta, table=table, history=history)
    c.add("table with meta", "table_rows", table="$table", meta="$meta")
    c.add("table without meta", "table_rows", table="$table")
    c.add("history with meta", "table_rows", table="$history", meta="$meta")
    return c


def build() -> dict[str, dict]:
    return {"heatmap.json": heatmap_cases().obj(), "panel.json": panel_cases().obj(),
            "season.json": season_cases().obj(), "data.json": data_cases().obj(), "trends.json": trend_cases().obj()}


def dump(obj: dict) -> str:
    """One input and one case per line, so a change shows up as a readable diff."""
    inputs = ",\n".join(f" {json.dumps(k)}: {json.dumps(v)}" for k, v in obj["inputs"].items())
    cases = ",\n".join(f" {json.dumps(c)}" for c in obj["cases"])
    return '{"inputs": {\n' + inputs + '\n},\n"cases": [\n' + cases + "\n]}\n"


def main(argv=None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, obj in build().items():
        (OUT / name).write_text(dump(obj), encoding="utf-8", newline="\n")
        print(f"{OUT / name}: {len(obj['cases'])} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
