"""Calibrates the niche trend's ratio cutoff (heatmap.TREND_RATIO) on real launches.

    python -m analysis.trend_calibration [--data site/public/data]

The trend line compares a niche's share of upcoming games with its share of last
year's launches. Shares drift even when nothing is announced, so the cutoff is set
where that drift alone rarely crosses it: each 13-week window of real launches since
2023 (paid and free, English) plays "upcoming", against the 52 weeks before it, for
every tag. The rule (heatmap.trend_test: minimum sizes, the ratio cutoff, |z| of at
least TREND_Z) should flag about 5% of these tag-quarters. Reads local files only
(meta.json and history.json from analysis.site_data).

Result on the 2026-10-13 data: 15 windows from 2023-01-02, 7,038 eligible
tag-quarters (paid 4,569, free 2,469). The z rule alone flags 13.7%. A ratio of 1.45
either way (or 1 / 1.45 = 0.69) brings it to 4.4% (paid 3.5%, free 6.0%); 1.40 gives
5.2%. So TREND_RATIO is 1.45. Upcoming games have fewer exact dates than a quarter of
real launches, so the z rule is weaker on them and the ratio carries the cut.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from .heatmap import PANEL_TYPES, TREND_Z, TYPICAL_WEEKS, WEEKS, speaks, trend_test, week_start
from .site_data import table_rows

FIRST = date(2023, 1, 2)  # the first window: a full year of launches before it
TARGET = 0.05  # the share of tag-quarters the rule may flag on real launches
CUTS = [round(1 + 0.05 * i, 2) for i in range(1, 41)]  # 1.05 to 3.00


def windows(history, first: date = FIRST) -> list[date]:
    """Mondays of 13-week windows from `first`, each ending before the data's last full week."""
    newest = max(date.fromisoformat(h["launch_date"]) for h in history)
    end = week_start(newest)  # the newest week may be partial
    out, start = [], first
    while start + timedelta(weeks=WEEKS) <= end:
        out.append(start)
        start += timedelta(weeks=WEEKS)
    return out


def tag_quarters(history, languages=("english",)) -> list[tuple[str, dict]]:
    """For each window, group and tag: the four counts trend_test takes, with the
    window's launches standing in for the upcoming games with exact dates."""
    rows = [(date.fromisoformat(h["launch_date"]), "free" if h["free"] else "paid", set(h["tags"]))
            for h in history if h["launch_type"] in PANEL_TYPES and speaks(h["langs"], languages)]
    out = []
    for start in windows(history):
        end, since = start + timedelta(weeks=WEEKS), start - timedelta(weeks=TYPICAL_WEEKS)
        for group in ("paid", "free"):
            now, past = Counter(), Counter()
            n_now = n_past = 0
            for day, g, tags in rows:
                if g != group:
                    continue
                if start <= day < end:
                    n_now += 1
                    now.update(tags)
                elif since <= day < start:
                    n_past += 1
                    past.update(tags)
            for tag in set(now) | set(past):
                out.append((group, {"exact": now[tag], "exact_all": n_now, "past": past[tag], "past_all": n_past}))
    return out


def flag_rates(cases, cuts=CUTS, z_cut: float = TREND_Z) -> dict:
    """Share of eligible tag-quarters (both minimum sizes met) flagged at each ratio cut,
    per group and pooled; and with the z rule alone (ratio cut 1)."""
    tested = [(g, c) for g, c in cases if trend_test(**c, ratio_cut=1, z_cut=0)["clear"]]  # sizes only
    out = {"eligible": {g: sum(x == g for x, _ in tested) for g in ("paid", "free")}}
    out["eligible"]["all"] = len(tested)

    def rate(ratio_cut):
        hits = Counter(g for g, c in tested if trend_test(**c, ratio_cut=ratio_cut, z_cut=z_cut)["clear"])
        return {g: hits[g] / max(out["eligible"][g], 1) for g in ("paid", "free")} | {
            "all": sum(hits.values()) / max(len(tested), 1)}

    out["z_only"] = rate(1)
    out["cuts"] = {cut: rate(cut) for cut in cuts}
    return out


def choose(rates: dict, target: float = TARGET) -> float:
    """The smallest cut that flags at most `target` of all eligible tag-quarters."""
    return next(cut for cut, r in rates["cuts"].items() if r["all"] <= target)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("site/public/data"))
    args = p.parse_args(argv)
    meta = json.loads((args.data / "meta.json").read_text(encoding="utf-8"))
    history = table_rows(json.loads((args.data / "history.json").read_text(encoding="utf-8")), meta)
    cases = tag_quarters(history)
    rates = flag_rates(cases)
    print(f"windows from {FIRST}: {len(windows(history))}; eligible tag-quarters: {rates['eligible']}")
    print(f"|z| >= {TREND_Z} alone flags: " + ", ".join(f"{g} {r:.1%}" for g, r in rates["z_only"].items()))
    for cut, r in rates["cuts"].items():
        print(f"ratio {cut:.2f}: " + ", ".join(f"{g} {x:.1%}" for g, x in r.items()))
    cut = choose(rates)
    print(f"chosen: {cut:.2f} (flags {rates['cuts'][cut]['all']:.1%} of tag-quarters on real launches)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
