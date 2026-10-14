"""Build the website's data files from the data branch (docs/phase2-plan.md section 5).

    python -m analysis.site_data --data-dir _data --gp-dir _gp --out site/public/data

Writes, as compact JSON:
  meta.json      snapshot date, tags (id, name, upcoming games, past launches),
                 languages; rows below point into these two lists by index
  upcoming.json  one row per game in the newest snapshot that has a date or a
                 wishlist rank (day dates more than 30 days past are stale pages
                 and left out); `date_text` is the store's text for games with
                 no date ("Coming soon", "To be announced"), null for the rest
  history.json   one row per past launch, except `ea_exit` (not a first launch);
                 `listed` when the game was in the newest listing run (its
                 `last_listed` is the newest in the file, or empty): Trends counts
                 only those, so every quarter holds games still on Steam
  events.json    events.yaml with each event's window in UTC

upcoming.json and history.json are {"columns": [...], "rows": [[...], ...]}.
`followers` is the newest Games Popularity count (hype_src "f"; from
gp/latest_followers.csv, or every gp/followers/*.csv.gz without it) or, for a game
with only a wishlist rank, an estimate from a curve fitted on games with both
(hype_src "r", needs at least 30 such games). `moved` is [kind, old date text,
date of the change] when the date changed in the last 30 days: kind "moved",
or "date_set" when the game had no date before.

Reads only local files: no requests. Rebuilding the same data gives the same
files (no build time is written).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from pipeline import events as event_data
from pipeline import steam, storage

STALE_DAYS = 30
MOVED_DAYS = 30
MIN_FIT = 30
UPCOMING_COLUMNS = ["appid", "name", "precision", "date", "date_end", "date_text", "tags", "langs", "free", "ea",
                    "wishlist_rank", "followers", "hype_src", "moved"]
HISTORY_COLUMNS = ["appid", "launch_date", "launch_type", "tags", "langs", "free", "price_cents", "reviews_30d",
                   "listed"]
DATE_FIELDS = ("precision", "date", "date_end")  # a change in these is a move; wording alone is not

log = logging.getLogger("site_data")


tag_ids = steam.tag_ids
is_free = steam.free_game


def _int(raw: str | None) -> int | None:
    return int(raw) if raw not in (None, "") else None


def newest_followers(gp_dir: Path | None) -> dict[int, int]:
    """Newest follower count per game (by Games Popularity's own time), from
    gp/latest_followers.csv, or from every gp/followers/*.csv.gz without it."""
    best: dict[int, tuple[str, int]] = {}
    if gp_dir is None:
        return {}
    latest = gp_dir / "latest_followers.csv"
    if latest.exists():
        return {int(r["appid"]): int(r["followers"]) for r in storage.read_csv(latest) if r["followers"]}
    for f in sorted((gp_dir / "followers").glob("*.csv.gz")):
        for r in storage.read_csv(f):
            appid, at = int(r["appid"]), r["observed_at"]
            # on an equal observed_at the later file wins, as in collect_gp's latest_followers.csv
            if r["followers"] and (appid not in best or at >= best[appid][0]):
                best[appid] = (at, int(r["followers"]))
    return {appid: v for appid, (_, v) in best.items()}


def rank_curve(pairs: list[tuple[int, int]]) -> tuple[float, float] | None:
    """Least-squares fit of log(followers) = a + b log(rank), or None with fewer than MIN_FIT games."""
    pts = [(math.log(r), math.log(f)) for r, f in pairs if r > 0 and f > 0]
    if len(pts) < MIN_FIT:
        return None
    mx, my = sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in pts) / sxx
    return my - b * mx, b


def recent_changes(snapshot_dir: Path, latest: date, days: int = MOVED_DAYS) -> dict[int, list]:
    """Each game's last date change in the `days` before `latest`: [kind, old raw text, change date].
    A change is a new precision or date range, seen on the first snapshot that shows
    it; new wording for the same dates is not one, and a game's first snapshot is
    not one. A game that leaves the list and comes back is compared with its last
    snapshot before it left only if that is inside the window."""
    since = latest - timedelta(days=days + 1)  # one more day, as the baseline
    files = [f for f in sorted(snapshot_dir.glob("*.csv.gz")) if since <= date.fromisoformat(f.name[:10]) <= latest]
    last: dict[int, tuple[tuple, str]] = {}  # appid: (dates, raw text) in its newest snapshot so far
    changes: dict[int, list] = {}
    for f in files:
        day = f.name[:10]
        for r in storage.read_csv(f):
            appid = int(r["appid"])
            cur = tuple(r.get(k, "") for k in DATE_FIELDS)
            old = last.get(appid)
            if old is not None and old[0] != cur:
                changes[appid] = ["date_set" if old[0][0] in ("", "unknown") else "moved", old[1], day]
            last[appid] = (cur, r.get("raw", ""))
    return changes


def build(data_dir: Path, events_path: Path, out: Path, gp_dir: Path | None = None) -> dict:
    snapshot_dir = data_dir / "upcoming" / "snapshots"
    snapshots = sorted(snapshot_dir.glob("*.csv.gz"))
    if not snapshots:
        raise SystemExit(f"no upcoming snapshot in {snapshot_dir}")
    snapshot_path = snapshots[-1]
    snapshot_date = date.fromisoformat(snapshot_path.name[:10])
    apps = {int(r["appid"]): r for r in storage.read_csv(data_dir / "upcoming" / "apps.csv")}
    tag_names = {int(r["tagid"]): r["name"] for r in storage.read_csv(data_dir / "tags.csv")}
    followers = newest_followers(gp_dir)
    moved = recent_changes(snapshot_dir, snapshot_date)
    stale_before = (snapshot_date - timedelta(days=STALE_DAYS)).isoformat()

    upcoming = []
    for r in storage.read_csv(snapshot_path):
        appid, precision = int(r["appid"]), r["precision"] or "unknown"
        if precision == "unknown" and not r["wishlist_rank"]:
            continue
        if precision == "day" and r["date_end"] < stale_before:
            continue
        app = apps.get(appid, {})
        tags = tag_ids(app.get("tags", ""))
        upcoming.append({
            "appid": appid, "name": app.get("name", ""), "precision": precision,
            "date": r["date"] or None, "date_end": r["date_end"] or None,
            # the store's words for a game with no date ("Coming soon"); the site rebuilds the rest
            "date_text": (r["raw"] or None) if precision == "unknown" else None, "tags": tags,
            "langs": [x for x in app.get("languages", "").split("|") if x], "free": is_free(app.get("is_free"), tags),
            "ea": r["early_access"] == "1", "wishlist_rank": _int(r["wishlist_rank"]),
            "followers": followers.get(appid), "hype_src": "f" if appid in followers else None,
            "moved": moved.get(appid) if precision != "unknown" else None,
        })
    curve = rank_curve([(g["wishlist_rank"], g["followers"]) for g in upcoming
                        if g["wishlist_rank"] and g["followers"] is not None])
    if curve:
        for g in upcoming:
            if g["followers"] is None and g["wishlist_rank"]:
                g["followers"] = round(math.exp(curve[0] + curve[1] * math.log(g["wishlist_rank"])))
                g["hype_src"] = "r"

    history = []
    rows = storage.read_csv(data_dir / "history" / "games.csv")
    # the newest listing run: a game it no longer lists keeps its row with an older last_listed
    newest = max((r.get("last_listed") or "" for r in rows), default="")
    for r in rows:
        if r["launch_type"] == "ea_exit":
            continue
        tags = tag_ids(r["tags"])
        history.append({
            "appid": int(r["appid"]), "launch_date": r["launch_date"], "launch_type": r["launch_type"],
            "tags": tags, "langs": [x for x in r["languages"].split("|") if x], "free": is_free(r["is_free"], tags),
            "price_cents": _int(r["price_cents"]), "reviews_30d": _int(r["reviews_30d"]),
            "listed": (r.get("last_listed") or newest) == newest,
        })

    # shared lists: tags (every known tag, then any unknown ones) and languages, by first use
    tag_list = sorted(tag_names) + sorted({t for g in upcoming + history for t in g["tags"]} - set(tag_names))
    tag_index = {t: i for i, t in enumerate(tag_list)}
    languages = sorted({x for g in upcoming + history for x in g["langs"]})
    lang_index = {x: i for i, x in enumerate(languages)}
    up_count = {t: 0 for t in tag_list}
    hist_count = dict(up_count)
    for games, counts in ((upcoming, up_count), (history, hist_count)):
        for g in games:
            for t in g["tags"]:
                counts[t] += 1
            g["tags"] = [tag_index[t] for t in g["tags"]]
            g["langs"] = [lang_index[x] for x in g["langs"]]
    meta = {
        "snapshot_date": snapshot_date.isoformat(),
        "tags": [[t, tag_names.get(t), up_count[t], hist_count[t]] for t in tag_list],
        "languages": languages,
        "rank_curve": list(curve) if curve else None,
    }
    events = []
    for e in event_data.load(events_path):
        starts, ends = event_data.window(e)
        events.append({k: (v.isoformat() if isinstance(v, date) else v) for k, v in e.items()}
                      | {"starts_at": _utc(starts), "ends_at": _utc(ends)})

    out.mkdir(parents=True, exist_ok=True)
    files = {"meta.json": meta, "upcoming.json": _table(upcoming, UPCOMING_COLUMNS),
             "history.json": _table(history, HISTORY_COLUMNS), "events.json": events}
    for name, obj in files.items():
        (out / name).write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return {"snapshot_date": snapshot_date.isoformat(), "upcoming": len(upcoming), "history": len(history),
            "events": len(events), "with_followers": sum(g["hype_src"] == "f" for g in upcoming),
            "rank_estimates": sum(g["hype_src"] == "r" for g in upcoming),
            "moved": sum(g["moved"] is not None for g in upcoming)}


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _table(rows: list[dict], columns: list[str]) -> dict:
    return {"columns": columns, "rows": [[r[c] for c in columns] for r in rows]}


def load_table(path: Path, meta: dict | None = None) -> list[dict]:
    """Rows of upcoming.json or history.json as dicts; with `meta`, tags and langs
    are turned back into tag ids and language names."""
    return table_rows(json.loads(Path(path).read_text(encoding="utf-8")), meta)


def table_rows(table: dict, meta: dict | None = None) -> list[dict]:
    """load_table for a table already read (site/src/lib/data.js fromTable is its copy)."""
    rows = [dict(zip(table["columns"], r)) for r in table["rows"]]
    if meta:
        for r in rows:
            r["tags"] = [meta["tags"][i][0] for i in r["tags"]]
            r["langs"] = [meta["languages"][i] for i in r["langs"]]
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("_data"))
    p.add_argument("--gp-dir", type=Path, default=None,
                   help="Games Popularity folder (latest_followers.csv or followers/*.csv.gz); "
                        "without it, no follower numbers")
    p.add_argument("--events", type=Path, default=Path("data/events.yaml"))
    p.add_argument("--out", type=Path, default=Path("site/public/data"))
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.out.resolve() == args.data_dir.resolve():
        raise SystemExit("--out must not be the data folder")
    log.info("built %s: %s", args.out, build(args.data_dir, args.events, args.out, args.gp_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
