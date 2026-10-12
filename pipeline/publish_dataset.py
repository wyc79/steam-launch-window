"""Publish the data branch as a Parquet dataset on Hugging Face.

Builds a folder like this from --data-dir, then uploads it:

  history/games.parquet                 one row per launch since 2022
  upcoming/apps.parquet                 names, tags, languages of every upcoming game seen
  upcoming/snapshots/YYYY-MM.parquet    every daily snapshot of that month (snapshot_date column)
  upcoming/release_changes.parquet      derived: each first sighting, change of the release date
                                        text or range, and exit from the coming-soon list
  upcoming/runs.parquet                 one row per daily collection run
  followers/latest.parquet              newest follower count per game
  followers/snapshots/YYYY-MM.parquet   every follower count fetched that month
  tags.parquet, events.parquet
  manifest.json                         rows and columns of every file, checked before upload
  README.md                             dataset card

The dataset also holds gp/ (Games Popularity follower and player histories),
written there directly by the daily job. This script leaves gp/ alone; the card
lists its configs when its files are found in the dataset (needs HF_TOKEN and
--repo-id, also in a dry run).

Needs the `publish` extra (pandas, pyarrow, huggingface_hub). Uploading needs
HF_TOKEN in the environment and --repo-id; --dry-run only builds the folder.

Before uploading, the new manifest is compared with the published one: a
missing file, a dropped column, or a file with 5% fewer rows stops the upload.
The upload names the revision it started from, so a concurrent change makes it
fail instead of being overwritten. The dataset must already exist.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from . import collect_followers, collect_history, collect_upcoming, storage
from . import events as event_data

log = logging.getLogger("publish_dataset")

INT_COLUMNS = {
    "appid", "tagid", "release_ts", "date_ok", "early_access", "wishlist_rank", "price_cents",
    "is_free", "followers", "launch_ts", "steam_release_ts", "early_access_now",
    "demo_release_ts", "demo_before_launch", "reviews_total_now", "reviews_30d",
    "reviews_30d_positive", "reviews_before_launch", "steam_appid", "reviews_1d", "reviews_7d",
    "games", "dated", "ranked", "ranked_not_listed", "date_mismatch", "requests", "seconds", "ranking_ok",
}
BOOL_COLUMNS = {"on_steam_at_launch", "free_to_play"}
DATE_COLUMNS = {"date", "date_end", "launch_date", "first_seen", "last_seen", "snapshot_date",
                "reviews_30d_fetched", "prior_check_fetched", "reviews_early_fetched",
                "first_listed", "last_listed", "prev_date", "prev_date_end", "start", "end"}
MARKER = ".publish-dataset-build"  # marks a folder this script built, so it may delete it
GP_KINDS = ("followers", "players")
SHRINK_LIMIT = 0.95
RELEASE_FIELDS = ["raw", "precision", "date", "date_end"]


def typed(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Integers as nullable Int64, flags as nullable booleans, ISO dates as dates,
    everything else as text.

    With `columns`, missing ones are added empty, so files written at
    different times (before and after a column was added) share one schema.
    """
    if columns:
        for col in columns:
            if col not in df.columns:
                df[col] = pd.NA
        df = df[[c for c in df.columns if c not in columns] + columns]
    for col in df.columns:
        if col in INT_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        elif col in BOOL_COLUMNS:
            df[col] = df[col].astype("boolean")
        elif col in DATE_COLUMNS:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        elif col in ("starts_at", "ends_at"):
            continue  # already UTC timestamps
        elif col == "fetched_at":
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
        else:
            df[col] = df[col].astype("string")
    return df


def read(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    return typed(pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""]), columns)


