"""Load and check data/events.yaml.

    python -m pipeline.events                     check the file
    python -m pipeline.events --check-steam _data also compare release dates with Steam's own

The file's rules are documented at its top. In short:
- Dates are Pacific calendar dates.
- Steam-run events (sales, Next Fest, themed fests) start at 10:00 Pacific on
  `start` and end at 10:00 Pacific on `end`, so the `end` day is only partly
  inside. Everything else covers whole days, `start` to `end` inclusive.
- A release's date is the day it became available, in Pacific time; for games
  on Steam at launch, the day it unlocked on Steam.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

PATH = Path(__file__).resolve().parents[1] / "data" / "events.yaml"
PACIFIC = ZoneInfo("America/Los_Angeles")

STEAM_RUN = {"seasonal_sale", "next_fest", "themed_fest"}
TYPES = STEAM_RUN | {"major_release", "regional_holiday"}
CONFIDENCE = {"high", "medium", "low"}
RELEASE_KINDS = {"full", "early_access", "early_access_exit", "expansion"}
SURPRISE = {"shadow_drop", "breakout"}
REGIONS = {"CN", "US", "global"}
STEAM_EVENT_HOUR = 10

# Apps whose Steam release date is known to be wrong, so --check-steam skips them.
STEAM_DATE_EXCEPTIONS = {
    3606480: "Call of Duty: Black Ops 7: Steam lists Nov 21, 2025, but PC went live Nov 13 at 9pm PT "
             "(launch reviews and patch notes on its Steam page that day)",
}

ALLOWED = {
    "common": {"name", "type", "start", "end", "confidence", "source", "note"},
    "major_release": {"on_steam_at_launch", "release_kind", "steam_appid", "free_to_play", "surprise"},
    "themed_fest": {"tags"},
    "regional_holiday": {"region"},
}


def load(path: Path = PATH) -> list[dict]:
    return yaml.safe_load(Path(path).read_text(encoding="ascii"))["events"]


def window(event: dict) -> tuple[datetime, datetime]:
    """When the event is in effect, as Pacific datetimes [start, end)."""
    if event["type"] in STEAM_RUN:
        at = time(STEAM_EVENT_HOUR)
        return (datetime.combine(event["start"], at, PACIFIC), datetime.combine(event["end"], at, PACIFIC))
    return (datetime.combine(event["start"], time(0), PACIFIC),
            datetime.combine(event["end"] + timedelta(days=1), time(0), PACIFIC))


def validate(events: list[dict]) -> list[str]:
    """Problems with the file, as readable strings. Empty means it is fine."""
    problems = []
    seen = set()
    for i, e in enumerate(events):
        who = f"#{i} {e.get('name', '?')!r}"
        t = e.get("type")
        if t not in TYPES:
            problems.append(f"{who}: unknown type {t!r}")
            continue
        extra = set(e) - ALLOWED["common"] - ALLOWED.get(t, set())
        if extra:
            problems.append(f"{who}: fields not allowed for {t}: {sorted(extra)}")
        for f in ("name", "start", "end", "confidence", "source"):
            if f not in e:
                problems.append(f"{who}: missing {f}")
        if not (isinstance(e.get("start"), date) and isinstance(e.get("end"), date)):
            problems.append(f"{who}: start and end must be dates")
            continue
        if e["start"] > e["end"]:
            problems.append(f"{who}: start after end")
        if t in STEAM_RUN and e["start"] == e["end"]:
            problems.append(f"{who}: a Steam event must end on a later day than it starts")
        if not str(e.get("source", "")).startswith("https://"):
            problems.append(f"{who}: source must be an https link")
        if e.get("confidence") not in CONFIDENCE:
            problems.append(f"{who}: confidence must be one of {sorted(CONFIDENCE)}")
        if t == "major_release":
            if not isinstance(e.get("on_steam_at_launch"), bool):
                problems.append(f"{who}: on_steam_at_launch must be true or false")
            if e.get("release_kind") not in RELEASE_KINDS:
                problems.append(f"{who}: release_kind must be one of {sorted(RELEASE_KINDS)}")
            if "steam_appid" in e and not (isinstance(e["steam_appid"], int) and e["steam_appid"] > 0):
                problems.append(f"{who}: steam_appid must be a positive integer")
            if e.get("on_steam_at_launch") and "steam_appid" not in e:
                problems.append(f"{who}: on Steam at launch but no steam_appid")
            if "free_to_play" in e and e["free_to_play"] is not True:
                problems.append(f"{who}: write free_to_play only when true")
            if "surprise" in e and e["surprise"] not in SURPRISE:
                problems.append(f"{who}: surprise must be one of {sorted(SURPRISE)}")
            if e["start"] != e["end"]:
                problems.append(f"{who}: a release is a single day (start == end)")
        if t == "themed_fest" and "tags" in e:
            if not (isinstance(e["tags"], list) and e["tags"] and all(isinstance(x, str) for x in e["tags"])):
                problems.append(f"{who}: tags must be a non-empty list of tag names")
        if t == "regional_holiday" and e.get("region") not in REGIONS:
            problems.append(f"{who}: region must be one of {sorted(REGIONS)}")
        key = (e.get("name"), e["start"])
        if key in seen:
            problems.append(f"{who}: duplicate of an earlier entry with the same name and start")
        seen.add(key)
    keys = [(e["start"], e["type"], e["name"]) for e in events
            if isinstance(e.get("start"), date) and "type" in e and "name" in e]
    if keys != sorted(keys):
        problems.append("events are not sorted by (start, type, name)")
    return problems


def steam_dates(data_dir: Path) -> dict[int, tuple[date, date]]:
    """Steam's own dates (Pacific) per appid: (first launch, current release).

    They differ for games that left Early Access: first launch is the EA start
    when Steam gives it, current release is the 1.0 date. The newest upcoming
    snapshot adds exact dates for games not out yet.
    """
    from . import steam, storage

    out: dict[int, tuple[date, date]] = {}
    for r in storage.read_csv(data_dir / "history" / "games.csv"):
        first = date.fromisoformat(r["launch_date"])
        current = steam.pacific_date(int(r["steam_release_ts"])) if r["steam_release_ts"] else first
        out[int(r["appid"])] = (first, current)
    snaps = sorted((data_dir / "upcoming" / "snapshots").glob("*.csv.gz"))
    if snaps:
        for r in storage.read_csv(snaps[-1]):
            if r["precision"] == "day":
                d = date.fromisoformat(r["date"])
                out[int(r["appid"])] = (d, d)
    return out


def check_against_steam(events: list[dict], data_dir: Path) -> list[str]:
    """Releases on Steam at launch whose date differs from Steam's own date."""
    known = steam_dates(data_dir)
    problems = []
    for e in events:
        if e["type"] != "major_release" or not e.get("on_steam_at_launch") or "steam_appid" not in e:
            continue
        dates = known.get(e["steam_appid"])
        if dates is None or e["steam_appid"] in STEAM_DATE_EXCEPTIONS:
            continue  # not in collected data (a DLC, released before 2022, delisted) or known wrong
        steam_date = dates[1] if e.get("release_kind") == "early_access_exit" else dates[0]
        if e.get("release_kind") == "early_access_exit" and steam_date < e["start"]:
            continue  # the 1.0 has not happened yet in Steam's data
        if steam_date != e["start"]:
            problems.append(f"{e['name']!r}: events.yaml says {e['start']}, Steam says {steam_date} "
                            f"(app {e['steam_appid']})")
    return problems


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file", type=Path, default=PATH)
    p.add_argument("--check-steam", type=Path, metavar="DATA_DIR",
                   help="also compare release dates with Steam's data in DATA_DIR (e.g. _data)")
    args = p.parse_args(argv)
    events = load(args.file)
    problems = validate(events)
    if args.check_steam:
        problems += check_against_steam(events, args.check_steam)
    for line in problems:
        print(line)
    print(f"{len(events)} events, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