def write(df: pd.DataFrame, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return len(df)


def monthly(src_dir: Path, out_dir: Path, columns: list[str]) -> dict[str, int]:
    """Combine YYYY-MM-DD.csv.gz files into YYYY-MM.parquet with a snapshot_date column."""
    by_month: dict[str, list[Path]] = defaultdict(list)
    for f in sorted(src_dir.glob("*.csv.gz")):
        by_month[f.name[:7]].append(f)
    counts = {}
    for month, files in by_month.items():
        parts = []
        for f in files:
            df = read(f, columns)
            df.insert(0, "snapshot_date", pd.to_datetime(f.name[:10]).date())
            parts.append(df)
        counts[month] = write(pd.concat(parts, ignore_index=True), out_dir / f"{month}.parquet")
    return counts


def release_changes(src_dir: Path) -> pd.DataFrame:
    """One row per game each time its release date text or range changes, plus its
    first day in the snapshots, each day it left the coming-soon list, and each
    day it came back. Days with no snapshot file are simply skipped."""
    prev: dict[str, dict] = {}
    seen: set[str] = set()
    rows = []
    for f in sorted(src_dir.glob("*.csv.gz")):
        day = f.name[:10]
        today = {}
        for r in storage.read_csv(f):
            today[r["appid"]] = cur = {k: r.get(k, "") for k in RELEASE_FIELDS}
            old = prev.get(r["appid"])
            if old is None:
                change = "returned" if r["appid"] in seen else "first_seen"
                rows.append({"appid": r["appid"], "snapshot_date": day, "change": change, **cur})
                seen.add(r["appid"])
            elif old != cur:
                rows.append({"appid": r["appid"], "snapshot_date": day, "change": "changed", **cur,
                             **{f"prev_{k}": v for k, v in old.items()}})
        for appid, old in prev.items():
            if appid not in today:
                rows.append({"appid": appid, "snapshot_date": day, "change": "left_list",
                             **{f"prev_{k}": v for k, v in old.items()}})
        prev = today
    columns = ["appid", "snapshot_date", "change", *RELEASE_FIELDS, *(f"prev_{k}" for k in RELEASE_FIELDS)]
    df = pd.DataFrame(rows, columns=columns)
    df = df.sort_values(["snapshot_date", "appid"], key=lambda c: c.astype(int) if c.name == "appid" else c)
    return typed(df.fillna("").replace("", pd.NA).reset_index(drop=True))


def data_date(data_dir: Path) -> str:
    """Date of the newest daily snapshot: the card shows it, so rebuilding the same data gives the same card."""
    days = sorted(f.name[:10] for f in (data_dir / "upcoming" / "snapshots").glob("*.csv.gz"))
    return days[-1] if days else "-"


def manifest(out: Path) -> dict:
    import pyarrow.parquet as pq

    result = {}
    for f in sorted(out.rglob("*.parquet")):
        meta = pq.read_metadata(f)
        result[f.relative_to(out).as_posix()] = {"rows": meta.num_rows, "columns": meta.schema.to_arrow_schema().names}
    return result


def check_manifest(new: dict, old: dict | None) -> list[str]:
    """Reasons not to upload `new` over the published `old` (None for a first upload)."""
    problems = []
    for name, was in (old or {}).items():
        now = new.get(name)
        if now is None:
            problems.append(f"{name}: missing from the new build")
            continue
        dropped = sorted(set(was["columns"]) - set(now["columns"]))
        if dropped:
            problems.append(f"{name}: dropped columns {dropped}")
        if now["rows"] < SHRINK_LIMIT * was["rows"]:
            problems.append(f"{name}: shrank from {was['rows']} to {now['rows']} rows")
    return problems


def remote_gp_kinds(repo_id: str, token: str, api=None) -> set[str]:
    """Which Games Popularity series ("followers", "players") already have files in the dataset."""
    from huggingface_hub import HfApi
    from huggingface_hub.errors import RepositoryNotFoundError

    try:
        files = (api or HfApi(token=token)).list_repo_files(repo_id, repo_type="dataset")
    except RepositoryNotFoundError:
        raise SystemExit(f"dataset {repo_id} not found: create it on Hugging Face first") from None
    return {kind for kind in GP_KINDS if any(f.startswith(f"gp/{kind}/") and f.endswith(".csv.gz") for f in files)}


def build(data_dir: Path, events_path: Path, out: Path, license_id: str, gp_kinds: set[str] = frozenset()) -> dict:
    if out.exists() and any(out.iterdir()):
        if not (out / MARKER).exists():
            raise SystemExit(f"{out} is not a dataset build (no {MARKER}); refusing to delete it")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / MARKER).write_text("built by pipeline.publish_dataset; safe to delete")
    stats = {}
    simple = {
        "history/games.parquet": (data_dir / "history" / "games.csv", collect_history.FIELDS),
        "upcoming/apps.parquet": (data_dir / "upcoming" / "apps.csv", collect_upcoming.APP_FIELDS),
        "followers/latest.parquet": (data_dir / "followers" / "latest.csv", collect_followers.FIELDS),
        "tags.parquet": (data_dir / "tags.csv", ["tagid", "name"]),
        "upcoming/runs.parquet": (data_dir / "upcoming" / "runs.csv", collect_upcoming.RUN_FIELDS),
    }
    for dest, (src, columns) in simple.items():
        if src.exists():
            stats[dest] = write(read(src, columns), out / dest)
    snapshot_columns = {"upcoming": collect_upcoming.SNAPSHOT_FIELDS, "followers": collect_followers.FIELDS}
    for name, columns in snapshot_columns.items():
        months = monthly(data_dir / name / "snapshots", out / name / "snapshots", columns)
        if months:
            stats[f"{name}/snapshots"] = months
    snaps = data_dir / "upcoming" / "snapshots"
    if any(snaps.glob("*.csv.gz")):
        stats["upcoming/release_changes.parquet"] = write(release_changes(snaps),
                                                         out / "upcoming" / "release_changes.parquet")
    stats["events.parquet"] = write(events_table(events_path), out / "events.parquet")
    (out / "manifest.json").write_text(json.dumps(manifest(out), indent=1, sort_keys=True), encoding="utf-8")
    (out / "README.md").write_text(card(stats, license_id, data_date(data_dir), gp_kinds), encoding="utf-8")
    return stats


def events_table(path: Path) -> pd.DataFrame:
    """events.yaml as a table (list fields joined with "|").

    starts_at / ends_at give the exact window in UTC (Steam events run 10:00 to
    10:00 Pacific; other events cover whole Pacific days). free_to_play is only
    written in the YAML when true; releases get an explicit false here.
    """
    rows = []
    for e in event_data.load(path):
        starts, ends = event_data.window(e)
        row = {**e, "starts_at": starts, "ends_at": ends}
        if "tags" in row:
            row["tags"] = "|".join(row["tags"])
        if row["type"] == "major_release":
            row.setdefault("free_to_play", False)
        rows.append(row)
    df = pd.DataFrame(rows)
    for col in ("starts_at", "ends_at"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return typed(df)


def card(stats: dict, license_id: str, updated: str, gp_kinds: set[str] = frozenset()) -> str:
    # (config name, files, key in stats); configs with no data yet are left out
    stats = {**stats, **{f"gp/{k}": 0 for k in gp_kinds}}  # in the dataset already, not built here
    configs = [
        ("history", "history/games.parquet", "history/games.parquet"),
        ("upcoming_snapshots", "upcoming/snapshots/*.parquet", "upcoming/snapshots"),
        ("upcoming_apps", "upcoming/apps.parquet", "upcoming/apps.parquet"),
        ("release_changes", "upcoming/release_changes.parquet", "upcoming/release_changes.parquet"),
        ("followers", "followers/snapshots/*.parquet", "followers/snapshots"),
        ("gp_followers", "gp/followers/*.csv.gz", "gp/followers"),
        ("gp_players", "gp/players/*.csv.gz", "gp/players"),
        ("events", "events.parquet", "events.parquet"),
        ("tags", "tags.parquet", "tags.parquet"),
        ("runs", "upcoming/runs.parquet", "upcoming/runs.parquet"),
    ]
    present = [(name, files) for name, files, key in configs if key in stats]
    meta = {
        "license": license_id,
        "pretty_name": "Steam Launch Window Data",
        "tags": ["steam", "video-games", "game-releases", "time-series"],
        "configs": [{"config_name": n, "data_files": p} for n, p in present],
    }

    def rows(key):
        v = stats.get(key)
        return sum(v.values()) if isinstance(v, dict) else (v or 0)

    snap_months = sorted(stats.get("upcoming/snapshots", {}))
    gp_rows = "".join([
        "| `gp_followers` | raw, daily | grows daily | Steam follower history from [Games Popularity]"
        "(https://games-popularity.com), about one point a day since 2024-03-15: `appid`, `followers`, "
        "`observed_at` (their time, UTC), `fetched_at` (ours); one file per fetch day |\n"
        if "followers" in gp_kinds else "",
        "| `gp_players` | raw, daily | grows daily | concurrent players, hourly, for the first month after "
        "launch, from Games Popularity; same columns with `players` |\n"
        if "players" in gp_kinds else "",
    ])
    return f"""---
{yaml.safe_dump(meta, sort_keys=False).strip()}
---

# Steam Launch Window Data

Data behind [steam-launch-window](https://github.com/wyc79/steam-launch-window),
a tool that helps indie developers pick a Steam launch week. Updated weekly
(the `gp_` configs daily). Last update: {updated}.

Not affiliated with or endorsed by Valve. The data comes from Steam's public
store pages and endpoints, collected politely (rate-limited, no logins), and the
`gp_` configs from [Games Popularity](https://games-popularity.com).
No personal data: no Steam IDs, usernames or review texts, only counts.

## What is here

| Config | Kind | Rows | What |
|---|---|---|---|
| `history` | today's view | {rows("history/games.parquet"):,} | games launched on Steam since 2022: launch date and type, price, tags, languages, demo, reviews in the first day, week and 30 days |
| `upcoming_snapshots` | raw, daily | {rows("upcoming/snapshots"):,} | one row per coming-soon game per day ({snap_months[0] if snap_months else "-"} to {snap_months[-1] if snap_months else "-"}): release date and its precision, Early Access, wishlist rank, price if set |
| `upcoming_apps` | latest | {rows("upcoming/apps.parquet"):,} | name, developers, publishers, tags with vote weights, languages, demo; `last_seen` is the last day the game was coming soon |
| `release_changes` | derived | {rows("upcoming/release_changes.parquet"):,} | each game's first day in the snapshots, every change of its release date text or range, each day it left the coming-soon list, and each day it came back (`returned`) |
| `followers` | raw | {rows("followers/snapshots"):,} | Steam community hub follower counts, with fetch time |
{gp_rows}| `events` | curated | {rows("events.parquet"):,} | Steam sales, Next Fests, themed fests, major releases, regional holidays, each with a source; `starts_at`/`ends_at` (UTC) give the exact window: Steam events run from 10:00 Pacific on `start` to 10:00 Pacific on `end` |
| `tags` | latest | {rows("tags.parquet"):,} | Steam tag id to name |
| `runs` | log | {rows("upcoming/runs.parquet"):,} | one row per daily collection: games, requests, whether the wishlist crawl worked |

```python
from datasets import load_dataset
history = load_dataset("<this repo>", "history")
```

## When each value was observed

- **Observed at the time:** `upcoming_snapshots` (one row per day, `snapshot_date` in UTC),
  `followers` (`fetched_at`), `runs`. Use these for "what was known before launch".
  The `gp_` configs were recorded at the time by Games Popularity (`observed_at`)
  but fetched by us later, often long after (`fetched_at`). Each fetch only asks
  for points newer than the ones already fetched, so a game's series is spread
  over several fetch-day files.
- **Frozen before launch:** a launched game's `upcoming_apps` row stops updating
  when it leaves the coming-soon list, so its tags, publisher, demo and languages
  are pre-launch values when `last_seen` is before the launch date.
- **Today's view:** `history`. Price, demo, Early Access status and tags are as
  they are now, and tags keep being voted after launch. Review counts cover a
  fixed window after launch but only reviews that still exist.
  `first_listed`/`last_listed` say when a game was first and last seen in
  Steam's list of released games; rows of games that disappear are kept.

## Things to know before using it

- **Dates** are Pacific time. Fuzzy release dates ("Q3 2027") have a
  `precision` and a `date` to `date_end` range.
- **Reviews** of paid games are from people who bought the game on Steam (key
  activations excluded), like the store's own count. Free games count all
  reviews, since nobody buys them; `reviews_purchase` says which (`steam` or
  `all`; empty means `steam`). Delisted games that left before collection
  started are missing.
- **`launch_type`**: `full`, `early_access`, or `ea_exit` (a 1.0 launch of a
  game that was already on sale in Early Access; treat these apart).
- **Wishlist rank** only covers Steam's top ~5,300 wishlisted games.
- **Upcoming prices** are almost always missing: paid games set them at launch.
- **Missing days:** `runs` shows which days were collected.

## Data rights

No license is granted here for the data. The code that builds it is MIT
licensed ([LICENSE](https://github.com/wyc79/steam-launch-window/blob/main/LICENSE)),
and that license covers the code only. The facts in this dataset (release
dates, tags, review and follower counts) come from Steam, owned by Valve
Corporation, which has not licensed or endorsed this dataset. Game names are
trademarks of their owners. Whether you may reuse the data depends on Valve's
terms for Steam data and on your local law. The `gp_` follower and player
histories come from [Games Popularity](https://games-popularity.com) and are
republished with its owner's permission (2026-10-12); credit them if you use them.
The `gp/` folder also holds `state.csv` and `runs.csv`, the collector's working
files (what was fetched when, and with what result).

Full methods: [README](https://github.com/wyc79/steam-launch-window#readme) and
[endpoint notes](https://github.com/wyc79/steam-launch-window/blob/main/docs/endpoints.md).
"""


def upload(out: Path, repo_id: str, token: str, api=None) -> None:
    from huggingface_hub import HfApi
    from huggingface_hub.errors import RemoteEntryNotFoundError, RepositoryNotFoundError

    api = api or HfApi(token=token)
    try:
        head = api.repo_info(repo_id, repo_type="dataset").sha
    except RepositoryNotFoundError:
        raise SystemExit(f"dataset {repo_id} not found: create it on Hugging Face first") from None
    try:
        old = json.loads(Path(api.hf_hub_download(repo_id, "manifest.json", repo_type="dataset",
                                                  revision=head)).read_text(encoding="utf-8"))
    except RemoteEntryNotFoundError:  # no manifest published yet; a network error must fail, not skip the check
        old = None
    new = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    problems = check_manifest(new, old)
    if problems:
        raise SystemExit("not uploading:\n  " + "\n  ".join(problems))
    stamp = datetime.now(timezone.utc).date().isoformat()
    api.upload_folder(folder_path=str(out), repo_id=repo_id, repo_type="dataset", parent_commit=head,
                      ignore_patterns=[MARKER], commit_message=f"Weekly update {stamp}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, default=Path("_data"))
    p.add_argument("--events", type=Path, default=Path("data/events.yaml"))
    p.add_argument("--out", type=Path, default=Path(".cache/dataset"))
    p.add_argument("--repo-id", default=os.environ.get("HF_DATASET_REPO", ""),
                   help="Hugging Face dataset, e.g. user/steam-launch-data")
    p.add_argument("--license", default="other",
                   help="Hugging Face license id for the card. 'other': the data is Steam's, not ours to license")
    p.add_argument("--dry-run", action="store_true", help="build the folder but do not upload")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    token = os.environ.get("HF_TOKEN")
    gp_kinds = remote_gp_kinds(args.repo_id, token) if token and args.repo_id else set()
    stats = build(args.data_dir, args.events, args.out, args.license, gp_kinds)
    log.info("built %s: %s; Games Popularity configs: %s", args.out, stats, sorted(gp_kinds) or "none")
    if args.dry_run:
        return 0
    if not token or not args.repo_id:
        raise SystemExit("set HF_TOKEN and --repo-id (or HF_DATASET_REPO) to upload, or use --dry-run")
    upload(args.out, args.repo_id, token)
    log.info("uploaded to https://huggingface.co/datasets/%s", args.repo_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
